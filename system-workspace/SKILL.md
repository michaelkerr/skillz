---
name: system-workspace
description: Generate workspace-level context for a multi-repo system. Reads each repo's AGENTS.md (listed in workspace.json), then produces a workspace AGENTS.md capturing only what is true across repos -- shared conventions, cross-repo contracts, and workspace-wide constraints. Use when setting up or refreshing context for a workspace that coordinates multiple repos. Do NOT use for single-repo projects.
---

# System Workspace

Generate workspace-level context that ties multiple repos together. Each repo already has its own AGENTS.md (produced by product-discovery or product-evolution). This skill reads those per-repo files and produces a thin workspace-level AGENTS.md capturing only cross-cutting concerns.

## When to use this

- A workspace directory coordinates two or more repos, each with its own AGENTS.md
- Cross-repo work is happening and the AI needs to understand how repos relate
- A new repo has been added to the workspace and context needs refreshing

Do not use this for single-repo projects. Each repo's own AGENTS.md is sufficient on its own.

## Phase 1: Read or Create the Manifest

Read `references/workspace-schema.json` for the expected format.

Check whether `workspace.json` exists in the current directory.

### If workspace.json exists

Read it. Validate that it matches the schema (has a `repos` array with at least two entries, each with `path` and `name`). If invalid, tell the user what's wrong and fix it with them before continuing.

### If workspace.json does not exist

Walk the user through creating one:

1. Scan the parent directory for sibling directories that look like repos (contain a `.git` directory, `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, or similar project markers). Present the list as candidates.
2. Ask the user which of these repos belong to this workspace. They may also add paths not in the scan results.
3. For each selected repo, derive a short `name` from the directory name and compute the `path` relative to this workspace directory (e.g., `../my-api`).
4. Confirm the final list with the user before writing.
5. Write `workspace.json` to the current directory matching the schema.

If there are fewer than two repos, stop. A workspace-level context file is not useful for a single repo.

## Phase 2: Read Per-Repo Context

For each entry in `workspace.json`:
1. Resolve the `path` relative to this directory
2. Read `AGENTS.md` at that path
3. If no AGENTS.md exists, note the repo as missing context and continue

If fewer than two repos have an AGENTS.md, stop. A workspace-level context file is not useful until at least two repos have their own context established.

## Phase 3: Generate Workspace Context

Produce two files in this directory:

### 3.1 AGENTS.md

Read `references/workspace-agents-template.md` for the exact format. Follow it precisely.

The workspace AGENTS.md must contain exactly four `##` sections:

1. `## Repos` -- One-line description of each repo and what it does, derived from its "What this is" section. Note any repos in the manifest that had no AGENTS.md.
2. `## Cross-repo contracts` -- What flows between repos: shared types, API contracts, shared infra, event schemas. Name the source repo, the consuming repo, and the file path to the contract on each side. Derive this strictly from each repo's "Cross-repo dependencies" section (if present) and from the "What this is" sections. If no cross-repo dependencies exist yet, state that explicitly.
3. `## Shared conventions` -- Only conventions that appear in two or more repo AGENTS.md files. Do not restate conventions unique to one repo.
4. `## Do not` -- Workspace-wide constraints.

Rules:
- Base every claim on the actual AGENTS.md files. Do not invent conventions, contracts, or commands.
- Do not restate content that already lives in a repo's own AGENTS.md. The workspace file captures only what is true ACROSS repos.
- Keep the file under 100 lines. Terse and factual.
- Flag anything inferred rather than confirmed from the files with **[INFERRED]**.

### 3.2 CLAUDE.md

Create a CLAUDE.md in this directory containing only:

```
@agents.md
```

### Verifying all outputs

After writing both files, run the output quality eval against this directory:

```
python ${CLAUDE_PLUGIN_ROOT}/references/eval_workspace_quality.py <workspace-dir>
```

Fix any FAIL findings. Present the results to the user only after the eval passes clean.

## Phase 4: Present and Confirm

Present the workspace AGENTS.md to the user. Highlight:

- Which repos were included and which were missing context
- Cross-repo contracts found (or the absence of them)
- Shared conventions extracted
- Any claims marked **[INFERRED]**

Ask: "Does this match how these repos relate? Anything wrong or missing?"

## Staying Current

Re-run this skill when:

- A new repo is added to workspace.json
- A repo's AGENTS.md changes significantly (new cross-repo dependencies, changed conventions)
- Cross-repo contracts change (new shared types, API changes)

The workspace AGENTS.md should never be more than one significant change out of date.
