#!/usr/bin/env python3
"""Generate a catalog entry JSON for a PELDRUN skill package.

The generated entry is compatible with PELDRUN's skill catalog schema
and includes the SHA-256 checksum of the ZIP for supply-chain integrity.

Usage:
    python scripts/generate_catalog_entry.py \\
        --skill <skill_id> \\
        --zip <path_to_zip> \\
        --download-url <url> \\
        --repo <repository_url>

    # Auto-detect skill and compute download URL from GitHub:
    python scripts/generate_catalog_entry.py \\
        --skill pdf_document \\
        --github-owner peldrunai \\
        --github-repo peldrun-office-skills

Output:
    dist/<skill_id>-catalog-entry.json

The entry can be:
    - Merged into the main catalog via scripts/merge_catalog_entry.py
    - Imported automatically via the peldrun-skill-catalog import workflow
    - Attached to a GitHub Release for manual catalog updates

Exit codes:
    0 - Success
    1 - Generation failed
    2 - Skill or ZIP not found
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
DIST_DIR = REPO_ROOT / "dist"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


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


def load_manifest(skill_path: Path) -> dict[str, Any]:
    """Load and return the skill's manifest."""
    manifest_path = skill_path / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_catalog_entry(
    manifest: dict[str, Any],
    zip_path: Path,
    download_url: str,
    repo_url: str,
) -> dict[str, Any]:
    """Build a catalog entry from manifest data."""
    skill_id = manifest["id"]
    version = manifest["version"]

    # Compute SHA-256 of the ZIP
    checksum = compute_sha256(zip_path)

    # Determine if it's a router skill
    sub_skills = manifest.get("sub_skills", [])
    has_sub_skills = len(sub_skills) > 0
    sub_skills_count = len(sub_skills)

    # Build the entry (following PELDRUN catalog schema)
    entry: dict[str, Any] = {
        "id": skill_id,
        "name": manifest.get("name", skill_id),
        "version": version,
        "description": manifest.get("description", ""),
        "download_url": download_url,
        "checksum_sha256": checksum,
        "has_sub_skills": has_sub_skills,
        "sub_skills_count": sub_skills_count,
        "trust": manifest.get("trust", "community"),
        "stability": manifest.get("stability", "stable"),
        "release_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    # Optional fields
    if "display_name" in manifest:
        entry["display_name"] = manifest["display_name"]

    if "short_description" in manifest:
        entry["short_description"] = manifest["short_description"]

    if "store_description" in manifest:
        entry["store_description"] = manifest["store_description"]

    if "icon_svg" in manifest:
        entry["icon"] = manifest["icon_svg"]
        entry["icon_type"] = "svg"
    elif "icon" in manifest:
        entry["icon"] = manifest["icon"]
        entry["icon_type"] = "name"

    if "tags" in manifest:
        entry["tags"] = manifest["tags"]

    if "license" in manifest:
        entry["license"] = manifest["license"]

    # Author info
    author = manifest.get("author")
    if author:
        entry["author"] = author.get("name")
        entry["author_url"] = author.get("url")

        entry["developer"] = {
            "name": author.get("name"),
            "url": author.get("url"),
        }
        if author.get("email"):
            entry["developer"]["email"] = author["email"]

    # URLs
    if repo_url:
        entry["repository_url"] = repo_url
        entry["homepage"] = manifest.get("homepage", repo_url)

    if "docs_url" in manifest:
        entry["docs_url"] = manifest["docs_url"]

    if "brand_color" in manifest:
        entry["brand_color"] = manifest["brand_color"]

    # Deprecation info
    if manifest.get("deprecated"):
        entry["stability"] = "deprecated"
        if "deprecation_message" in manifest:
            entry["deprecation_message"] = manifest["deprecation_message"]

    # Install warnings
    if manifest.get("sub_skills"):
        entry["install_warnings"] = [
            "This skill uses Progressive Disclosure with sub-skills."
        ]

    return entry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a PELDRUN skill catalog entry"
    )
    parser.add_argument(
        "--skill",
        required=True,
        help="Skill ID to generate entry for",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        help="Path to the built ZIP file (auto-detected if omitted)",
    )
    parser.add_argument(
        "--download-url",
        help="Download URL for the ZIP (required if not using --github-owner)",
    )
    parser.add_argument(
        "--github-owner",
        help="GitHub repository owner (auto-computes download URL)",
    )
    parser.add_argument(
        "--github-repo",
        help="GitHub repository name (auto-computes download URL)",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="Repository URL for repository_url field",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path (default: dist/<skill_id>-catalog-entry.json)",
    )
    args = parser.parse_args()

    # Find skill
    skill_path = find_skill_path(args.skill)
    if skill_path is None:
        print(f"Error: Skill '{args.skill}' not found")
        return 2

    # Load manifest
    manifest = load_manifest(skill_path)
    version = manifest["version"]

    # Determine ZIP path
    if args.zip:
        zip_path = args.zip
    else:
        zip_name = f"{args.skill}-{version}.zip"
        zip_path = DIST_DIR / zip_name

    if not zip_path.is_file():
        print(f"Error: ZIP not found at {zip_path}")
        print(f"Please build the package first: python scripts/build_package.py {args.skill}")
        return 2

    # Determine download URL
    if args.github_owner and args.github_repo:
        zip_name = zip_path.name
        download_url = (
            f"https://github.com/{args.github_owner}/{args.github_repo}"
            f"/releases/download/{args.skill}-v{version}/{zip_name}"
        )
    elif args.download_url:
        download_url = args.download_url
    else:
        print("Error: Provide either --download-url or --github-owner/--github-repo")
        return 1

    # Build repository URL if not provided
    repo_url = args.repo
    if not repo_url and args.github_owner and args.github_repo:
        repo_url = f"https://github.com/{args.github_owner}/{args.github_repo}"

    # Generate entry
    print(f"Generating catalog entry for: {args.skill} v{version}")
    print(f"ZIP: {zip_path}")
    print(f"Download URL: {download_url}")

    entry = build_catalog_entry(manifest, zip_path, download_url, repo_url)

    # Write output
    output_path = args.output or (DIST_DIR / f"{args.skill}-catalog-entry.json")
    DIST_DIR.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(entry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nGenerated: {output_path}")
    print(f"SHA-256: {entry['checksum_sha256']}")
    if entry.get("has_sub_skills"):
        print(f"Sub-skills: {entry['sub_skills_count']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())