 # PELDRUN Skill Template

A fully automated template for building, validating, and releasing PELDRUN skill packages. Mirrors the CI/CD pipeline used by `peldrun-provider-cloudflare-ai`, adapted for skills with full support for simple skills, multi-skill repositories, and router skills with sub-skills.

## Features

- ✅ **Single-skill and multi-skill repositories** — one repo per skill, or many skills in one repo
- ✅ **Router skills with sub-skills** — Progressive Disclosure pattern fully supported
- ✅ **JSON Schema validation** — manifests validated against the official PELDRUN schema
- ✅ **Deterministic ZIP builds** — reproducible packages with forbidden-file filtering
- ✅ **Install-time verification** — mirrors exactly what PELDRUN performs at install
- ✅ **Automated releases** — tag-driven pipeline with GitHub Release artifacts
- ✅ **SHA-256 checksums** — supply-chain integrity for every package
- ✅ **Catalog entry generation** — ready for `peldrun-skill-catalog` auto-import
- ✅ **Conventional Commits changelog** — automatic CHANGELOG from git history
- ✅ **Semver versioning** — `update_version.py` bumps versions across the repo

## Quick Start

### 1. Create a new repository from this template

```bash
git clone <this-repo-url> my-skill-repo
cd my-skill-repo
```

### 2. Remove the example skill

```bash
rm -rf skills/_example
```

### 3. Create your first skill

**For a multi-skill repository:**

```bash
mkdir -p skills/my_skill
# Edit skills/my_skill/manifest.json
# Edit skills/my_skill/SKILL.md
```

**For a single-skill repository** (manifest at root):

```bash
# Edit manifest.json at repo root
# Edit SKILL.md at repo root
```

### 4. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install jsonschema==4.23.0 pyyaml==6.0.2
```

### 5. Validate locally

```bash
python scripts/validate_manifest.py my_skill
```

### 6. Build and verify

```bash
python scripts/build_package.py my_skill --verify
```

Output: `dist/my_skill-1.0.0.zip`

### 7. Release

```bash
# Bump version
python scripts/update_version.py my_skill patch

# Commit
git add -A
git commit -m "chore(release): my_skill v1.0.1"

# Tag (triggers automated release)
git tag -a my_skill-v1.0.1 -m "Release v1.0.1"
git push origin main
git push origin my_skill-v1.0.1
```

## Repository Layouts

### Single-Skill Repository

One skill per repository. Manifest at the root. Tag pattern: `v<version>`.

```
my-skill-repo/
├── manifest.json              # at root
├── SKILL.md
├── icon.svg                   # optional
├── references/                # optional
│   └── checklist.md
├── .github/workflows/
│   ├── validate.yml
│   └── release.yml
├── scripts/
│   ├── validate_manifest.py
│   ├── build_package.py
│   ├── verify_package.py
│   ├── generate_catalog_entry.py
│   ├── update_version.py
│   └── changelog.py
├── manifest.schema.json
├── .gitignore
├── .gitattributes
├── CHANGELOG.md
├── LICENSE
└── README.md
```

**Tag example:**

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### Multi-Skill Repository

Many skills in one repository. Each skill lives under `skills/<id>/`. Tag pattern: `<skill_id>-v<version>`.

```
my-skills-repo/
├── skills/
│   ├── skill_a/
│   │   ├── manifest.json
│   │   ├── SKILL.md
│   │   └── icon.svg
│   ├── skill_b/
│   │   ├── manifest.json
│   │   ├── SKILL.md
│   │   └── sub_skills/
│   │       ├── sub_x/
│   │       │   └── SKILL.md
│   │       └── sub_y/
│   │           └── SKILL.md
│   └── _example/              # template (auto-skipped)
│       ├── manifest.json
│       ├── SKILL.md
│       └── sub_skills/
│           └── example_sub/
│               └── SKILL.md
├── .github/workflows/
├── scripts/
├── manifest.schema.json
└── ...
```

**Tag examples:**

```bash
git tag -a skill_a-v1.0.0 -m "Release skill_a v1.0.0"
git push origin skill_a-v1.0.0

