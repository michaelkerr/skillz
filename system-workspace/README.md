# System Workspace

A Claude Code plugin for generating workspace-level context across multiple repos. Reads each repo's AGENTS.md and produces a thin workspace AGENTS.md capturing only cross-cutting concerns: shared conventions, cross-repo contracts, and workspace-wide constraints.

## What it does

When working across multiple repos, each repo's own AGENTS.md covers its stack, structure, and conventions. But nothing captures how the repos relate to each other. This skill fills that gap.

It reads the per-repo AGENTS.md and ROADMAP.md files and produces:
1. **workspace.json** — manifest listing repos in the workspace (created interactively if missing)
2. **AGENTS.md** — workspace-level context with four sections: Repos, Cross-repo contracts, Shared conventions, Do not
3. **ROADMAP.md** — cross-repo roadmap with NOW/NEXT/LATER/PARKED buckets for work spanning multiple repos
4. **CLAUDE.md** — import stub (`@agents.md`)

## When to use

- A workspace directory coordinates two or more repos, each with its own AGENTS.md
- Cross-repo work is happening and the AI needs to understand how repos relate
- A new repo has been added to the workspace and context needs refreshing

Do **not** use for single-repo projects. Each repo's own AGENTS.md is sufficient on its own.

## Included files

| File | Purpose |
|------|---------|
| `skills/system-workspace/SKILL.md` | Skill instructions |
| `references/workspace-schema.json` | JSON schema for workspace.json |
| `references/sample-workspace.json` | Example workspace.json |
| `references/workspace-agents-template.md` | Template and format spec for workspace AGENTS.md |
| `references/workspace-roadmap-template.md` | Template and format spec for workspace ROADMAP.md |
| `references/eval_workspace_quality.py` | Validates structural correctness of generated artifacts |

## Eval script

Run output quality checks after generating artifacts:

```bash
python references/eval_workspace_quality.py /path/to/workspace
```

Supports `--format json` for structured output.
