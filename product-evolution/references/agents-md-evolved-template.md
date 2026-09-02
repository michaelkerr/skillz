# Evolved AGENTS.md Template

Save this file as `AGENTS.md` in the project root, replacing the startup-phase version. Also ensure a `CLAUDE.md` exists in the project root containing only `@agents.md` so that Claude Code imports this file automatically. Follow this format exactly.

## Purpose

At maturity, AGENTS.md carries more weight than the startup version. The project is no longer finding its patterns -- it has them. This file tells the AI what they are, where things live, and how to work without breaking what exists.

## Required sections

The file must contain exactly nine `##` sections in this order:

1. `## What this is` -- one paragraph reflecting the product's current state, not its original pitch.
2. `## Work protocol` -- references ROADMAP.md, defines the pick-and-work loop, regression safety, and artifact maintenance.
3. `## Tech stack` -- what is actually in use, from dependency manifests and code. Include versions for major dependencies. Note upgrade constraints.
4. `## Architecture overview` -- brief summary pointing to ARCHITECTURE.md for detail.
5. `## Project structure` -- more detailed than startup phase. Document every major directory and its purpose. Include naming conventions per directory.
6. `## Conventions` -- expanded and more prescriptive. Group by category. Each convention includes a brief "because" rationale.
7. `## Module guide` -- for codebases too large to read entirely, tells the AI where to look. Lists every major functional area with its entry point and key files.
8. `## Do not` -- more entries than at startup. Includes lessons learned from things that went wrong.
9. `## Known issues` -- things that are broken or fragile but not yet fixed. Prevents the AI from investigating known problems.

The top-level heading (`#`) is the project name.

## What NOT to include

- Product strategy, user personas, market analysis (these do not change AI behavior)
- Rationale paragraphs (keep entries to 1-2 lines)
- Speculative content ("we might later want to...", "eventually we'll...", "down the road")
- Progress tracking, status updates, or session notes (that belongs in ROADMAP.md)

## Complete example

```markdown
# SalesSync

## What this is

A dashboard that pre-computes daily Salesforce pipeline summaries so a 12-person sales team can run their daily standup and weekly reviews from live data instead of a manually assembled spreadsheet. Used daily by the sales manager and presented on-screen during standups.

## Work protocol

- The roadmap lives in ROADMAP.md. Read it at the start of every session.
- Pick a NOW item to work on. Items are not sequenced -- choose based on what is most needed.
- Before starting work on a NOW item:
  1. Run the full test suite. State the result count explicitly (e.g., "42 passed, 0 failed"). Do not start implementation if any test fails -- fix the failure first.
  2. Read the item's "Touches" field. Review those parts of the codebase to understand current state.
  3. Check DECISIONS.md for prior decisions that affect this work.
- While working:
  1. Write or update tests for every behavior you change or add. A feature without a test is not done.
  2. Follow the conventions below. If a situation is not covered, check how similar cases are handled elsewhere in the codebase and follow that pattern. If it is genuinely new, document the convention you choose.
  3. If work reveals a new risk, update the item's Risk field.
  4. If work uncovers tech debt or a bug unrelated to the current item, add it to ROADMAP.md in the appropriate bucket. Do not fix it now unless it blocks the current work.
- When work is done:
  1. Run the full test suite again. State the result count. Do not present work as complete if any test fails.
  2. Update ROADMAP.md: remove the item from NOW, update "What's built" if the product's capabilities changed.
  3. Promote an item from Next to NOW if the NOW bucket is thin.
  4. Update AGENTS.md if new conventions or patterns emerged.
  5. Update ARCHITECTURE.md if the system's structure changed.
  6. Log any significant decisions in DECISIONS.md.
- When the user starts a new session, read AGENTS.md, ROADMAP.md, and ARCHITECTURE.md before beginning work.

## Tech stack

- React 18 (Vite 5) for the frontend
- Node.js 20 + Express 4 backend for Salesforce API proxy
- SQLite 3 for caching fetched data locally
- Resend for transactional email (added in v2)
- Vitest for testing

## Architecture overview

Three-layer architecture: React frontend, Express API proxy, SQLite cache. Salesforce API is the sole external data source, fetched on a daily cron schedule. See ARCHITECTURE.md for component map and data flow.

## Project structure

- `/src/components/` -- React components, each in its own folder with co-located CSS module
- `/src/export/` -- CSV and PDF export logic
- `/src/email/` -- email templates as React components, send logic
- `/server/routes/` -- Express API routes, one file per resource
- `/server/salesforce/` -- Salesforce API client, data aggregation, schema mapping
- `/server/jobs/` -- Scheduled jobs (daily fetch, weekly email)
- `/tests/` -- mirrors src/ and server/ structure
- `/migrations/` -- SQLite schema migrations, numbered sequentially

## Conventions

- State management via useState/useReducer only, no external state library -- because the app is small enough that global state adds complexity without benefit
- CSS modules for all component styling, no inline styles -- because it enforces scoping and makes theming possible later
- Salesforce credentials via environment variables, never committed -- because the API key grants full org access
- All Salesforce data access goes through /server/salesforce/client.ts, never direct API calls from routes -- because rate limiting and error handling are centralized there
- Date handling uses date-fns, not native Date -- because timezone edge cases around midnight pipeline boundaries broke things twice with native Date
- Test files named *.test.ts, co-located with source when under /src/, mirrored path when under /server/ -- because co-location keeps tests visible during component work

## Module guide

- Authentication: none yet (deferred, see DECISIONS.md D3)
- Salesforce integration: /server/salesforce/ -- client.ts for API calls, aggregator.ts for pipeline math, schema.ts for type mappings
- Data caching: /server/db/ -- SQLite via better-sqlite3, migrations in /migrations/
- Dashboard: /src/components/Dashboard/ -- summary view, rep drill-down, standup mode
- Export: /src/export/ -- csv-builder.ts and pdf-builder.ts, shared encoding layer in encoding.ts
- Email: /src/email/ -- templates as React components, sender.ts wraps Resend API
- Scheduling: /server/jobs/ -- daily-fetch.ts (6am UTC cron), weekly-email.ts (Monday 7am UTC)

## Do not

- Do not add npm dependencies without discussion
- Do not modify the migration runner in /server/db/migrate.ts -- it has edge cases around partial failures (see DECISIONS.md D5)
- Do not store Salesforce credentials in code or logs
- Do not use native Date for any pipeline date calculations -- use date-fns (see Conventions)
- Do not make direct Salesforce API calls outside /server/salesforce/client.ts
- Do not delete or rename columns in existing migrations -- add new migrations instead

## Known issues

- CSV export silently drops rows with Unicode characters in deal names. Tracked in ROADMAP.md NOW bucket.
- The standup mode font size is hardcoded for 1080p displays and looks wrong on 4K screens. Low priority.
- Weekly email job occasionally times out on large pipelines (50+ deals). No data loss -- it retries on the next cycle.
```
