# Delivery Plan

## Summary

[One paragraph: who, what problem, core value proposition. For evolution: what the product IS now.]

---

<!-- Select the format that matches the project type in .workflow/state.json -->

<!-- ============================================ -->
<!-- GREENFIELD FORMAT: Sequenced build steps      -->
<!-- ============================================ -->

## Steps

### Step 1: [Name]

- **ID**: WI-001
- **Status**: ready | implementing | verifying | reviewing | accepted
- **What it does**: [one sentence, one user-visible behavior]
- **What good looks like**: [specific input → specific output example]
- **Acceptance criteria**: AC-001
- **Test**: [assertion: "Given X, output should be Y" | manual]
- **Depends on**: [nothing | WI-NNN]
- **Risks**: RISK-NNN
- **Notes**: [filled after completion: patterns established, unexpected complexity, scope changes]

### Step 2: [Name]

- **ID**: WI-002
- **Status**: ready
- **What it does**: [one sentence, one behavior]
- **What good looks like**: [example]
- **Acceptance criteria**: AC-002
- **Test**: [assertion | manual]
- **Depends on**: WI-001
- **Risks**:
- **Notes**:

<!-- Sequencing principles:
  1. Core interaction first — the thing that makes the product the product
  2. Each step is independently evaluable
  3. Each step builds on the prior working state
  4. Defer infrastructure (auth, deployment, CI, database setup)
  5. One behavior per step — if "What it does" contains "and" joining two behaviors, split it
  6. More granularity where the hard part is
  Typical range: 5-12 steps. Over 15 means the scope is too large. -->

<!-- ============================================ -->
<!-- EVOLUTION FORMAT: Priority-bucketed items      -->
<!-- ============================================ -->

<!-- ## What's Built

[3-8 bullets of current capabilities]

## Now

### [Item name]

- **ID**: WI-001
- **Type**: feature | fix | debt | improvement | infrastructure
- **Status**: ready | implementing | verifying | reviewing | accepted
- **What it does**: [one sentence]
- **Done when**: [testable outcome]
- **Acceptance criteria**: AC-001
- **Touches**: [files/modules affected]
- **Risk**: RISK-NNN
- **Notes**:

## Next

- **WI-NNN [Item name]** (type): [one sentence description]
- **WI-NNN [Item name]** (type): [one sentence description]

## Later

- **[Item name]**: [why it matters, when it might become relevant]

## Parked

- **[Item name]**: [why it is parked] -->
