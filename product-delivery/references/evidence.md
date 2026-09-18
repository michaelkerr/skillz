# Evidence Types and Linking Rules

Evidence connects transitions to their justification. Every state transition should reference at least one evidence entry. This document catalogs the evidence types, what produces them, and how they link to stable IDs.

## Evidence Types

| Type | What It Contains | Produced During | Consumed By |
|---|---|---|---|
| `brief` | Project brief fields (who, problem, core interaction) | intake, discover | frame, plan |
| `synthesis` | Confirmed product summary or direction | frame | plan |
| `maturity-assessment` | Maturity signal evaluation results | discover (evolution) | frame |
| `health-check` | Test coverage, tech debt, dead code, architecture strain | discover (evolution) | plan, deliver |
| `direction` | What's working, what's next, what's dragging | frame (evolution) | plan |
| `plan` | Delivery plan artifact | plan | deliver |
| `context-files` | AGENTS.md, CLAUDE.md, ARCHITECTURE.md, DECISIONS.md | plan | deliver, release |
| `test-results` | Test suite execution with pass/fail counts | deliver, release, stabilize | deliver (next item), release |
| `user-confirmation` | Explicit user approval of state or artifacts | frame, plan, stabilize | transition guards |
| `coherence-check` | Cross-artifact consistency verification | release | stabilize |
| `eval-results` | Output quality or skill compliance eval output | plan, release | stabilize |
| `approval` | Explicit approval for irreversible actions | any | transition guards |
| `artifact` | Any other produced artifact | any | evidence index |

## Evidence Record Format

Each evidence entry in `state.json.evidence_index`:

```json
{
  "key": "EVD-001",
  "type": "test-results",
  "path": ".workflow/evidence/test-run-2024-03-15.txt",
  "hash": "sha256:a1b2c3...",
  "timestamp": "2024-03-15T14:30:00Z"
}
```

## Linking Rules

Evidence links to stable IDs using these conventions:

- **Acceptance criteria**: An evidence entry that demonstrates AC-NNN lists it in the event's `evidence_keys` as `AC-NNN:EVD-NNN`.
- **Risks**: Evidence of risk mitigation uses `RISK-NNN:EVD-NNN`.
- **Decisions**: Evidence supporting a decision uses `DEC-NNN:EVD-NNN`.
- **Work items**: Evidence for a work item transition uses `WI-NNN:EVD-NNN`.

## Storage

- Evidence metadata goes in `state.json.evidence_index`.
- Short evidence (under 500 chars) can be inline in the event's `data` field.
- Longer evidence goes in `.workflow/evidence/` as separate files.
- The evidence ledger (`templates/evidence-ledger.md`) provides a human-readable index.

## Hashing

When an evidence entry references a file, compute its SHA-256 hash at recording time and store it in the `hash` field. The CLI's `check` command can verify that evidence files have not been modified since recording.

## Referential Integrity

The CLI validates:
- Every transition event references at least one evidence key (warning, not blocking).
- Every evidence key in an event corresponds to an entry in `evidence_index`.
- Every AC-NNN, RISK-NNN, DEC-NNN referenced in evidence exists in the state.
- Evidence file paths resolve to existing files.
