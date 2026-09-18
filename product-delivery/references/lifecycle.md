# Lifecycle State Machine

This document is the authoritative specification for the product-delivery state machine. SKILL.md summarizes it; this file is the complete reference.

## Top-Level States

| State | Purpose | Status |
|---|---|---|
| `intake` | Establish request, scope, constraints, risk, and actors | active |
| `discover` | Inspect repository/system and research unknowns | active |
| `frame` | Convert findings into agreed problem statement and success criteria | active |
| `plan` | Produce delivery plan, work graph, test strategy, context files | active |
| `deliver` | Execute work items through the nested submachine | active |
| `release` | Integrate, restructure artifacts, verify coherence | active |
| `stabilize` | Observe, present, confirm, and close out | active |
| `closed` | Final record preserved; no further transitions | terminal |
| `blocked` | Suspended safely with preserved state | blocked |
| `aborted` | Ended intentionally | terminal |

## Transition Table

Valid edges in the top-level machine:

```
intake     → discover
intake     → blocked
intake     → aborted

discover   → frame
discover   → blocked
discover   → aborted

frame      → plan
frame      → blocked
frame      → aborted

plan       → deliver
plan       → blocked
plan       → aborted

deliver    → release
deliver    → blocked
deliver    → aborted

release    → stabilize
release    → deliver    (if new work identified during restructure)
release    → blocked
release    → aborted

stabilize  → closed
stabilize  → deliver    (if user identifies new work during confirmation)
stabilize  → blocked
stabilize  → aborted

blocked    → (resume_state)  (returns to the state saved before blocking)

closed     → (none, terminal)
aborted    → (none, terminal)
```

Every transition not listed here is illegal. The engine must reject it and log a rejection event.

## Blocked State

`blocked` is a resumable overlay, not a normal state in the progression. When entering `blocked`:

1. The current phase is saved to `resume_state`.
2. `phase` is set to `blocked`.
3. `status` is set to `blocked`.
4. `blocked_reason` and `blocked_owner` are recorded.

When resuming:

1. `phase` is restored from `resume_state`.
2. `status` is set to `active`.
3. `resume_state`, `blocked_reason`, and `blocked_owner` are cleared.
4. All work-item states within `deliver` are preserved across block/resume.

## Terminal States

`closed` and `aborted` are terminal. No transitions out. The engine must reject any transition attempt and log a rejection event.

`aborted` requires a reason and records the disposition of partial work (what exists, what to do with it).

`closed` requires that stabilization is complete and the user has confirmed.

## Work-Item Submachine

Inside the `deliver` phase, each work item follows its own state machine:

```
ready → implementing → verifying → reviewing → accepted
```

### Valid Work-Item Transitions

```
ready         → implementing
implementing  → verifying
implementing  → blocked
verifying     → reviewing
verifying     → rework
reviewing     → accepted
reviewing     → rework
reviewing     → waived
rework        → implementing
blocked       → implementing   (when unblocked)
```

### Exception Paths

- **implementing → blocked**: External dependency or impediment. Records blocker reason.
- **verifying → rework**: Tests fail or acceptance criteria not met. Returns to implementing with recorded deficiency.
- **reviewing → rework**: User requests changes. Returns to implementing with recorded feedback.
- **reviewing → waived**: User accepts item with known gap. Requires `waive_approver` and `waive_reason`. Logged as evidence.
- **Any non-terminal item → cancelled**: Only valid when the parent scope changes and the item is no longer relevant. Requires a reason.

### Completion Guard

The top-level machine cannot leave `deliver` until the child completion guard is satisfied:

- Every work item must be in a terminal state: `accepted`, `waived`, or `cancelled`.
- At least one work item must be `accepted` (cannot waive or cancel all items).
- Items in `blocked` must be resolved or cancelled before exiting `deliver`.

## State Persistence Rules

1. Every mutation to `state.json` increments `revision` by 1.
2. Every mutation appends an event to `events.jsonl` with the new revision number.
3. `state.json` is a projection of `events.jsonl` — it can be rebuilt by replaying all events.
4. The `updated_at` timestamp is set on every mutation.
5. The `last_transition` field points to the most recent transition or item_transition event ID.

## Recovery Rules

If `state.json` is missing or corrupted:

1. If `events.jsonl` exists, rebuild `state.json` by replaying events from the beginning.
2. If both are missing, the workflow does not exist in this project. Run `workflow init`.
3. If `state.json` exists but `events.jsonl` is missing, log a warning. The state is usable but non-auditable.

## Concurrency Rules

1. Only one active workflow per project directory (one `.workflow/state.json`).
2. Transitions use optimistic concurrency: the caller must provide the expected revision. If the current revision differs, the transition is rejected.
3. Failed transitions leave state unchanged and append a rejection event with `type: "note"` and `reason` describing the conflict.
4. Repeated requests with the same `idempotency_key` are no-ops (return success without duplicating effects).

## Idempotency Key Format

```
{workflow_id}:{revision}:{from_state}-to-{to_state}
```

For work-item transitions:

```
{workflow_id}:{revision}:{item_id}:{from_state}-to-{to_state}
```

The engine stores used keys in the event log and rejects duplicates.

## Phase-Specific Behavior

### intake

- Determines `project_type` based on existing artifacts:
  - If the project has a working codebase with existing AGENTS.md, BUILD_PLAN.md with 10+ completed steps, or ROADMAP.md → `evolution`
  - If the project is new or has no coordination artifacts → `greenfield`
- Captures initial brief fields: who, problem, workaround
- For greenfield: runs the discovery conversation (core, user, core interaction)
- For evolution: identifies existing state and proposes migration or direct assessment

### discover

- For greenfield: completes brief with success criteria and constraints (what "done" looks like, hard constraints)
- For evolution: reads all existing coordination artifacts, assesses maturity signals, runs codebase health check

### frame

- For greenfield: synthesizes product summary, confirms with user
- For evolution: runs the direction conversation (what's working, what's next, what's dragging)
- Exit produces confirmed scope and acceptance criteria

### plan

- Generates the delivery plan using `templates/plan.md`
- Generates context files (AGENTS.md, CLAUDE.md stub)
- For evolution: also generates ARCHITECTURE.md and DECISIONS.md
- Runs output quality eval

### deliver

- Manages work items through the nested submachine
- Each item follows: ready → implementing → verifying → reviewing → accepted
- Preserves test-first discipline and regression bracket from legacy skills
- Updates AGENTS.md when patterns emerge

### release

- Archives superseded artifacts (BUILD_PLAN.md → BUILD_PLAN.archived.md)
- Verifies coherence across all artifacts
- Runs output quality eval
- Can loop back to `deliver` if restructuring reveals new work

### stabilize

- Presents complete artifact set to user
- Highlights changes, risks, open items
- Asks for confirmation
- Can loop back to `deliver` if user identifies new work
