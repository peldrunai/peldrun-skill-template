#!/usr/bin/env python3
"""Validate skill manifest.json against the official PELDRUN schema.

This script ensures a skill's manifest.json passes all validation rules
that PELDRUN enforces at install time. It catches errors before they
reach the installer.

Usage:
    python scripts/validate_manifest.py <skill_id>     # validate one skill
    python scripts/validate_manifest.py --all          # validate all skills
    python scripts/validate_manifest.py <path/to/manifest.json>

Exit codes:
    0 - All validations passed
    1 - One or more validations failed
    2 - File not found or invalid JSON
    3 - Schema file not found

The script performs:
    - JSON parsing
    - JSON Schema validation (using jsonschema library)
    - Semantic checks (sub-skill files exist, no duplicate IDs)
    - Frontmatter validation in SKILL.md files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import Draft7Validator, FormatChecker
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema==4.23.0")
    sys.exit(3)

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml==6.0.2")
    sys.exit(3)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "manifest.schema.json"
SKILLS_DIR = REPO_ROOT / "skills"

# File types that PELDRUN rejects at install time
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib",  # Executables
    ".pyc", ".pyo", ".pyd",            # Bytecode
    ".git", ".svn", ".hg",             # VCS metadata
}

FORBIDDEN_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules", ".venv", "venv"}

MAX_PACKAGE_SIZE = 100 * 1024 * 1024  # 100 MB uncompressed
MAX_FILE_SIZE = 5 * 1024 * 1024         # 5 MB per file
MAX_FILES = 500
MAX_PATH_DEPTH = 10


class ManifestValidator:
    """Accumulates all validation errors and reports them together."""

    def __init__(self, skill_path: Path) -> None:
        self.skill_path = skill_path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def validate_all(self) -> bool:
        """Run all validation checks. Returns True if no errors."""
        self._check_manifest_exists()
        if self.errors:
            return False

        manifest = self._load_manifest()
        if manifest is None:
            return False

        self._validate_schema(manifest)
        self._validate_skill_files(manifest)
        self._validate_sub_skills(manifest)
        self._validate_package_safety()

        return len(self.errors) == 0

    def _check_manifest_exists(self) -> None:
        manifest_path = self.skill_path / "manifest.json"
        if not manifest_path.is_file():
            self.error(f"manifest.json not found at {manifest_path}")

    def _load_manifest(self) -> dict[str, Any] | None:
        manifest_path = self.skill_path / "manifest.json"
        try:
            raw = manifest_path.read_text(encoding="utf-8")
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            self.error(f"manifest.json is not valid JSON: {exc}")
            return None
        except OSError as exc:
            self.error(f"Could not read manifest.json: {exc}")
            return None

    def _validate_schema(self, manifest: dict[str, Any]) -> None:
        """Validate against the official JSON Schema."""
        if not SCHEMA_PATH.is_file():
            self.error(f"Schema file not found: {SCHEMA_PATH}")
            return

        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self.error(f"Could not load schema: {exc}")
            return

        validator = Draft7Validator(schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(manifest))

        for err in sorted(errors, key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in err.absolute_path) or "<root>"
            self.error(f"Schema: {path}: {err.message}")

    def _validate_skill_files(self, manifest: dict[str, Any]) -> None:
        """Verify SKILL.md and references exist."""
        execution = manifest.get("execution", {})
        instructions_file = execution.get("instructions_file", "SKILL.md")
        instructions_path = self.skill_path / instructions_file

        if not instructions_path.is_file():
            self.error(f"Instructions file not found: {instructions_file}")
        else:
            self._validate_skill_frontmatter(instructions_path)

        references_dir = execution.get("references_dir")
        if references_dir:
            ref_path = self.skill_path / references_dir
            if not ref_path.is_dir():
                self.error(f"References directory not found: {references_dir}")

        icon = manifest.get("icon")
        if icon and ".." not in icon:
            icon_path = self.skill_path / icon
            if not icon_path.is_file():
                self.warn(f"Icon file not found: {icon}")

    def _validate_skill_frontmatter(self, skill_md: Path) -> None:
        """Validate YAML frontmatter in SKILL.md."""
        try:
            content = skill_md.read_text(encoding="utf-8")
        except OSError as exc:
            self.error(f"Could not read {skill_md.name}: {exc}")
            return

        if not content.startswith("---"):
            self.error(f"{skill_md.name} must start with '---' YAML frontmatter")
            return

        # Find the closing ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            self.error(f"{skill_md.name} missing closing '---' for frontmatter")
            return

        frontmatter_text = content[3:end_idx].strip()
        if not frontmatter_text:
            self.warn(f"{skill_md.name} has empty frontmatter")
            return

        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                self.error(f"{skill_md.name} frontmatter must be a YAML mapping")
        except yaml.YAMLError as exc:
            self.error(f"{skill_md.name} frontmatter is not valid YAML: {exc}")

    def _validate_sub_skills(self, manifest: dict[str, Any]) -> None:
        """Validate sub-skills (router pattern)."""
        sub_skills = manifest.get("sub_skills", [])
        if not sub_skills:
            return

        seen_ids: set[str] = set()
        for idx, sub in enumerate(sub_skills):
            sub_id = sub.get("id", f"<missing-{idx}>")

            # Check for duplicate IDs
            if sub_id in seen_ids:
                self.error(f"Duplicate sub_skill id: '{sub_id}'")
            seen_ids.add(sub_id)

            # Check instructions_file exists
            instructions_file = sub.get("instructions_file", "")
            if not instructions_file:
                continue

            # Security: prevent path traversal
            if ".." in instructions_file:
                self.error(
                    f"sub_skills[{idx}].instructions_file contains '..': {instructions_file}"
                )
                continue

            if not instructions_file.startswith("sub_skills/"):
                self.error(
                    f"sub_skills[{idx}].instructions_file must start with 'sub_skills/': "
                    f"{instructions_file}"
                )
                continue

            sub_path = self.skill_path / instructions_file
            if not sub_path.is_file():
                self.error(
                    f"sub_skills[{idx}] ({sub_id}): file not found: {instructions_file}"
                )
            else:
                self._validate_skill_frontmatter(sub_path)

    def _validate_package_safety(self) -> None:
        """Check for forbidden files and size limits."""
        file_count = 0
        total_size = 0

        for path in self.skill_path.rglob("*"):
            if path.is_file():
                # Skip hidden files and __pycache__
                rel_parts = path.relative_to(self.skill_path).parts
                if any(part.startswith(".") or part in FORBIDDEN_DIRS for part in rel_parts[:-1]):
                    continue

                file_count += 1
                size = path.stat().st_size
                total_size += size

                # Check individual file size
                if size > MAX_FILE_SIZE:
                    self.error(
                        f"File exceeds 5 MB limit: {path.relative_to(self.skill_path)} "
                        f"({size:,} bytes)"
                    )

                # Check forbidden extensions
                if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
                    self.error(
                        f"Forbidden file type: {path.relative_to(self.skill_path)}"
                    )

                # Check path depth
                if len(rel_parts) > MAX_PATH_DEPTH:
                    self.error(
                        f"Path depth exceeds {MAX_PATH_DEPTH}: "
                        f"{path.relative_to(self.skill_path)}"
                    )

        if file_count > MAX_FILES:
            self.error(f"Too many files: {file_count} (max {MAX_FILES})")

        if total_size > MAX_PACKAGE_SIZE:
            self.error(
                f"Package size exceeds 100 MB: {total_size:,} bytes"
            )

    def report(self) -> int:
        """Print results and return exit code."""
        skill_name = self.skill_path.name
        header = f"[{skill_name}]"

        if self.warnings:
            for w in self.warnings:
                print(f"{header} WARNING: {w}")

        if self.errors:
            for e in self.errors:
                print(f"{header} ERROR: {e}")
            print(f"{header} FAILED ({len(self.errors)} error(s))")
            return 1

        print(f"{header} OK")
        return 0


def discover_skills() -> list[Path]:
    """Find all skill directories in the repository."""
    skills: list[Path] = []

    # Check for single-skill repo (manifest at root)
    if (REPO_ROOT / "manifest.json").is_file():
        skills.append(REPO_ROOT)

    # Check for multi-skill repo (skills/<id>/manifest.json)
    if SKILLS_DIR.is_dir():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "manifest.json").is_file():
                # Skip example directories
                if skill_dir.name.startswith("_"):
                    continue
                skills.append(skill_dir)

    return skills


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate PELDRUN skill manifests against the official schema."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Validate all skills in the repository",
    )
    group.add_argument(
        "skill",
        nargs="?",
        help="Skill ID to validate (or path to manifest.json)",
    )
    args = parser.parse_args()

    if args.all:
        skills = discover_skills()
        if not skills:
            print("No skills found in repository.")
            return 1

        print(f"Validating {len(skills)} skill(s)...\n")
        exit_code = 0
        for skill_path in skills:
            validator = ManifestValidator(skill_path)
            validator.validate_all()
            exit_code = max(exit_code, validator.report())

        print(f"\n{'='*60}")
        print(f"Total: {len(skills)} skill(s) validated")
        return exit_code

    else:
        # Single skill validation
        skill_arg = args.skill
        skill_path = Path(skill_arg)

        # Handle skill_id (not a path)
        if not skill_path.exists() or not skill_path.is_dir():
            candidate = SKILLS_DIR / skill_arg
            if (candidate / "manifest.json").is_file():
                skill_path = candidate
            elif (REPO_ROOT / "manifest.json").is_file():
                # Single-skill repo
                skill_path = REPO_ROOT
            else:
                print(f"Error: Skill '{skill_arg}' not found")
                return 2

        validator = ManifestValidator(skill_path)
        validator.validate_all()
        return validator.report()


if __name__ == "__main__":
    sys.exit(main())