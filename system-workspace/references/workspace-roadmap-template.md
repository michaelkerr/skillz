# Workspace ROADMAP.md Template

Save this file as `ROADMAP.md` in the workspace root. Follow this format exactly.

## Purpose

The workspace ROADMAP.md captures work that spans multiple repos. Each repo has its own ROADMAP.md for repo-scoped work. This file does not repeat any of that. It answers one question: what cross-repo work is planned, in progress, or deferred?

An item belongs here when it requires coordinated changes across two or more repos, or when it is a workspace-wide initiative (migration, convention adoption, shared infrastructure) that no single repo owns.

## Required sections

The file must contain exactly five `##` sections in this order:

1. `## System summary` -- One paragraph describing the multi-repo system as a whole: what it does, who uses it, and how the repos work together. Not a list of repos (that's in AGENTS.md).
2. `## Now` -- 1-3 cross-repo items actively in progress or next up.
3. `## Next` -- 2-5 cross-repo items that come after the current NOW batch.
4. `## Later` -- Cross-repo work that matters but is not urgent.
5. `## Parked` -- Cross-repo ideas considered and deliberately deferred.

The top-level heading (`#`) is "Workspace Roadmap" or the system name followed by "Roadmap".

## What qualifies as a workspace roadmap item

An item belongs here if ANY of these are true:

- It requires changes in two or more repos (e.g., API v2 migration touching api-service and web-client)
- It is a workspace-wide initiative no single repo owns (e.g., adopt shared linting config across all repos)
- It involves changing a cross-repo contract (shared types, API shape, event schema)
- It has sequencing constraints across repos (repo A must ship before repo B can start)

An item does NOT belong here if:

- It lives entirely within one repo, even if important -- put it in that repo's ROADMAP.md
- It is a per-repo convention or pattern -- put it in that repo's AGENTS.md
- It is speculative with no concrete scope -- do not track it anywhere yet

## NOW item format

Each NOW item is a `### [Item name]` heading followed by exactly six bold fields as a bulleted list:

```markdown
### [Item name]
- **Type**: migration | integration | infrastructure | convention | contract-change
- **What it does**: [one sentence describing the cross-repo outcome]
- **Repos**: [which repos are involved, and what each one's role is]
- **Sequence**: [ordering constraints between repos, or "parallel" if none]
- **Done when**: [concrete, testable completion criteria spanning the relevant repos]
- **Notes**: [empty at start; filled in during work]
```

### Field rules

**Type**: One of five values exactly: `migration` (moving repos to a new tool/pattern/version), `integration` (connecting repos that weren't connected), `infrastructure` (shared infra like CI, deploy, shared packages), `convention` (adopting a shared convention across repos), `contract-change` (changing a shared API, schema, or type that flows between repos).

**What it does**: One sentence describing the outcome across the system.

**Repos**: List each involved repo and its role in the change. e.g., "acme-api (producer), acme-web (consumer), acme-shared (type definitions)".

**Sequence**: Which repo must go first, or "parallel" if repos can move independently. e.g., "acme-shared ships new types → acme-api adopts → acme-web updates client".

**Done when**: Criteria that span the repos. "All three repos import from @acme/shared v2 and the old inline types are deleted" passes. "Types are updated" does not.

**Notes**: Empty at start. Filled during work with coordination decisions, blockers, or scope changes.

## NEXT item format

Less detailed. Each gets a one-liner with repos named:

```markdown
- **[Item name]** (type): [one sentence]. Repos: [list].
```

## LATER item format

Even less detail. Just enough to remember what and why:

```markdown
- **[Item name]**: [why it matters across repos]
```

## PARKED item format

Include the reason so items do not resurface without new information:

```markdown
- **[Item name]**: [why it is parked]
```

## Relationship to per-repo roadmaps

When a workspace roadmap item is in NOW, the individual repos involved should have corresponding items in their own ROADMAP.md files. The workspace item tracks coordination; the per-repo items track implementation. If a per-repo ROADMAP.md has an item that affects a cross-repo contract, it should be reflected here.

## What NOT to include

- Per-repo work items (those belong in each repo's own ROADMAP.md)
- Product strategy or vision statements
- Completed items (update System summary if capabilities changed, then remove)
- Speculative items with no concrete scope

## Line budget

Keep the entire file under 80 lines. Cross-repo coordination should be few and high-signal.

## Complete example

```markdown
# Acme Platform Roadmap

## System summary

Acme Platform is a three-repo system serving a 12-person sales team: acme-api handles data and business logic, acme-web is the customer-facing dashboard, and acme-shared publishes TypeScript types consumed by both. The repos coordinate through a shared type package and REST API contracts.

## Now

### Shared Types V2 Migration
- **Type**: migration
- **What it does**: Migrates all three repos from hand-written TypeScript interfaces to Zod schemas in acme-shared, giving runtime validation alongside static types.
- **Repos**: acme-shared (defines schemas), acme-api (validates inbound requests), acme-web (validates API responses)
- **Sequence**: acme-shared publishes @acme/shared@2.0 → acme-api adopts for request validation → acme-web adopts for response parsing
- **Done when**: All API request/response shapes use Zod schemas from @acme/shared@2.0, the old hand-written interfaces are deleted from all three repos, and both acme-api and acme-web CI pass with the new dependency.
- **Notes**:

### Unified Error Format
- **Type**: contract-change
- **What it does**: Standardizes error response shapes across acme-api endpoints so acme-web can use a single error handler.
- **Repos**: acme-shared (error type definitions), acme-api (error responses), acme-web (error handling)
- **Sequence**: parallel -- acme-shared defines the shape, acme-api and acme-web can adopt independently once published
- **Done when**: All acme-api error responses match the ErrorResponse schema in acme-shared, and acme-web's API client uses a single catch handler for all endpoints.
- **Notes**:

## Next

- **CI Pipeline Consolidation** (infrastructure): Move all three repos to a shared GitHub Actions workflow. Repos: acme-api, acme-web, acme-shared.
- **Event Bus Integration** (integration): Replace direct API calls from acme-jobs to acme-api with an event bus for async job completion. Repos: acme-api, acme-jobs.
- **Shared ESLint Config** (convention): Extract the duplicated ESLint config into @acme/eslint-config consumed by all repos. Repos: all.

## Later

- **Monorepo Evaluation**: Assess whether the three repos should become a monorepo as the team grows. Affects build, deploy, and CI for all repos.
- **API Versioning Strategy**: Define how acme-api versions its endpoints so acme-web can adopt new APIs without lockstep deploys.

## Parked

- **GraphQL Migration**: Considered replacing the REST API with GraphQL. Parked because the team is small, the API surface is stable, and the migration cost outweighs the flexibility benefits at current scale.
```
