---
name: product-delivery
description: >
  Unified lifecycle skill for software products — from first idea through
  delivery and stabilization. Replaces product-discovery and product-evolution
  with a single hierarchical state machine. Use when starting a new product
  ("I want to build..."), evolving a mature one ("what should we do next?"),
  resuming an in-progress workflow ("workflow status"), or when someone is about
  to jump straight into code without planning. Do NOT use for non-software
  projects or for work that does not need lifecycle coordination.
license: Apache-2.0
compatibility: Requires filesystem access. MCP server or CLI for state management.
metadata:
  version: "1.0.0"
---

# Product Delivery

Manage a software product from first idea through delivery and stabilization using a hierarchical state machine. State lives in `.workflow/state.json` in the target project. All transitions are evidence-gated and logged to `.workflow/events.jsonl`.

This skill replaces product-discovery and product-evolution with a single authority.

## How It Works

The workflow progresses through top-level states:

```
intake → discover → frame → plan → deliver → release → stabilize → closed
```

Two overlay states can be entered from any active state:
- `blocked` — suspends safely, preserves all state, resumes where it left off
- `aborted` — ends intentionally (terminal)

Inside `deliver`, each work item follows its own submachine:

```
ready → implementing → verifying → reviewing → accepted
```

See `references/lifecycle.md` for the full state machine specification including all valid transitions, exception paths, and completion guards.

## State Management

Use the MCP server (`product-delivery`) when available — it exposes all workflow operations as tools with built-in validation. Fall back to the CLI (`scripts/workflow`) in environments without MCP. Both share the same engine; behavior is identical.

## Initialization

When entering a project:

1. Check for `.workflow/state.json`. If it exists, resume from the current state.
2. If it does not exist, initialize a new workflow.
3. If the project has `BUILD_PLAN.md` or `ROADMAP.md` from legacy skills, initialize with migration (see `references/migration.md`).

## States

### intake

Establish the request. Determine whether this is a greenfield project (new product from scratch) or an evolution (existing product that needs restructuring).

**Detection rules:**
- If the project has a working codebase with AGENTS.md, BUILD_PLAN.md with completed steps, or ROADMAP.md → evolution
- If the project is new or has no coordination artifacts → greenfield

**For greenfield — run a structured conversation:**

Ask one question at a time. Wait for the answer. Follow up when an answer is incomplete, contradicts an earlier answer, or uses vague language.

**1. The Core.** Ask: "What are you building, and what problem does it solve?" Complete when you can fill: **[Who]** has **[problem with frequency/consequence]** and currently **[workaround or "nothing — triggered by X"]**.

**2. The User.** Ask: "Who specifically will use this, and what's their context?" Complete when you know: a specific role/person, the trigger moment, and the current workaround.

**3. The Core Interaction.** Ask: "Walk me through the single most important thing a user does in this product." Complete when you know: the one interaction, the input, the output, and where the hard part is (input/processing/output).

**For evolution:** Identify existing artifacts and note the project type. The detailed assessment happens in `discover`.

**Exit evidence:** Brief has who and problem populated. Project type determined.

### discover

Deepen understanding before committing to a direction.

**For greenfield:**

**4. What "Done" Looks Like.** Ask: "What would you need to see in a working prototype to know this idea works?" Each criterion must be testable: "Given [input], the product [does thing] in [bound]." Reject "feels intuitive" or "works well" — ask what they would see or measure.

**5. Constraints.** Ask: "Are there hard constraints I should know about?" Probe for platform, stack preferences, data sources, user scale, and timeline (exploring vs. shipping).

**For evolution:**

Read all existing coordination artifacts (AGENTS.md, BUILD_PLAN.md, ROADMAP.md, docs). Assess maturity signals:
- Core product interaction works and has been validated
- Multiple completed build steps with accumulated notes
- Remaining work is mostly independent
- Codebase has clear, repeated patterns

If the project is not ready to evolve, say so directly and stop. Do not proceed to restructuring.

Run a codebase health check: test coverage gaps, tech debt, dead code, architecture strain. Record results as evidence.

**Exit evidence:** For greenfield: success criteria are testable, constraints captured. For evolution: maturity assessment and health check recorded.

### frame

Convert findings into an agreed direction.

**For greenfield:**

Synthesize a product summary:

```
Problem:          [one sentence]
User:             [who, in what context]
Core interaction: [the one thing that IS the product]
Success criteria: [how you will know the prototype works]
Constraints:      [platform, stack, data, users, timeline]
```

Confirm with the user. If anything is wrong or missing, fix it before proceeding.

**For evolution:**

Run the direction conversation. Ask one question at a time:

1. "What's the strongest part of this product right now?" — identifies what to protect.
2. "What are the 2-3 most important things this product needs in the next month?" — seeds the NOW bucket.
3. "What's the most annoying thing about working in this codebase right now?" — tech debt, missing tooling, slow builds. These become first-class work items.

**Exit evidence:** User has confirmed the framing. Acceptance criteria defined (greenfield) or direction captured (evolution).

### plan

Produce the delivery plan and context files.

**For greenfield — generate a sequenced build plan** using `templates/plan.md`:

1. Core interaction first — the thing that makes the product the product.
2. Each step is independently evaluable.
3. Each step builds on the prior working state.
4. Defer infrastructure (auth, deployment, CI, database setup).
5. One behavior per step — if "What it does" contains "and" joining two behaviors, split it.
6. More granularity where the hard part is.
7. Typical range: 5-12 steps. Over 15 means scope is too large.

