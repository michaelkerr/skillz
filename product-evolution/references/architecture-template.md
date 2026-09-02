# ARCHITECTURE.md Template

Save this file as `ARCHITECTURE.md` in the project root. Follow this format exactly.

## Purpose

This document exists because the codebase is too complex for CLAUDE.md's project structure section to convey how the system works. CLAUDE.md says WHERE things are. ARCHITECTURE.md says HOW they fit together.

Keep this document accurate. An outdated architecture doc is worse than none -- it gives the AI confidence in a wrong mental model. Update it when the system's structure changes, not when individual features are added within the existing structure.

## Required sections

The file must contain at least five `##` sections:

1. `## System overview` -- 2-3 sentences describing the architecture at the highest level.
2. `## Component map` -- each major component as a `###` heading with Purpose, Entry point, Depends on, Depended on by, and Key patterns.
3. `## Data flow` -- how data moves through the system for core interactions. Text descriptions, not diagrams.
4. `## Data model` -- key entities, their relationships, where they live. Not a full schema.
5. `## Integration points` -- external services, APIs, third-party dependencies with failure modes.

Optional sections for complex projects:

- `## Performance-sensitive paths` -- code paths where performance matters, optimizations applied, constraints.
- `## Security model` -- auth, authorization, data access controls, input validation patterns.

## Component map entry format

```markdown
### [Component name]
- **Purpose**: [what it does]
- **Entry point**: [main file]
- **Depends on**: [other components it calls or imports from]
- **Depended on by**: [what calls into it]
- **Key patterns**: [anything specific to this component's implementation]
```

## Data flow format

Use numbered steps per core interaction:

```markdown
### [Core interaction name]
1. [Step]: [what happens, which component handles it, what data is passed]
2. [Step]: ...
```

## Complete example

```markdown
# Architecture

## System overview

Monolithic Node.js application with a React frontend served by Vite in development and static builds in production. Express handles API routing and proxies all Salesforce API calls. SQLite provides local data caching so the dashboard loads instantly from cached data rather than waiting for Salesforce API responses.

## Component map

### Salesforce Client
- **Purpose**: Handles all communication with the Salesforce REST API.
- **Entry point**: /server/salesforce/client.ts
- **Depends on**: nothing (leaf dependency)
- **Depended on by**: Aggregator, Daily Fetch Job
- **Key patterns**: Rate-limited request queue. All responses normalized to internal schema via schema.ts before leaving this module.

### Aggregator
- **Purpose**: Transforms raw Salesforce opportunity data into pipeline summaries (totals, per-stage, per-rep).
- **Entry point**: /server/salesforce/aggregator.ts
- **Depends on**: Salesforce Client (for schema types only, not for API calls)
- **Depended on by**: Dashboard API routes, Weekly Email Job
- **Key patterns**: Pure functions. No side effects. Takes an array of normalized opportunities, returns summary objects. All date comparisons use date-fns startOfDay in UTC.

### Dashboard API
- **Purpose**: Serves pipeline data to the React frontend.
- **Entry point**: /server/routes/pipeline.ts
- **Depends on**: Database (reads cached data), Aggregator (computes summaries)
- **Depended on by**: React Dashboard components
- **Key patterns**: Always reads from cache, never calls Salesforce directly. Returns 503 with last-update timestamp if cache is empty.

### React Dashboard
- **Purpose**: Renders pipeline summaries, rep drill-downs, and standup mode.
- **Entry point**: /src/components/Dashboard/index.tsx
- **Depends on**: Dashboard API (via fetch)
- **Depended on by**: nothing (top-level UI)
- **Key patterns**: All state in component state (useState/useReducer). No global state store. Standup mode is a CSS class toggle, not a separate route.

### Daily Fetch Job
- **Purpose**: Runs on a cron schedule to pull fresh Salesforce data and cache it.
- **Entry point**: /server/jobs/daily-fetch.ts
- **Depends on**: Salesforce Client, Database
- **Depended on by**: nothing (triggered by cron)
- **Key patterns**: Records fetch timestamp and success/failure status. On failure, does not clear stale cache -- the dashboard shows the stale-data banner instead.

## Data flow

### Morning Dashboard Load
1. Manager opens the app. React requests GET /api/pipeline/summary.
2. Dashboard API reads cached opportunities from SQLite.
3. Aggregator computes totals, per-stage counts, and per-rep breakdowns from cached data.
4. API returns the summary JSON. React renders the dashboard.
5. If cache is empty or fetch never succeeded, API returns 503 with last-update timestamp. React shows the stale-data banner.

### Daily Data Refresh
1. Cron triggers daily-fetch.ts at 06:00 UTC.
2. Salesforce Client queries the Salesforce REST API for opportunities updated in the last 24 hours.
3. Raw responses are normalized via schema.ts.
4. Normalized data is upserted into SQLite, replacing stale records.
5. Fetch timestamp and status are recorded. On failure, existing cache is preserved.

### Rep Drill-Down
1. Manager clicks a rep name in the summary view.
2. React requests GET /api/pipeline/rep/:repId.
3. Dashboard API reads that rep's cached opportunities from SQLite.
4. API returns the deal list. React renders the detail panel below the summary row.

## Data model

Three SQLite tables:

- **opportunities**: Salesforce opportunity records (id, rep_name, deal_name, value, stage, updated_at). Primary key is Salesforce ID. Upserted on each daily fetch.
- **fetch_log**: One row per fetch attempt (id, timestamp, status, error_message). Used by the dashboard to show data freshness and error states.
- **settings**: Key-value store for configuration (cron schedule, Salesforce org ID). Single-row entries.

Relationships: fetch_log is independent. opportunities are the core data. settings configures the fetch behavior.

## Integration points

### Salesforce REST API
- **What it does**: Source of all pipeline data.
- **How it is called**: OAuth 2.0 bearer token, REST queries via /server/salesforce/client.ts.
- **When it is down**: Dashboard serves cached data. Stale-data banner shows with last-success timestamp. Daily fetch logs the failure and retries on next cron cycle.

### Resend (email)
- **What it does**: Sends weekly pipeline summary emails.
- **How it is called**: REST API via /src/email/sender.ts with API key from environment variable.
- **When it is down**: Email job logs the failure. No retry within the same cycle. Manager can view the same data in the dashboard.
```
