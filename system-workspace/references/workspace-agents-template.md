# Workspace AGENTS.md Template

Save this file as `AGENTS.md` in the workspace root. Also create a `CLAUDE.md` containing only `@agents.md` so that Claude Code imports this file automatically. Follow this format exactly.

## Purpose

The workspace AGENTS.md exists only to capture what is true ACROSS repos. Each repo has its own AGENTS.md with stack, structure, commands, conventions, and known issues. This file does not repeat any of that. It answers one question: how do these repos relate?

## Required sections

The file must contain exactly four `##` sections in this order:

1. `## Repos` -- One line per repo: name and what it does (from its "What this is" section). Note any repos listed in workspace.json that have no AGENTS.md.
2. `## Cross-repo contracts` -- What flows between repos. For each contract: the source repo, the consuming repo, what is shared (types, API endpoints, event schemas, shared infra), and the file path on each side. Derive strictly from each repo's "Cross-repo dependencies" section and "What this is" section. If no cross-repo dependencies exist, state: "No cross-repo dependencies declared yet."
3. `## Shared conventions` -- Conventions that appear in two or more repos. One line each. Do not include conventions unique to a single repo.
4. `## Do not` -- Workspace-wide constraints that apply across all repos.

The top-level heading (`#`) is the workspace or system name.

## What NOT to include

- Per-repo details (stack, structure, commands, module guides) -- those belong in each repo's own AGENTS.md
- Roadmap content -- that belongs in the workspace ROADMAP.md
- Speculative content about future integrations
- Progress tracking or session notes

## Line budget

Keep the entire file under 100 lines. If cross-repo contracts push past this, the repos need to consolidate their contract documentation, not expand this file.

## Complete example

```markdown
# Acme Platform

## Repos

- **acme-api** -- REST API serving the core product. Node.js/Express, owns the database.
- **acme-web** -- React frontend consuming acme-api.
- **acme-jobs** -- Background job runner for async work (email, reports, data sync).
- **acme-shared** -- Shared TypeScript types and validation schemas, published as an internal package.

## Cross-repo contracts

- **acme-shared → acme-api, acme-web, acme-jobs**: TypeScript types and Zod schemas for all API request/response shapes. Source: `acme-shared/src/schemas/`. Consumed via `@acme/shared` package import.
- **acme-api → acme-web**: REST endpoints. Contract defined in `acme-api/src/routes/` (Express route handlers). No formal OpenAPI spec yet. **[INFERRED]**
- **acme-api → acme-jobs**: Job payloads enqueued via BullMQ. Schema in `acme-shared/src/schemas/jobs.ts`. Queue names in `acme-api/src/jobs/queues.ts`.

## Shared conventions

- All repos use Vitest for testing
- All repos use date-fns for date handling, not native Date
- ESLint with the same shared config (`@acme/eslint-config`)
- Environment variables for all secrets, never committed

## Do not

- Do not duplicate types across repos -- single source of truth in acme-shared
- Do not add direct database access outside acme-api -- all data access goes through the API
- Do not modify job payload schemas without updating both acme-api (producer) and acme-jobs (consumer)
```