Each step gets a WI-NNN ID, links to AC-NNN acceptance criteria, and has a test field (assertion or "manual").

**For evolution — generate a priority-bucketed roadmap** using `templates/plan.md` (evolution format):

- NOW: 2-3 items with full detail (type, acceptance criteria, touches, risk)
- NEXT: items with one-sentence descriptions
- LATER: items with rationale for deferral
- PARKED: items with reason for parking

Seed with direction conversation outcomes and health check findings.

**Generate context files:**

- AGENTS.md: tool-agnostic project context file. For greenfield: sections for what-this-is, build protocol, tech stack, project structure, commands, conventions, do-not, decisions, known issues. For evolution: add architecture overview, module guide; evolve build protocol to work protocol.
- CLAUDE.md: stub containing only `@agents.md`
- For evolution, also: ARCHITECTURE.md (system overview, component map, data flow, data model, integration points) and DECISIONS.md (running log with date, area, decision, context, alternatives, consequences).

Run the output quality eval to validate. Fix any FAIL findings.

**Exit evidence:** Plan artifact exists and passes validation. Context files exist. User confirms.

### deliver

Execute work items through the nested submachine. This is the build loop.

**Work-item flow:** `ready → implementing → verifying → reviewing → accepted`

**Exception paths:**
- `implementing → blocked` — external dependency or impediment
- `verifying → rework → implementing` — tests fail or criteria not met
- `reviewing → rework → implementing` — user requests changes
- `reviewing → waived` — user accepts with known gap (requires approver and reason, logged as evidence)

**For each work item:**

1. Run existing tests before starting. Report count: "47 passed, 0 failed." Do not start if any test fails.
2. Write the test first if the step has a specific assertion (not "manual").
3. Build the step. Implement only the described behavior.
4. Run all tests after building. Report count.
5. Present for review. Wait for user response.
6. If approved: mark accepted, update AGENTS.md if patterns emerged, write regression test for manual steps.
7. If changes requested: transition to rework, implement changes, re-verify.

**What triggers an AGENTS.md update:** a new file/folder pattern, a library/pattern used across two+ steps, a structural decision, an abandoned approach.

The `deliver` phase cannot exit until all work items are in terminal state (accepted, waived, or cancelled) and at least one is accepted.

### release

Restructure artifacts and verify coherence.

- Archive superseded artifacts (BUILD_PLAN.md → BUILD_PLAN.archived.md for evolution migrations)
- Verify coherence: AGENTS.md module guide covers ARCHITECTURE.md components, all decisions captured, work protocol references current plan, no orphaned references
- Run the output quality eval
- Fix any findings

Can loop back to `deliver` if restructuring reveals new work.

**Exit evidence:** Coherence check passes. Eval passes. Superseded artifacts archived.

### stabilize

Present and confirm.

Present the complete artifact set to the user:
- What changed from the old structure and why
- Current plan contents
- Key decisions
- Health issues found during assessment
- How the work protocol operates

Ask: "Does this match where the project is? Anything wrong, missing, or in the wrong bucket?"

Can loop back to `deliver` if user identifies new work.

**Exit evidence:** User confirms. Residual risks acknowledged. Final test suite passes.

### blocked

Resumable overlay. Can be entered from any active state.

Record: what is blocked, who owns resolving it, what will unblock it. The workflow resumes to exactly the state it was in before blocking, with all work-item states preserved.

### aborted

Terminal. User explicitly abandons the workflow. Record: reason, disposition of partial work (keep/archive/delete), cleanup status.

## Work-Item Submachine

Inside `deliver`, each work item has its own lifecycle:

| State | Meaning |
|---|---|
| `ready` | Defined, dependencies met, not yet started |
| `implementing` | Active development |
| `verifying` | Running tests, checking acceptance criteria |
| `reviewing` | Presented to user for evaluation |
| `accepted` | User approved |
| `blocked` | Waiting on external dependency |
| `rework` | Returned from verifying or reviewing |
| `waived` | Accepted with documented gap |
| `cancelled` | No longer relevant due to scope change |

See `references/lifecycle.md` for the complete transition table.

## Stable Identifiers

All entities get immutable IDs once assigned:

- **AC-NNN**: Acceptance criteria
- **RISK-NNN**: Risks
- **DEC-NNN**: Decisions
- **WI-NNN**: Work items
- **EVD-NNN**: Evidence entries

Reference these IDs across artifacts and in the evidence ledger. The workflow engine validates referential integrity.

## Interaction Style

- Ask one question at a time. Do not present all questions as a list.
- Push back when answers use:
  - **Category words without instances**: "all kinds of users" — ask for one specific person.
  - **Quality words without measures**: "fast," "intuitive" — ask what they would see or measure.
  - **Deferred specifics**: "it depends," "probably" — pin down one concrete case.
- Adapt pace: if prior answers already fill the template for a section, skip it. State the extracted answer and confirm.
- If the user insists on skipping discovery: respect it. Fill gaps with assumptions marked **[ASSUMED]**.
- For evolution projects: be direct about health issues. Quantify. Do not over-ceremony the migration.

## Evidence Tracking

Use `templates/evidence-ledger.md` to link transitions to their justification. Each entry documents what was observed, produced, or confirmed. Do not store long reports in the ledger — store references and hashes; keep full findings under `.workflow/evidence/`.

## Verifying Outputs

After generating or updating artifacts, run the output quality eval. Fix any FAIL findings before presenting to the user. After a session, evaluate the conversation transcript for skill compliance. Both evals are in the `evals/` directory.