git tag -a skill_b-v2.1.0 -m "Release skill_b v2.1.0"
git push origin skill_b-v2.1.0
```

## Available Scripts

All scripts live in `scripts/` and use only the Python standard library plus `jsonschema` and `pyyaml`.

### `validate_manifest.py`

Validate one or all skills against the official JSON Schema.

```bash
python scripts/validate_manifest.py my_skill      # one skill
python scripts/validate_manifest.py --all         # all skills
python scripts/validate_manifest.py path/to/manifest.json
```

**Checks performed:**

- JSON parsing
- JSON Schema validation
- Semantic checks (sub-skill files exist, no duplicate IDs)
- Frontmatter validation in SKILL.md files
- Forbidden files detection (.exe, .pyc, etc.)
- Package size and file count limits

### `build_package.py`

Build a deterministic ZIP package.

```bash
python scripts/build_package.py my_skill            # build one
python scripts/build_package.py --all               # build all
python scripts/build_package.py my_skill --verify   # build and verify
```

**Output:** `dist/<skill_id>-<version>.zip`

The ZIP contains files at its root (no wrapping directory), matching PELDRUN's install-time expectations.

### `verify_package.py`

Verify a built ZIP against PELDRUN's install-time requirements.

```bash
python scripts/verify_package.py dist/my_skill-1.0.0.zip
```

**Checks performed:**

- ZIP integrity
- manifest.json at root
- Schema validation
- Sub-skill file presence
- Path traversal detection
- Forbidden files
- Size limits

### `generate_catalog_entry.py`

Generate a catalog entry JSON with SHA-256 checksum for the PELDRUN skill catalog.

```bash
python scripts/generate_catalog_entry.py \
    --skill my_skill \
    --zip dist/my_skill-1.0.0.zip \
    --download-url "https://github.com/<owner>/<repo>/releases/download/my_skill-v1.0.0/my_skill-1.0.0.zip" \
    --repo "https://github.com/<owner>/<repo>"

# Or auto-compute from GitHub:
python scripts/generate_catalog_entry.py \
    --skill my_skill \
    --github-owner myorg \
    --github-repo my-skill-repo
```

**Output:** `dist/<skill_id>-catalog-entry.json`

The generated entry can be:

- Merged into `peldrun-skill-catalog` via the import workflow
- Attached to a GitHub Release
- Used for manual catalog updates

### `update_version.py`

Bump the semantic version in manifest.json.

```bash
python scripts/update_version.py my_skill patch   # 1.0.0 -> 1.0.1
python scripts/update_version.py my_skill minor   # 1.0.0 -> 1.1.0
python scripts/update_version.py my_skill major   # 1.0.0 -> 2.0.0
python scripts/update_version.py my_skill 1.2.3   # exact version
python scripts/update_version.py --all patch      # bump all skills
```

### `changelog.py`

Generate a CHANGELOG section from git commits using Conventional Commits.

```bash
python scripts/changelog.py my_skill my_skill-v1.0.0 my_skill-v1.1.0
python scripts/changelog.py --preview my_skill    # uncommitted changes
python scripts/changelog.py my_skill v1.0.0 HEAD --output CHANGELOG-section.md
```

**Commit classification:**

| Type | Section |
|------|---------|
| `feat(scope):` | Features |
| `fix(scope):` | Bug Fixes |
| `docs:` | Documentation |
| `perf:` | Performance |
| `refactor:` | Refactoring |
| `chore:`, `test:`, `ci:`, `style:` | Skipped |

## Router Skills (Sub-Skills)

Router skills use the **Progressive Disclosure** pattern to split a large skill into a parent router plus specialized sub-skills. The model loads only the sub-skill it needs for the current task.

### Directory Structure

```
skills/my_router/
├── manifest.json              # declares sub_skills array
├── SKILL.md                   # router body (keep short, < 2 KiB)
├── icon.svg                   # optional
└── sub_skills/
    ├── aspect_a/
    │   └── SKILL.md
    └── aspect_b/
        └── SKILL.md
```

### Manifest Declaration

```json
{
  "schema_version": "1.0.0",
  "id": "my_router",
  "version": "1.0.0",
  "name": "My Router",
  "description": "Router skill with specialized sub-skills.",
  "execution": {
    "type": "instructions",
    "instructions_file": "SKILL.md"
  },
  "sub_skills": [
    {
      "id": "aspect_a",
      "description": "Handle aspect A of the task.",
      "triggers": ["a", "alpha", "aspect-a"],
      "instructions_file": "sub_skills/aspect_a/SKILL.md",
      "capabilities": { "exclusive": false }
    },
    {
      "id": "aspect_b",
      "description": "Handle aspect B of the task.",
      "triggers": ["b", "beta", "aspect-b"],
      "instructions_file": "sub_skills/aspect_b/SKILL.md",
      "capabilities": { "exclusive": false }
    }
  ]
}
```

### Router Body (SKILL.md)

```markdown
---
name: my_router
description: Router skill with specialized sub-skills.
---

