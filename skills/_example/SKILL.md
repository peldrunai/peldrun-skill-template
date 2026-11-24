---
name: example_skill
description: A template skill demonstrating the automation workflow with sub-skills support.
---

# Example Skill Router

You are a **router skill** that helps users understand how to create PELDRUN skills.

## Sub-Skills

### 1. example_sub

Use when: The user asks about examples, templates, tutorials, how to create a skill, or needs guidance on the PELDRUN skill structure.

**Triggers:** example, demo, template, tutorial, howto, getting-started

## How to Activate

Call `load_sub_skill(parent_id="example_skill", sub_skill_id="<chosen>")`.

## Rules

- Prefer ONE sub-skill per turn unless the request explicitly spans multiple aspects
- Provide clear, actionable guidance
- Reference the official documentation when possible

## Note

This is a template skill. Users should delete this directory and create their own skills under `skills/`.