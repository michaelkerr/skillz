# Evidence Ledger

Evidence records link workflow transitions to their justification. Each entry documents what was observed, produced, or confirmed, and ties it to the state change it supports.

Do not store long reports here. Store references plus hashes; keep human-readable findings under `.workflow/evidence/`. This ledger is a lookup table, not a document.

---

### EVD-001: [Short description]

- **Type**: brief | synthesis | maturity-assessment | health-check | direction | plan | context-files | test-results | user-confirmation | coherence-check | eval-results | approval | artifact
- **Date**: YYYY-MM-DD
- **Transition**: [from] → [to]
- **Supports**: AC-NNN, DEC-NNN, RISK-NNN (as applicable)
- **Content**: [one-line summary or path to full artifact, e.g., `.workflow/evidence/health-check-2024-03-15.md`]
- **Hash**: [SHA-256 of referenced file, if applicable]

### EVD-002: [Short description]

- **Type**:
- **Date**:
- **Transition**:
- **Supports**:
- **Content**:
- **Hash**:

<!-- Evidence types:
  - brief: Project brief captured during intake/discover
  - synthesis: Product summary confirmation during frame
  - maturity-assessment: Maturity signals evaluation (evolution)
  - health-check: Codebase health analysis (evolution)
  - direction: Direction conversation outcomes (evolution)
  - plan: Delivery plan creation or update
  - context-files: AGENTS.md, CLAUDE.md, ARCHITECTURE.md, DECISIONS.md
  - test-results: Test suite execution results with counts
  - user-confirmation: Explicit user approval of state/artifacts
  - coherence-check: Cross-artifact coherence verification
  - eval-results: Output quality or skill compliance eval results
  - approval: Explicit approval for irreversible actions
  - artifact: Any other produced artifact referenced as evidence -->
