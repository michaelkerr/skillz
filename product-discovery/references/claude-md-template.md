# CLAUDE.md Template

Save this file as `CLAUDE.md` in the project root. Follow this format exactly.

## Purpose

CLAUDE.md is a context file for AI coding assistants. It contains only information that changes AI behavior: structural decisions, conventions, constraints, and workflow rules. It is short at project start and grows as the project grows.

## Required sections

The file must contain exactly seven `##` sections in this order:

1. `## What this is` -- One paragraph from the product summary. State what the product does and for whom.
2. `## Build protocol` -- Reference BUILD_PLAN.md. Define the test-first and step-approval workflow.
3. `## Tech stack` -- Choices and brief rationale (one line per choice).
4. `## Project structure` -- Top-level directory convention. Grows as the project grows.
5. `## Conventions` -- Only conventions decided during the discovery conversation. One line each.
6. `## Do not` -- Hard constraints from discovery. Things the project must not do.
7. `## Decisions` -- Architectural decisions with rejected alternatives (one line each: "X over Y because Z").

The top-level heading (`#`) is the project name.

## What NOT to include

- Product strategy, user personas, market analysis (these do not change AI behavior)
- Rationale paragraphs (keep entries to 1-2 lines)
- Speculative content ("we might later want to...", "eventually we'll...", "down the road")
- Progress tracking, status updates, or session notes (that belongs in BUILD_PLAN.md)

## Complete example

```markdown
# SalesSync

## What this is

A dashboard that pre-computes daily Salesforce pipeline summaries so a sales manager can see yesterday's numbers in under 60 seconds, replacing the 30-minute manual spreadsheet ritual.

## Build protocol

- The build plan lives in BUILD_PLAN.md. Read it at the start of every session.
- Find the next step with status "not started." Build it.
- If the step has a Test field that is not "manual," write the test before writing the implementation. Build until the test passes.
- After building a step, present it to the user for evaluation. Do not proceed to the next step until the user confirms.

## Tech stack

- React (Vite) for the frontend
- Node.js + Express backend for Salesforce API proxy
- SQLite for caching fetched data locally

## Project structure

- Components in /src/components, each in its own folder
- API routes in /server/routes
- Salesforce integration in /server/salesforce

## Conventions

- All state management via useState/useReducer, no external state library
- CSS modules, no inline styles
- Salesforce credentials via environment variables, never committed

## Do not

- Do not add npm dependencies without discussion
- Do not implement auth until Step 6 or later
- Do not store Salesforce credentials in code

## Decisions

- SQLite over Postgres because this is a single-user local prototype
- Server-side Salesforce calls (not client-side) because API keys must stay secret
```