# My Router

You have access to two specialized sub-skills. Select the single most relevant one.

## Sub-Skills

### 1. aspect_a
Use when: The user asks about A-related tasks.

### 2. aspect_b
Use when: The user asks about B-related tasks.

## How to Activate

Call `load_sub_skill(parent_id="my_router", sub_skill_id="<chosen>")`.

Prefer ONE sub-skill per turn unless the request explicitly spans multiple aspects.
```

### Sub-Skill Body (sub_skills/aspect_a/SKILL.md)

```markdown
---
name: aspect_a
description: Handle aspect A of the task.
---

# Aspect A

You are handling aspect A...

## Instructions

1. First step
2. Second step

## Output Format

...
```

### Sub-Skill Limits

- Maximum **50 sub-skills** per router
- Router body: keep under **2 KiB**
- Each sub-skill body: keep under **8 KiB**
- Sub-skill IDs must be unique within the parent
- `instructions_file` must start with `sub_skills/` and end with `.md`
- No `..` segments in the path (containment enforced)

## manifest.json Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Semver. Major must be `1`. Example: `"1.0.0"` |
| `id` | string | Lowercase, 3-64 chars, `[a-z0-9_]` |
| `version` | string | Semver. Example: `"1.0.0"` |
| `name` | string | Human-readable name (1-120 chars) |
| `description` | string | Short description (1-500 chars) |
| `execution` | object | `{ "type": "instructions", "instructions_file": "SKILL.md" }` |

### Common Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | UI override for `name` |
| `short_description` | string | Shorter variant for store card |
| `store_description` | string | Longer markdown for details drawer |
| `tags` | array | Max 20, each ≤32 chars. Indexed by BM25 |
| `author` | object | `{ "name", "url", "email" }` |
| `trust` | enum | `"verified"` / `"community"` / `"unverified"` |
| `license` | string | SPDX identifier or `"proprietary"` |
| `stability` | enum | `"experimental"` / `"beta"` / `"stable"` / `"deprecated"` |
| `capabilities` | object | `{ "chat_invocable", "agent_assignable", "workflow_node" }` |
| `icon_svg` | string | Inline SVG (max 32 KiB, sanitized) |
| `icon` | string | Relative path to SVG file |
| `brand_color` | string | Hex color, e.g. `"#8B5CF6"` |
| `user_editable` | boolean | Allow UI editing of SKILL.md |
| `sub_skills` | array | Router sub-skill declarations |

### Execution Block

```json
"execution": {
  "type": "instructions",
  "instructions_file": "SKILL.md",
  "references_dir": "references"
}
```

Only `"instructions"` is supported. Custom handlers are not executed in this release.

### Capabilities Block

```json
"capabilities": {
  "chat_invocable": true,
  "agent_assignable": true,
  "workflow_node": false
}
```

| Flag | Effect |
|------|--------|
| `chat_invocable: true` | Appears in `/` typeahead menu |
| `agent_assignable: true` | Can be assigned to agents |
| `workflow_node: true` | Reserved for future Workflow integration |

### Compatibility Block

```json
"compatibility": {
  "peldrun_min_version": "0.2.0",
  "peldrun_max_version": "1.0.0"
}
```

Both fields optional. Omitting either leaves that end unbounded.

### Limits Block

```json
"limits": {
  "max_instructions_bytes": 262144
}
```

Default 256 KiB. Hard ceiling 1 MiB.

## SKILL.md Format

`SKILL.md` is a Markdown document with a **YAML frontmatter block** at the top.

### Structure

```markdown
---
name: my_skill
description: A short one-line description.
---

# My Skill

## Instructions

1. First step
2. Second step
3. Report findings clearly

## Output Format

...
```

### Frontmatter Requirements

- Must start with `---` on the first line
- Must contain a closing `---` on its own line
- Must parse as a YAML mapping
- Supported fields: `name`, `description`, `license`, `compatibility`

### Body Guidelines

- Be specific and actionable
- Structure with `##` and `###` headers
- Include an output format
- Keep simple skills under **8 KiB**
- Keep router bodies under **2 KiB**
- Never include secrets, API keys, or personal data

