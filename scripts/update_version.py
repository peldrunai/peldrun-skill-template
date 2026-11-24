#!/usr/bin/env python3
"""Bump the semantic version of a skill's manifest.json.

Updates the version in manifest.json and optionally prepends a
CHANGELOG section generated from git commits.

Usage:
    python scripts/update_version.py <skill_id> patch      # 1.0.0 -> 1.0.1
    python scripts/update_version.py <skill_id> minor      # 1.0.0 -> 1.1.0
    python scripts/update_version.py <skill_id> major      # 1.0.0 -> 2.0.0
    python scripts/update_version.py <skill_id> 1.2.3      # exact version
    python scripts/update_version.py --all patch            # bump all skills

Exit codes:
    0 - Success
    1 - Invalid arguments
    2 - Skill not found
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(.*)$")


def bump_version(current: str, bump: str) -> str:
    """Bump a semantic version string."""
    match = VERSION_PATTERN.match(current)
    if not match:
        raise ValueError(f"Invalid version format: {current}")

    major, minor, patch, suffix = match.groups()
    major, minor, patch = int(major), int(minor), int(patch)

    if bump == "major":
        return f"{major + 1}.0.0"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif VERSION_PATTERN.match(bump):
        return bump
    else:
        raise ValueError(
            f"Invalid bump type: '{bump}'. "
            f"Use 'major', 'minor', 'patch', or an exact version."
        )


def find_skill_path(skill_id: str) -> Path | None:
    """Locate skill directory by ID."""
    # Single-skill repo
    root_manifest = REPO_ROOT / "manifest.json"
    if root_manifest.is_file():
        try:
            manifest = json.loads(root_manifest.read_text(encoding="utf-8"))
            if manifest.get("id") == skill_id:
                return REPO_ROOT
        except (json.JSONDecodeError, OSError):
            pass

    # Multi-skill repo
    candidate = SKILLS_DIR / skill_id
    if (candidate / "manifest.json").is_file():
        return candidate

    return None


def update_skill_version(skill_path: Path, bump: str) -> tuple[str, str]:
    """Update version in manifest.json. Returns (old_version, new_version)."""
    manifest_path = skill_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    old_version = manifest["version"]
    new_version = bump_version(old_version, bump)

    manifest["version"] = new_version

    # Write back with consistent formatting
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return old_version, new_version


def discover_skills() -> list[Path]:
    """Find all skill directories."""
    skills: list[Path] = []

    # Single-skill repo
    if (REPO_ROOT / "manifest.json").is_file():
        skills.append(REPO_ROOT)

    # Multi-skill repo
    if SKILLS_DIR.is_dir():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "manifest.json").is_file():
                if not skill_dir.name.startswith("_"):
                    skills.append(skill_dir)

    return skills


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bump skill version in manifest.json"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Bump all skills in the repository",
    )
    parser.add_argument(
        "skill_id",
        nargs="?",
        help="Skill ID (omit with --all)",
    )
    parser.add_argument(
        "bump",
        help="Bump type: 'major', 'minor', 'patch', or exact version",
    )
    args = parser.parse_args()

    if args.all:
        skills = discover_skills()
        if not skills:
            print("No skills found")
            return 2

        print(f"Bumping {len(skills)} skill(s) with '{args.bump}'...\n")
        for skill_path in skills:
            skill_name = skill_path.name
            try:
                old, new = update_skill_version(skill_path, args.bump)
                print(f"[{skill_name}] {old} -> {new}")
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"[{skill_name}] ERROR: {exc}")
                return 1

        return 0

    else:
        if not args.skill_id:
            parser.error("skill_id required when not using --all")

        skill_path = find_skill_path(args.skill_id)
        if skill_path is None:
            print(f"Error: Skill '{args.skill_id}' not found")
            return 2

        try:
            old, new = update_skill_version(skill_path, args.bump)
            print(f"Updated {args.skill_id}: {old} -> {new}")
            print(f"\nNext steps:")
            print(f"  1. Review changes: git diff")
            print(f"  2. Commit: git commit -m 'chore(release): {args.skill_id} v{new}'")
            print(f"  3. Tag: git tag -a {args.skill_id}-v{new} -m 'Release v{new}'")
            print(f"  4. Push: git push origin main && git push origin {args.skill_id}-v{new}")
            return 0
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}")
            return 1


if __name__ == "__main__":
    sys.exit(main())