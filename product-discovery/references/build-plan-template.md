# BUILD_PLAN.md Template

Save this file as `BUILD_PLAN.md` in the project root. Follow this format exactly.

## Structure

The file has two sections:

1. `## Product summary` -- one paragraph from Phase 1 synthesis. State the user, the problem, and the product's core value in 2-3 sentences.
2. `## Steps` -- the sequenced build steps.

## Step format

Each step is a `### Step N: [Name]` heading followed by exactly six bold fields as a bulleted list. Use this exact layout:

```markdown
### Step N: [Name]
- **Status**: not started
- **What it does**: [one sentence, one user-visible behavior]
- **What good looks like**: [one specific input/output example]
- **Test**: [assertion with literal input and expected output, OR "manual"]
- **Builds on**: [nothing, OR prior step number(s)]
- **Notes**:
```

### Field rules

**Status**: One of three values exactly: `not started`, `in progress`, `complete`. All steps start as `not started`.

**What it does**: One sentence describing a single user-visible behavior. If the sentence contains "and" joining two behaviors ("Add filtering and sorting"), split into two steps.

**What good looks like**: A concrete example showing a specific input and the specific output the user sees. Not abstract ("the UI updates") -- concrete ("Clicking 'Jane Smith' shows her 3 deals with values and stages").

**Test**: Either:
- The word `manual` (for steps requiring human judgment: layout, interaction feel, visual design)
- An assertion with literal input and literal expected output: "Given [specific input], [specific expected result]." The assertion must define expected behavior independent of implementation. "The function returns an array" fails -- it describes code, not what the user sees. "Given these 3 transactions, the total displays as $47.50" passes.

**Builds on**: `nothing` for the first step. For subsequent steps, reference the step number(s) this step depends on: `Step 0`, `Step 1`, etc. No forward references (a step cannot build on a later step). No circular references.

**Notes**: Empty at project start. Filled during the build with patterns established, unexpected complexity, or scope changes.

## Step numbering

- If the core interaction requires a specific data source (API, database), start with `Step 0` for the data connection, then `Step 1` for the core interaction.
- Otherwise, start with `Step 1` for the core interaction.
- Number sequentially. Steps can be added, removed, or reordered during the build.

## Scope

- Exploring: 5-7 steps. Core interaction plus 1-2 supporting behaviors. No infrastructure.
- Shipping: 8-12 steps. Infrastructure steps (auth, deployment, error handling) come after the core interaction.
- If you have more than 15 steps, the scope is too big. Work with the user to cut.

## Complete example

```markdown
# Build Plan

## Product summary

A 12-person sales team wastes 30 minutes each morning manually pulling Salesforce pipeline data into Google Sheets for their daily standup. This app pre-computes the summary so the sales manager sees yesterday's numbers in under 60 seconds.

## Steps

### Step 0: Salesforce API Connection
- **Status**: not started
- **What it does**: Connects to the Salesforce API and retrieves yesterday's opportunity pipeline data.
- **What good looks like**: Given valid Salesforce credentials, the script outputs a JSON array of yesterday's opportunities with rep name, deal value, and stage.
- **Test**: Given a Salesforce sandbox with 3 test opportunities updated yesterday, the output JSON contains exactly 3 entries with fields rep_name, value, and stage.
- **Builds on**: nothing
- **Notes**:

### Step 1: Pipeline Summary View
- **Status**: not started
- **What it does**: Displays yesterday's pipeline numbers as a summary dashboard the sales manager can scan in under 10 seconds.
- **What good looks like**: A page shows total pipeline value, deals by stage, and a per-rep breakdown, all from the Salesforce data retrieved in Step 0.
- **Test**: Given 5 opportunities across 3 reps and 2 stages, the summary shows the correct total, correct per-stage counts, and correct per-rep subtotals.
- **Builds on**: Step 0
- **Notes**:

### Step 2: Rep Detail Drill-Down
- **Status**: not started
- **What it does**: Tapping a rep name in the summary reveals that rep's individual deals.
- **What good looks like**: Clicking "Jane Smith" shows her 3 deals with values and stages. Clicking again collapses the detail.
- **Test**: manual
- **Builds on**: Step 1
- **Notes**:

### Step 3: Auto-Refresh on Schedule
- **Status**: not started
- **What it does**: The app fetches fresh Salesforce data on a daily schedule so the manager never manually refreshes.
- **What good looks like**: After the scheduled job runs at 6am, opening the app shows data updated within the last hour.
- **Test**: Given a cron job configured for 06:00 UTC, the data_fetched_at timestamp in the database is within 60 minutes of 06:00 UTC after the job runs.
- **Builds on**: Step 1
- **Notes**:

### Step 4: Error State Handling
- **Status**: not started
- **What it does**: Shows a clear message when Salesforce data is unavailable or stale.
- **What good looks like**: If the last fetch failed, the dashboard shows "Data unavailable -- last successful update was [timestamp]" instead of blank or stale numbers.
- **Test**: Given a failed Salesforce fetch and a last-success timestamp of "2025-01-15 06:00", the banner displays "Data unavailable -- last successful update was Jan 15, 6:00 AM."
- **Builds on**: Step 3
- **Notes**:

### Step 5: Standup Mode
- **Status**: not started
- **What it does**: A full-screen view optimized for presenting pipeline numbers during the standup meeting.
- **What good looks like**: Pressing "Standup" enters a large-text view showing total pipeline, top 3 changes since yesterday, and the rep with the biggest movement.
- **Test**: manual
- **Builds on**: Step 2
- **Notes**:
```