## CI/CD Workflows

### `validate.yml` — Continuous Integration

Triggers on push to `main` and pull requests. Validates every skill in the repository.

**Steps:**

1. Verify required files exist
2. Install `jsonschema` and `pyyaml`
3. Validate all manifests
4. Build all skill packages
5. Verify all built packages
6. Generate summary

### `release.yml` — Automated Release

Triggers on tag push matching `v*` or `*-v*`.

**Steps:**

1. Parse tag to determine skill ID and version
2. Verify tag version matches manifest.json
3. Validate manifest
4. Build ZIP package
5. Generate catalog entry with SHA-256
6. Create GitHub Release with ZIP + catalog entry attached

**Tag patterns:**

| Pattern | Repo Type | Example |
|---------|-----------|---------|
| `v<major>.<minor>.<patch>` | Single-skill | `v1.0.0` |
| `<skill_id>-v<major>.<minor>.<patch>` | Multi-skill | `pdf_document-v1.2.3` |

## Local Development

### Setup

```bash
git clone <repo-url>
cd <repo>
python -m venv .venv
source .venv/bin/activate
pip install jsonschema==4.23.0 pyyaml==6.0.2
```

### Validation Loop

```bash
# Validate one skill
python scripts/validate_manifest.py my_skill

# Validate all
python scripts/validate_manifest.py --all

# Build and verify
python scripts/build_package.py my_skill --verify

# Generate catalog entry (for testing)
python scripts/generate_catalog_entry.py \
    --skill my_skill \
    --download-url "https://example.com/my_skill-1.0.0.zip"
```

### Preview Changelog

```bash
python scripts/changelog.py --preview my_skill
```

## Release Workflow

### Standard Release

```bash
# 1. Make changes and commit with Conventional Commits
git add -A
git commit -m "feat(my_skill): add new output format"
git commit -m "fix(my_skill): correct frontmatter validation"

# 2. Bump version
python scripts/update_version.py my_skill patch

# 3. Review changes
git diff

# 4. Commit version bump
git add -A
git commit -m "chore(release): my_skill v1.0.1"

# 5. Tag and push
git tag -a my_skill-v1.0.1 -m "Release v1.0.1"
git push origin main
git push origin my_skill-v1.0.1
```

The `release.yml` workflow automatically:

- Builds the ZIP package
- Generates the catalog entry with SHA-256
- Creates a GitHub Release
- Attaches both artifacts to the release

### Version Bump Guide

| Change | Bump |
|--------|------|
| Typo fixes, small instruction tweaks | `patch` |
| New sections, non-breaking behavior changes | `minor` |
| Adding sub-skills | `minor` |
| Removing or renaming a sub-skill | `major` |
| Structurally different output | `major` |

## Conventional Commits

This template uses Conventional Commits for automatic changelog generation.

### Format

```
type(scope): description
```

### Types

| Type | Changelog Section |
|------|-------------------|
| `feat` | Features |
| `fix` | Bug Fixes |
| `docs` | Documentation |
| `perf` | Performance |
| `refactor` | Refactoring |
| `chore` | _(skipped)_ |
| `test` | _(skipped)_ |
| `ci` | _(skipped)_ |
| `style` | _(skipped)_ |

### Examples

```
feat(code_review): add severity levels to output format
fix(security_audit): correct SQL injection detection pattern
docs: clarify installation steps in README
perf(model_discovery): cache results per connection
refactor(adapter): simplify error handling
```

## Catalog Integration

Each release generates a `catalog-entry.json` compatible with `peldrun-skill-catalog`.

### Automatic Import

1. Copy the `catalog-entry.json` URL from the GitHub Release
2. In `peldrun-skill-catalog`, trigger the "Import Skill to Catalog" workflow
3. Paste the URL
4. A PR is created automatically with the new skill merged into `catalog.json`

### Manual Import

```bash
# Generate entry locally
python scripts/generate_catalog_entry.py \
    --skill my_skill \
    --github-owner myorg \
    --github-repo my-skill-repo

# The entry is in dist/my_skill-catalog-entry.json
```

### Entry Structure

```json
{
  "id": "my_skill",
  "name": "My Skill",
  "version": "1.0.0",
  "description": "A short one-line description.",
  "download_url": "https://github.com/.../my_skill-1.0.0.zip",
  "checksum_sha256": "abc123...",
  "has_sub_skills": false,
  "sub_skills_count": 0,
  "trust": "community",
  "stability": "stable",
  "release_date": "2026-11-25",
  "tags": ["example", "demo"],
  "developer": {
    "name": "PELDRUN Community",
    "url": "https://github.com/peldrunai"
  }
}
```

