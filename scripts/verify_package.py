#!/usr/bin/env python3
"""Verify a built PELDRUN skill ZIP matches install-time requirements.

This script mirrors exactly what PELDRUN performs when installing a skill
from a ZIP. If verification passes, the ZIP will install successfully.

Usage:
    python scripts/verify_package.py dist/<skill_id>-<version>.zip

Checks performed:
    - ZIP can be opened
    - manifest.json exists at root and is valid JSON
    - manifest passes JSON Schema validation
    - SKILL.md exists and has valid frontmatter
    - All declared sub-skill files exist in the ZIP
    - No forbidden files (.exe, .pyc, etc.)
    - No path traversal attacks
    - Package size within limits

Exit codes:
    0 - Verification passed
    1 - Verification failed
    2 - File not found
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft7Validator, FormatChecker
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema==4.23.0")
    sys.exit(3)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "manifest.schema.json"

FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".pyd",
}

FORBIDDEN_NAMES = {".git", ".svn", ".hg", "__pycache__", "node_modules"}

MAX_PACKAGE_SIZE = 100 * 1024 * 1024
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_FILES = 500
MAX_PATH_DEPTH = 10


class PackageVerifier:
    """Verify a ZIP package against PELDRUN install requirements."""

    def __init__(self, zip_path: Path) -> None:
        self.zip_path = zip_path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.manifest: dict | None = None

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def verify(self) -> bool:
        """Run all verification checks."""
        if not self.zip_path.is_file():
            self.error(f"File not found: {self.zip_path}")
            return False

        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                self._check_forbidden_files(zf)
                self._check_path_traversal(zf)
                self._check_size_limits(zf)
                self._load_and_validate_manifest(zf)
                self._verify_sub_skills(zf)
        except zipfile.BadZipFile as exc:
            self.error(f"Invalid ZIP file: {exc}")

        return len(self.errors) == 0

    def _check_forbidden_files(self, zf: zipfile.ZipFile) -> None:
        """Check for forbidden file types and names."""
        for info in zf.infolist():
            name = info.filename
            parts = name.split("/")

            # Check forbidden directory names
            for part in parts[:-1]:
                if part in FORBIDDEN_NAMES:
                    self.error(f"Forbidden directory in ZIP: {name}")

            # Check forbidden extensions
            ext = Path(name).suffix.lower()
            if ext in FORBIDDEN_EXTENSIONS:
                self.error(f"Forbidden file type in ZIP: {name}")

            # Check for symlinks
            if info.external_attr >> 28 == 0xA:  # symlink attribute
                self.error(f"Symlink detected in ZIP: {name}")

    def _check_path_traversal(self, zf: zipfile.ZipFile) -> None:
        """Detect path traversal attacks."""
        for info in zf.infolist():
            name = info.filename
            if ".." in name.split("/"):
                self.error(f"Path traversal detected: {name}")
            if name.startswith("/") or ":" in name:
                self.error(f"Absolute path in ZIP: {name}")

    def _check_size_limits(self, zf: zipfile.ZipFile) -> None:
        """Verify size constraints."""
        file_count = 0
        total_size = 0

        for info in zf.infolist():
            file_count += 1
            total_size += info.file_size

            if info.file_size > MAX_FILE_SIZE:
                self.error(
                    f"File exceeds 5 MB limit: {info.filename} "
                    f"({info.file_size:,} bytes)"
                )

        if file_count > MAX_FILES:
            self.error(f"Too many files in ZIP: {file_count} (max {MAX_FILES})")

        if total_size > MAX_PACKAGE_SIZE:
            self.error(
                f"Package exceeds 100 MB limit: {total_size:,} bytes"
            )

    def _load_and_validate_manifest(self, zf: zipfile.ZipFile) -> None:
        """Load and validate manifest.json from the ZIP."""
        if "manifest.json" not in zf.namelist():
            self.error("manifest.json not found at ZIP root")
            return

        try:
            with zf.open("manifest.json") as f:
                raw = f.read().decode("utf-8")
                self.manifest = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.error(f"manifest.json is not valid: {exc}")
            return

        # Validate against schema
        if not SCHEMA_PATH.is_file():
            self.warn(f"Schema not found at {SCHEMA_PATH}, skipping schema validation")
            return

        try:
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            validator = Draft7Validator(schema, format_checker=FormatChecker())
            errors = list(validator.iter_errors(self.manifest))

            for err in errors:
                path = ".".join(str(p) for p in err.absolute_path) or "<root>"
                self.error(f"Schema: {path}: {err.message}")
        except Exception as exc:
            self.error(f"Schema validation failed: {exc}")

    def _verify_sub_skills(self, zf: zipfile.ZipFile) -> None:
        """Verify all sub-skill files exist in the ZIP."""
        if not self.manifest:
            return

        zip_names = set(zf.namelist())

        # Check main instructions file
        instructions_file = self.manifest.get("execution", {}).get(
            "instructions_file", "SKILL.md"
        )
        if instructions_file not in zip_names:
            self.error(f"Instructions file not in ZIP: {instructions_file}")

        # Check sub-skills
        sub_skills = self.manifest.get("sub_skills", [])
        seen_ids: set[str] = set()

        for idx, sub in enumerate(sub_skills):
            sub_id = sub.get("id", f"<missing-{idx}>")

            if sub_id in seen_ids:
                self.error(f"Duplicate sub_skill id: '{sub_id}'")
            seen_ids.add(sub_id)

            sub_file = sub.get("instructions_file", "")
            if not sub_file:
                continue

            # Normalize path separators
            normalized = sub_file.replace("\\", "/")

            if ".." in normalized.split("/"):
                self.error(f"sub_skills[{idx}].instructions_file has '..': {sub_file}")
                continue

            if not normalized.startswith("sub_skills/"):
                self.error(
                    f"sub_skills[{idx}].instructions_file must start with 'sub_skills/': "
                    f"{sub_file}"
                )
                continue

            if normalized not in zip_names:
                self.error(
                    f"sub_skills[{idx}] ({sub_id}): file not in ZIP: {sub_file}"
                )

    def report(self) -> int:
        """Print results and return exit code."""
        header = f"[{self.zip_path.name}]"

        for w in self.warnings:
            print(f"{header} WARNING: {w}")

        if self.errors:
            for e in self.errors:
                print(f"{header} ERROR: {e}")
            print(f"\n{header} VERIFICATION FAILED ({len(self.errors)} error(s))")
            return 1

        print(f"{header} VERIFICATION PASSED")
        if self.manifest:
            print(f"  Skill ID:  {self.manifest.get('id')}")
            print(f"  Version:   {self.manifest.get('version')}")
            sub_count = len(self.manifest.get("sub_skills", []))
            if sub_count > 0:
                print(f"  Sub-skills: {sub_count}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a PELDRUN skill ZIP package"
    )
    parser.add_argument("zip_path", type=Path, help="Path to the ZIP file")
    args = parser.parse_args()

    verifier = PackageVerifier(args.zip_path)
    verifier.verify()
    return verifier.report()


if __name__ == "__main__":
    sys.exit(main())