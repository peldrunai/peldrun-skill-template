#!/usr/bin/env python3
"""Build a PELDRUN skill package (.zip) from a skill directory.

The ZIP must contain manifest.json and SKILL.md at its ROOT (not wrapped
in a directory). This matches PELDRUN's install-time expectations.

Usage:
    python scripts/build_package.py <skill_id>          # build one skill
    python scripts/build_package.py --all                # build all skills
    python scripts/build_package.py <skill_id> --verify  # build and verify

Output:
    dist/<skill_id>-<version>.zip

Forbidden files (.exe, .pyc, .git/, etc.) are automatically excluded.
The --verify flag runs verify_package.py on the built ZIP to mirror
PELDRUN's install-time checks.

Exit codes:
    0 - Build succeeded
    1 - Build failed or verification failed
    2 - Skill not found
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
DIST_DIR = REPO_ROOT / "dist"

# Files and directories to always exclude from the ZIP
EXCLUDE_PATTERNS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "node_modules", ".git", ".svn", ".hg",
    ".DS_Store", "Thumbs.db",
}

EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".pyd"}


def find_skill_path(skill_id: str) -> Path | None:
    """Locate the skill directory by ID."""
    # Check single-skill repo (root manifest)
    root_manifest = REPO_ROOT / "manifest.json"
    if root_manifest.is_file():
        try:
            manifest = json.loads(root_manifest.read_text(encoding="utf-8"))
            if manifest.get("id") == skill_id:
                return REPO_ROOT
        except (json.JSONDecodeError, OSError):
            pass

    # Check multi-skill repo
    candidate = SKILLS_DIR / skill_id
    if (candidate / "manifest.json").is_file():
        return candidate

    return None


def should_include(path: Path, skill_root: Path) -> bool:
    """Determine if a file should be included in the ZIP."""
    rel_path = path.relative_to(skill_root)

    # Skip hidden files/directories at any level
    for part in rel_path.parts:
        if part.startswith(".") or part in EXCLUDE_PATTERNS:
            return False

    # Skip forbidden extensions
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return False

    # Skip the dist directory itself
    if rel_path.parts and rel_path.parts[0] == "dist":
        return False

    return True


def build_package(skill_path: Path) -> Path:
    """Build a ZIP package for the skill. Returns the output path."""
    manifest_path = skill_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    skill_id = manifest["id"]
    version = manifest["version"]
    zip_name = f"{skill_id}-{version}.zip"

    DIST_DIR.mkdir(exist_ok=True)
    zip_path = DIST_DIR / zip_name

    print(f"Building: {skill_id} v{version}")
    print(f"Source:   {skill_path}")
    print(f"Output:   {zip_path}")

    # Collect files
    files: list[tuple[Path, str]] = []
    for file_path in skill_path.rglob("*"):
        if file_path.is_file() and should_include(file_path, skill_path):
            rel_path = str(file_path.relative_to(skill_path))
            # Normalize path separators for ZIP (always use forward slash)
            arc_name = rel_path.replace(os.sep, "/")
            files.append((file_path, arc_name))

    if not files:
        print(f"ERROR: No files found to package")
        sys.exit(1)

    # Verify manifest.json and SKILL.md are at root
    arc_names = {arc for _, arc in files}
    if "manifest.json" not in arc_names:
        print(f"ERROR: manifest.json not found at package root")
        sys.exit(1)

    instructions_file = manifest.get("execution", {}).get(
        "instructions_file", "SKILL.md"
    )
    if instructions_file not in arc_names:
        print(f"ERROR: Instructions file '{instructions_file}' not at package root")
        sys.exit(1)

    # Create ZIP with deterministic ordering
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Sort files for deterministic output (important for reproducible builds)
        for file_path, arc_name in sorted(files, key=lambda x: x[1]):
            zf.write(file_path, arc_name)

    size = zip_path.stat().st_size
    print(f"Built:    {zip_name} ({size:,} bytes, {len(files)} files)")

    return zip_path


def verify_package(zip_path: Path) -> int:
    """Run verify_package.py on the built ZIP."""
    verify_script = REPO_ROOT / "scripts" / "verify_package.py"
    result = subprocess.run(
        [sys.executable, str(verify_script), str(zip_path)],
        cwd=REPO_ROOT,
    )
    return result.returncode


def build_all() -> list[Path]:
    """Build all skills in the repository."""
    built: list[Path] = []

    # Single-skill repo
    root_manifest = REPO_ROOT / "manifest.json"
    if root_manifest.is_file():
        try:
            manifest = json.loads(root_manifest.read_text(encoding="utf-8"))
            skill_id = manifest.get("id", "unknown")
            print(f"\n{'='*60}")
            zip_path = build_package(REPO_ROOT)
            built.append(zip_path)
        except (json.JSONDecodeError, KeyError) as exc:
            print(f"ERROR: Could not read root manifest: {exc}")

    # Multi-skill repo
    if SKILLS_DIR.is_dir():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "manifest.json").is_file():
                if skill_dir.name.startswith("_"):
                    continue
                print(f"\n{'='*60}")
                zip_path = build_package(skill_dir)
                built.append(zip_path)

    return built


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build PELDRUN skill packages (.zip)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Build all skills in the repository",
    )
    group.add_argument(
        "skill_id",
        nargs="?",
        help="Skill ID to build",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify the built package after building",
    )
    args = parser.parse_args()

    if args.all:
        built = build_all()
        if not built:
            print("No skills found to build.")
            return 1

        if args.verify:
            print(f"\n{'='*60}")
            print(f"Verifying {len(built)} package(s)...")
            for zip_path in built:
                print(f"\nVerifying: {zip_path.name}")
                exit_code = verify_package(zip_path)
                if exit_code != 0:
                    return exit_code

        print(f"\n{'='*60}")
        print(f"Successfully built {len(built)} package(s)")
        return 0

    else:
        skill_path = find_skill_path(args.skill_id)
        if skill_path is None:
            print(f"Error: Skill '{args.skill_id}' not found")
            return 2

        zip_path = build_package(skill_path)

        if args.verify:
            print(f"\nVerifying package...")
            return verify_package(zip_path)

        return 0


if __name__ == "__main__":
    sys.exit(main())