## Package Safety

### Forbidden Files

The following are automatically excluded from ZIP packages and rejected at install time:

- Executables: `.exe`, `.dll`, `.so`, `.dylib`
- Bytecode: `.pyc`, `.pyo`, `.pyd`
- VCS metadata: `.git/`, `.svn/`, `.hg/`
- Environment folders: `.venv/`, `venv/`, `node_modules/`
- Cache directories: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`
- Symbolic links

### Size Limits

| Limit | Value |
|-------|-------|
| Individual file | 5 MB |
| Total package (uncompressed) | 100 MB |
| Maximum files | 500 |
| Maximum path depth | 10 segments |
| Instructions file | 256 KiB (configurable up to 1 MiB) |

### Security

- Path traversal attacks are detected and rejected
- All paths are normalized and containment-checked
- SVG icons are sanitized (no `<script>`, event handlers, `javascript:` URIs)
- ZIP bombs are rejected via size limits

## Troubleshooting

### `manifest.json is not valid JSON`

Check for trailing commas, unquoted keys, or single quotes. Use a JSON linter:

```bash
python -c "import json; json.load(open('manifest.json'))"
```

### `Schema validation failed`

The error message includes the failing field path. Common issues:

| Error | Fix |
|-------|-----|
| `id must match ^[a-z0-9][a-z0-9_]{2,63}$` | Use lowercase, digits, underscores. Start with letter/digit. ≥3 chars. |
| `schema_version unsupported major` | Use a `1.x.y` string |
| `missing required field: execution` | Add the `execution` object |
| `execution.type must be 'instructions'` | Only `"instructions"` is accepted |

### `Instructions file not found`

The file named in `execution.instructions_file` (default `SKILL.md`) does not exist at the package root.

### `sub_skills[N].instructions_file must start with 'sub_skills/'`

Sub-skill files must live under the `sub_skills/` directory.

### `Duplicate sub_skill id`

Two sub-skills in the same parent have the same `id`. Make them unique.

### `File exceeds 5 MB limit`

Reduce file size or split into multiple files. Check for accidentally included assets.

### `Path traversal detected`

A file path contains `..`. Remove traversal segments.

### Release workflow fails with version mismatch

The tag version must match `manifest.json["version"]` exactly:

```bash
# Check manifest version
python -c "import json; print(json.load(open('manifest.json'))['version'])"

# Create matching tag
git tag -a my_skill-v1.0.0 -m "Release v1.0.0"
```

### GitHub Release not created

Ensure the repository has Actions enabled and the `GITHUB_TOKEN` has `contents: write` permission (default for the token).

## Contributing

### Adding a New Skill

1. Create `skills/<skill_id>/manifest.json` and `SKILL.md`
2. Run `python scripts/validate_manifest.py <skill_id>`
3. Run `python scripts/build_package.py <skill_id> --verify`
4. Open a pull request

### Modifying an Existing Skill

1. Edit the skill files
2. Bump the version: `python scripts/update_version.py <skill_id> patch`
3. Commit with a descriptive message
4. Tag and push to trigger a release

### Reporting Issues

Open an issue with:

- Skill ID and version
- Steps to reproduce
- Expected vs actual behavior
- Relevant error messages

## Security

Skills are **instructional only** — they never execute code, access the network, or write to the filesystem beyond reading their own package files.

The install pipeline enforces:

- JSON Schema validation
- Path containment (no traversal outside the package)
- Forbidden file type rejection
- Size limits
- SVG sanitization for icons

The catalog uses SHA-256 checksums to prevent supply-chain attacks: a compromised catalog cannot cause installation of arbitrary code because the checksum must match the actual ZIP bytes.

## License

MIT — see [LICENSE](LICENSE).

## Related Repositories

- [peldrun](https://github.com/peldrun/peldrun) — The main PELDRUN application
- [peldrun-skill-catalog](https://github.com/peldrunai/peldrun-skill-catalog) — Official skill catalog
- [peldrun-office-skills](https://github.com/peldrunai/peldrun-office-skills) — Example multi-skill repository
- [peldrun-provider-cloudflare-ai](https://github.com/peldrunai/peldrun-provider-cloudflare-ai) — Reference provider package with  