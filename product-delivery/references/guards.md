# Transition Guards

Every state transition is gated by one or more guards. A transition proceeds only when all mandatory guards return `pass` or an authorized `waived`. This document is the authoritative guard catalog.

## Guard Outcomes

| Outcome | Meaning |
|---|---|
| `pass` | Guard condition is satisfied |
| `fail` | Guard condition is not satisfied; transition blocked |
| `not_applicable` | Guard does not apply to this project type or context |
| `waived` | Guard failed but was explicitly waived with actor, reason, and risk |

A `waived` outcome is evidence, not a synonym for `pass`. It requires an actor, reason, expiry or scope, and the risk being accepted. Waivers are logged in the event log and stored in `state.json.waivers`.

## Guard Catalog

### intake → discover

| Guard | Condition | Project Type |
|---|---|---|
| `brief_who_populated` | `brief.who` is set and names a specific role or person, not a category | both |
| `brief_problem_populated` | `brief.problem` describes a concrete action/situation with frequency or consequence | both |
| `project_type_determined` | `project_type` is set to greenfield or evolution | both |

### discover → frame

| Guard | Condition | Project Type |
|---|---|---|
| `core_interaction_defined` | `brief.core_interaction` has description, input, output, and hard_part | greenfield |
| `success_criteria_exist` | At least one acceptance criterion exists with a testable assertion | greenfield |
| `constraints_captured` | `brief.constraints` has at least platform and timeline | greenfield |
| `maturity_assessment_complete` | Maturity signals have been evaluated and recorded as evidence | evolution |
| `health_check_performed` | Codebase health check has been run and results recorded as evidence | evolution |
| `existing_artifacts_read` | All existing coordination artifacts have been read and cataloged | evolution |

### frame → plan

| Guard | Condition | Project Type |
|---|---|---|
| `scope_confirmed` | User has confirmed the synthesis/summary or direction conversation is complete | both |
| `acceptance_criteria_testable` | Every AC-NNN has `testable: true` or a documented reason why not | greenfield |
| `direction_captured` | `brief.direction` has working, next (2-3 items), and dragging | evolution |
| `user_confirmation` | User has explicitly confirmed the framing is correct | both |

### plan → deliver

| Guard | Condition | Project Type |
|---|---|---|
| `plan_exists` | Delivery plan artifact exists and passes format validation | both |
| `criteria_mapped` | Every AC-NNN maps to at least one WI-NNN | both |
| `verification_strategy_exists` | Each work item has a test field (assertion or "manual") | both |
| `context_files_exist` | AGENTS.md and CLAUDE.md exist | both |
| `architecture_documented` | ARCHITECTURE.md exists | evolution |
| `decisions_seeded` | DECISIONS.md exists with initial entries from existing artifacts | evolution |

### deliver → release

| Guard | Condition | Project Type |
|---|---|---|
| `work_items_complete` | All WI-NNN are in terminal state (accepted, waived, or cancelled) | both |
| `at_least_one_accepted` | At least one work item is `accepted` (not all waived/cancelled) | both |
| `no_items_blocked` | No work items are in `blocked` state | both |
| `tests_pass` | Most recent test run shows all tests passing | both |
| `agents_md_current` | AGENTS.md reflects patterns established during delivery | both |

### release → stabilize

| Guard | Condition | Project Type |
|---|---|---|
| `coherence_check_passes` | Cross-artifact coherence verification has been performed | both |
| `eval_passes` | Output quality eval returns no FAIL findings | both |
| `superseded_artifacts_archived` | Old BUILD_PLAN.md archived if migrating from greenfield | evolution |
| `no_orphaned_references` | No active documents reference archived/removed artifacts | both |

### stabilize → closed

| Guard | Condition | Project Type |
|---|---|---|
| `user_confirms` | User has explicitly confirmed the final artifact set | both |
| `residual_risks_acknowledged` | All open RISK-NNN have status mitigated or accepted | both |
| `final_test_pass` | Final test suite run passes | both |

### Any active state → blocked

| Guard | Condition |
|---|---|
| `reason_provided` | A non-empty `blocked_reason` is given |
| `owner_provided` | A `blocked_owner` is specified (who needs to resolve this) |

No guards block this transition — it is always allowed when reason and owner are provided.

### blocked → (resume)

| Guard | Condition |
|---|---|
| `resume_state_exists` | `resume_state` is set and valid |

### Any active state → aborted

| Guard | Condition |
|---|---|
| `reason_provided` | A non-empty abort reason is given |
| `disposition_recorded` | What to do with partial work is documented |

## Work-Item Guards

### ready → implementing

| Guard | Condition |
|---|---|
| `dependencies_met` | All WI-NNN in `depends_on` are `accepted` or `waived` |
| `not_blocked` | No active blockers on this item |

### implementing → verifying

| Guard | Condition |
|---|---|
| `implementation_exists` | Some code or artifact has been produced |

### verifying → reviewing

| Guard | Condition |
|---|---|
| `tests_executed` | Tests for this item have been run and results recorded |
| `acceptance_criteria_checked` | Each linked AC-NNN has been evaluated against the implementation |

### reviewing → accepted

| Guard | Condition |
|---|---|
| `user_approves` | User has confirmed the work item meets expectations |
| `regression_tests_pass` | Full test suite passes after this item's changes |

### reviewing → waived

| Guard | Condition |
|---|---|
| `waive_approver_set` | `waive_approver` is recorded |
| `waive_reason_set` | `waive_reason` is recorded |
| `risk_acknowledged` | The gap being accepted is documented as a risk |

## Overriding Guards

Guards can be overridden in three ways:

1. **Force**: The `--force` flag on a transition. Logs `forced: true` in the event. All failed guards are recorded.
2. **Waiver**: A specific guard is waived with `workflow waive <guard>`. Requires approver and reason. Logged as a waiver event.
3. **Config override**: The `guard_overrides` in `config.json` can set a guard to `warn` (log but allow) or `skip` (ignore entirely).

Force and waiver are per-transition. Config overrides persist across transitions.
