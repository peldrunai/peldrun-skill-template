#!/usr/bin/env python3
"""Generate a CHANGELOG section from git commits using Conventional Commits.

Reads git log between two tags and generates a markdown CHANGELOG section
grouped by commit type (feat, fix, docs, etc.).

Usage:
    python scripts/changelog.py <skill_id> <from_tag> <to_tag>
    python scripts/changelog.py --preview <skill_id>     # preview uncommitted

Commit classification (Conventional Commits):
    feat(scope): ...     -> Features
    fix(scope): ...      -> Bug Fixes
    docs: ...            -> Documentation
    perf: ...            -> Performance
    refactor: ...        -> Refactoring
    chore, test, ci, style -> Skipped

Usage in release workflow:
    python scripts/changelog.py pdf_document pdf_document-v1.0.0 pdf_document-v1.1.0
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Commit type -> section name
COMMIT_TYPES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "perf": "Performance",
    "refactor": "Refactoring",
    "test": None,       # skip
    "chore": None,      # skip
    "ci": None,         # skip
    "style": None,      # skip
    "build": None,      # skip
}

# Pattern: type(scope): description OR type: description
COMMIT_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?\s*:\s*(?P<desc>.+)$",
    re.IGNORECASE,
)


@dataclass
class Commit:
    """A parsed conventional commit."""
    sha: str
    type: str
    scope: str | None
    description: str
    raw: str


@dataclass
class ChangelogEntry:
    """A grouped changelog section."""
    title: str
    commits: list[Commit] = field(default_factory=list)


def get_commits_between(from_tag: str, to_tag: str) -> list[str]:
    """Get raw commit messages between two git references."""
    try:
        result = subprocess.run(
            ["git", "log", "--format=%s", f"{from_tag}..{to_tag}"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError as exc:
        print(f"Error running git log: {exc}")
        print(f"stderr: {exc.stderr}")
        sys.exit(1)


def get_uncommitted_count() -> int:
    """Count commits since last tag for a skill."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


def parse_commit(message: str) -> Commit | None:
    """Parse a conventional commit message."""
    match = COMMIT_PATTERN.match(message)
    if not match:
        return None

    commit_type = match.group("type").lower()
    if commit_type not in COMMIT_TYPES:
        return None

    return Commit(
        sha="",  # Not needed for changelog
        type=commit_type,
        scope=match.group("scope"),
        description=match.group("desc").strip(),
        raw=message,
    )


def generate_changelog(commits: list[str], version: str) -> str:
    """Generate markdown changelog from commit messages."""
    # Parse and classify commits
    entries: dict[str, ChangelogEntry] = {}
    uncategorized: list[Commit] = []

    for raw_msg in commits:
        commit = parse_commit(raw_msg)
        if commit is None:
            continue

        section = COMMIT_TYPES.get(commit.type)
        if section is None:
            continue

        if section not in entries:
            entries[section] = ChangelogEntry(title=section)
        entries[section].commits.append(commit)

    if not entries:
        return f"## {version}\n\n_No significant changes._\n"

    # Build markdown
    lines = [f"## {version}\n"]

    # Preferred section order
    section_order = [
        "Features",
        "Bug Fixes",
        "Performance",
        "Refactoring",
        "Documentation",
    ]

    for section_name in section_order:
        if section_name not in entries:
            continue
        entry = entries[section_name]
        lines.append(f"### {section_name}\n")
        for commit in entry.commits:
            scope_str = f"**{commit.scope}:** " if commit.scope else ""
            lines.append(f"- {scope_str}{commit.description}")
        lines.append("")

    # Any other sections
    for section_name, entry in entries.items():
        if section_name in section_order:
            continue
        lines.append(f"### {section_name}\n")
        for commit in entry.commits:
            scope_str = f"**{commit.scope}:** " if commit.scope else ""
            lines.append(f"- {scope_str}{commit.description}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG from conventional commits"
    )
    parser.add_argument(
        "skill_id",
        nargs="?",
        help="Skill ID (for context)",
    )
    parser.add_argument(
        "from_tag",
        nargs="?",
        help="Starting git tag/reference",
    )
    parser.add_argument(
        "to_tag",
        nargs="?",
        default="HEAD",
        help="Ending git tag/reference (default: HEAD)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview uncommitted changes",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write to file instead of stdout",
    )
    args = parser.parse_args()

    if args.preview:
        # Show commits since last tag
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                check=True,
                cwd=REPO_ROOT,
            )
            last_tag = result.stdout.strip()
            commits_raw = get_commits_between(last_tag, "HEAD")
            version = "Unreleased"
        except subprocess.CalledProcessError:
            # No tags yet, use all commits
            result = subprocess.run(
                ["git", "log", "--format=%s"],
                capture_output=True,
                text=True,
                check=True,
                cwd=REPO_ROOT,
            )
            commits_raw = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
            version = "Unreleased"
    else:
        if not args.from_tag:
            parser.error("from_tag required when not using --preview")
        commits_raw = get_commits_between(args.from_tag, args.to_tag)
        # Extract version from to_tag (e.g. "pdf_document-v1.1.0" -> "1.1.0")
        version = args.to_tag
        if "-v" in version:
            version = version.split("-v", 1)[1]
        elif version.startswith("v"):
            version = version[1:]

    changelog = generate_changelog(commits_raw, version)

    if args.output:
        args.output.write_text(changelog, encoding="utf-8")
        print(f"Written to: {args.output}")
    else:
        print(changelog)

    return 0


if __name__ == "__main__":
    sys.exit(main())