# ROADMAP.md Template

Save this file as `ROADMAP.md` in the project root, replacing BUILD_PLAN.md. Follow this format exactly.

## Structure

The file has six sections:

1. `## Product summary` -- one paragraph describing what the product IS now, not what it was going to be.
2. `## What's built` -- compact summary of current capabilities. 3-8 bullet points. Not a list of every completed build step. A description of what the product does today.
3. `## Now` -- 2-4 items actively in progress or next up.
4. `## Next` -- 3-6 items that come after the current NOW batch.
5. `## Later` -- things that matter but are not urgent.
6. `## Parked` -- ideas considered and deliberately deferred.

## NOW item format

Each NOW item is a `### [Item name]` heading followed by exactly six bold fields as a bulleted list:

```markdown
### [Item name]
- **Type**: feature | fix | debt | improvement | infrastructure
- **What it does**: [one sentence describing the user-visible or developer-visible outcome]
- **Done when**: [concrete, testable completion criteria]
- **Touches**: [which parts of the codebase this change affects -- files, modules, or systems]
- **Risk**: [what could go wrong or what this might break]
- **Notes**: [empty at start; filled in during work]
```

### Field rules

**Type**: One of five values exactly: `feature`, `fix`, `debt`, `improvement`, `infrastructure`. Making tech debt and infrastructure visible as first-class work prevents the backlog from becoming feature-only.

**What it does**: One sentence describing the outcome. User-visible for features; developer-visible for debt/infrastructure.

**Done when**: Concrete, testable criteria. "The CSV export handles Unicode characters without dropping rows" passes. "It works better" does not.

**Touches**: Which parts of the codebase this change affects. Files, modules, or systems. At maturity, knowing WHAT a change affects matters more than knowing what comes after it.

**Risk**: What could go wrong or what this might break. At maturity, new work can break existing work. Calling out the risk surface before starting prevents surprises.

**Notes**: Empty at start. Filled during work with patterns established, unexpected complexity, or scope changes.

## NEXT item format

Less detailed. Each gets a one-liner:

```markdown
- **[Item name]** (type): [one sentence]
```

## LATER item format

Even less detail. Just enough to remember what and why:

```markdown
- **[Item name]**: [why it matters]
```

## PARKED item format

Include the reason so items do not resurface without new information:

```markdown
- **[Item name]**: [why it is parked]
```

## Key differences from BUILD_PLAN.md

1. **No sequence numbers.** Items in NOW are equally valid to work on. Pick based on context, energy, and need.
2. **No completed-step graveyard.** "What's built" is a living summary. When a NOW item is complete, update the summary if capabilities changed, then remove the item.
3. **Type labels.** Makes tech debt and infrastructure visible as first-class work.
4. **Risk field.** New work can break existing work at maturity.
5. **Touches field.** As the codebase grows, knowing what a change affects matters.

## Complete example

```markdown
# Roadmap

## Product summary

SalesSync pre-computes daily Salesforce pipeline summaries for a 12-person sales team. The manager opens the app each morning and sees yesterday's numbers in under 60 seconds, replacing a 30-minute manual spreadsheet ritual. The team uses it daily for standups and weekly pipeline reviews.

## What's built

- Salesforce API integration with daily scheduled data fetch
- Pipeline summary dashboard with total value, per-stage breakdown, and per-rep subtotals
- Rep detail drill-down (click rep name to see individual deals)
- Auto-refresh via daily cron job at 6am UTC
- Error state handling with stale-data banner
- Standup mode with large-text full-screen view

## Now

### Unicode CSV Export Fix
- **Type**: fix
- **What it does**: Fixes the CSV export to handle Unicode characters in deal names without dropping rows.
- **Done when**: Exporting a pipeline report containing deals with Chinese, Arabic, and emoji characters produces a CSV with all rows intact and correctly encoded.
- **Touches**: /src/export/csv-builder.ts, /src/export/encoding.ts
- **Risk**: Changing the encoding layer could affect the existing PDF export which shares the same data pipeline.
- **Notes**:

### Weekly Summary Email
- **Type**: feature
- **What it does**: Sends a weekly pipeline summary email to the sales manager every Monday at 7am.
- **Done when**: The manager receives an email with the same data shown in the dashboard summary, formatted for mobile reading.
- **Touches**: new /src/email/ module, /server/routes/schedule.ts, /server/salesforce/aggregator.ts
- **Risk**: Email delivery reliability. Need to handle Resend API failures gracefully.
- **Notes**:

### Test Coverage for Aggregator
- **Type**: debt
- **What it does**: Adds unit tests for the Salesforce data aggregation logic, which currently has zero coverage.
- **Done when**: /server/salesforce/aggregator.ts has tests covering: empty pipeline, single rep, multiple reps across stages, and deals updated at midnight boundary.
- **Touches**: /server/salesforce/aggregator.ts, new test file
- **Risk**: Low. Read-only tests against existing logic.
- **Notes**:

## Next

- **Deal Change Tracking** (feature): Show which deals changed stage since yesterday, with direction indicators (up/down).
- **Mobile-Responsive Layout** (improvement): Dashboard currently assumes desktop viewport. Make it usable on the manager's phone.
- **Rate Limit Handling** (infrastructure): Salesforce API rate limits are not handled. Add backoff and retry logic.
- **Filter by Team** (feature): Support filtering the pipeline view by sales team when the org grows beyond one team.

## Later

- **Multi-org Support**: Some managers oversee two Salesforce orgs. Would require credential management and org switching.
- **Historical Trends**: Show pipeline value over time as a chart. Requires storing daily snapshots.
- **Slack Integration**: Post the daily summary to a Slack channel instead of requiring the app to be opened.

## Parked

- **Real-time Updates**: Considered WebSocket-based live pipeline updates. Parked because the team only checks numbers once a day and the complexity is not justified by the use pattern.
- **Custom Dashboard Builder**: Let the manager drag and drop widgets. Parked because the fixed layout matches their workflow and customization adds maintenance burden without clear value.
```
