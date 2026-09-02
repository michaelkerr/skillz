# DECISIONS.md Template

Save this file as `DECISIONS.md` in the project root. Follow this format exactly.

## Purpose

A running log of decisions that matter. The bar for inclusion: "Would someone working on this codebase in 3 months need to know this, and would they not be able to figure it out from the code alone?"

Seed this with decisions already captured in CLAUDE.md's Decisions section and any significant choices documented in BUILD_PLAN.md notes.

## Structure

Open with a `## How to use this file` section, then list decisions as `### DN: [Short title]` headings, numbered sequentially.

## Decision entry format

Each decision has exactly six bold fields:

```markdown
### DN: [Short title]
- **Date**: [when]
- **Area**: [what part of the system this affects]
- **Decision**: [what was decided, in one sentence]
- **Context**: [why this came up -- what problem or question prompted it]
- **Alternatives considered**: [what else was on the table and why it was rejected]
- **Consequences**: [what this means for future work -- constraints it creates]
```

### Field rules

**Date**: When the decision was made. Format: YYYY-MM-DD.

**Area**: The part of the system this affects. Use component names, module paths, or system areas (e.g., "Data persistence", "Authentication", "Export pipeline").

**Decision**: One sentence stating what was decided. Declarative, not explanatory.

**Context**: The problem or question that prompted the decision. Enough for someone unfamiliar to understand why this came up.

**Alternatives considered**: What else was on the table. For each alternative, state why it was rejected in one sentence. This prevents re-litigating settled decisions.

**Consequences**: What this decision means for future work. Constraints it creates, doors it closes, patterns it establishes.

## Complete example

```markdown
# Decisions

## How to use this file

Each entry captures a decision that affects how the codebase should evolve. Read relevant entries before starting work that touches their area. Add new entries when you make a decision that future work needs to respect.

---

### D1: SQLite for data caching
- **Date**: 2025-01-10
- **Area**: Data persistence
- **Decision**: Use SQLite for local data caching instead of PostgreSQL.
- **Context**: The prototype needs to cache Salesforce data locally so the dashboard loads instantly. Needed to choose a database.
- **Alternatives considered**: PostgreSQL (rejected: requires separate server process and setup, overkill for a single-user local app). In-memory only (rejected: data lost on restart, fetch is slow enough that re-fetching on every app start is a bad experience).
- **Consequences**: Single-file database. No connection pooling needed. Migrations are sequential SQL files. Cannot support concurrent writes from multiple processes -- if we ever run multiple workers, this decision must be revisited.

---

### D2: Server-side Salesforce calls only
- **Date**: 2025-01-10
- **Area**: Salesforce integration
- **Decision**: All Salesforce API calls go through the Express backend, never from the browser.
- **Context**: The React frontend could call Salesforce directly using the REST API, but the OAuth credentials would be exposed in browser network traffic.
- **Alternatives considered**: Client-side calls with a proxy token (rejected: still exposes partial credentials and adds token management complexity). Salesforce Connected App with PKCE flow (rejected: adds OAuth complexity for a single-user app).
- **Consequences**: All Salesforce logic lives in /server/salesforce/. Frontend never imports or references Salesforce types directly. API latency includes a round-trip through the Express server.

---

### D3: Defer authentication
- **Date**: 2025-01-15
- **Area**: Authentication
- **Decision**: No authentication for the prototype. The app is accessible to anyone with the URL.
- **Context**: Only two users (sales manager and one team lead) during the prototype phase. Adding auth before validating the core product delays validation.
- **Alternatives considered**: Basic auth (rejected: marginal security benefit for the effort, and passwords would need management). OAuth via Google (rejected: full implementation for two known users is premature).
- **Consequences**: Do not build any feature that assumes a logged-in user identity. No per-user preferences, no audit trails. Auth must be added before any broader rollout.

---

### D4: date-fns over native Date
- **Date**: 2025-01-22
- **Area**: Date handling
- **Decision**: Use date-fns for all date calculations, not native JavaScript Date.
- **Context**: Two bugs were caused by timezone handling around midnight boundaries when computing "yesterday's pipeline." Native Date's timezone behavior varies by environment.
- **Alternatives considered**: Luxon (rejected: heavier dependency for what we need). Day.js (rejected: plugin-based architecture means we would need to track which plugins are loaded). Native Date with explicit UTC (rejected: already failed twice).
- **Consequences**: All date imports come from date-fns. Any new date logic must use date-fns functions. startOfDay is always called with UTC timezone option.

---

### D5: Do not modify the migration runner
- **Date**: 2025-02-03
- **Area**: Data persistence
- **Decision**: The migration runner in /server/db/migrate.ts is frozen. Changes go through new migration files only.
- **Context**: A bug fix to the runner caused a partial migration that corrupted the fetch_log table. The runner has edge cases around partial failures and transaction boundaries that are difficult to test.
- **Alternatives considered**: Rewriting the runner with proper transaction handling (rejected: risk of new edge cases outweighs benefit; the current runner works if you do not touch it). Switching to a library like knex migrations (rejected: would require re-writing all existing migrations).
- **Consequences**: Never modify migrate.ts. Schema changes are new .sql files in /migrations/ with sequential numbering. If the runner itself needs a fix, create a parallel runner and test it against a copy of the database first.
```
