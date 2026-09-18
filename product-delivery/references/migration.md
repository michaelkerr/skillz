# Migration from Legacy Skills

This document covers migrating projects that use product-discovery (BUILD_PLAN.md) or product-evolution (ROADMAP.md) to the unified product-delivery workflow.

## Detection

Run `workflow init --from-migration` in the project directory. The CLI detects legacy artifacts:

| Artifact | Source Skill | Detected As |
|---|---|---|
| `BUILD_PLAN.md` | product-discovery | greenfield migration |
| `ROADMAP.md` | product-evolution | evolution migration |
| Both present | mixed | evolution migration (takes precedence) |
| Neither present | none | fresh init (no migration) |

## Migration from product-discovery

### Artifacts Mapped

| Legacy Artifact | New Location | Action |
|---|---|---|
| `BUILD_PLAN.md` | `.workflow/` work items + `templates/plan.md` | Parse steps into WI-NNN work items |
| `AGENTS.md` | Preserved as-is | Will be evolved during plan or release phase |
| `CLAUDE.md` | Preserved as-is | No change needed |

### State Inference

The CLI infers the workflow phase from BUILD_PLAN.md content:

- If no steps are complete → `plan` (the plan exists but work hasn't started)
- If some steps are complete and some remain → `deliver` (work is in progress)
- If all steps are complete → `release` (ready for restructuring)

### Step-to-Work-Item Mapping

Each `### Step N: [Name]` in BUILD_PLAN.md becomes a work item:

| BUILD_PLAN.md Field | state.json Field |
|---|---|
| Step name | `work_items.WI-NNN.name` |
| Status: "not started" | `state: "ready"` |
| Status: "in progress" | `state: "implementing"` |
| Status: "complete" | `state: "accepted"` |
| Test field | Preserved as evidence |
| Builds on | `depends_on` (mapped to WI-NNN refs) |

### Product Summary Extraction

If a Product Summary section exists in the conversation or BUILD_PLAN.md:

- Problem → `brief.problem`
- User → `brief.who`
- Core interaction → `brief.core_interaction`
- Success criteria → `acceptance_criteria[]` with AC-NNN IDs
- Constraints → `brief.constraints`

## Migration from product-evolution

### Artifacts Mapped

| Legacy Artifact | New Location | Action |
|---|---|---|
| `ROADMAP.md` | `.workflow/` work items + `templates/plan.md` (evolution format) | Parse buckets into work items |
| `AGENTS.md` (evolved) | Preserved as-is | Already in evolved format |
| `ARCHITECTURE.md` | Preserved as-is | Referenced as evidence |
| `DECISIONS.md` | Preserved as-is; entries get DEC-NNN IDs | Decisions mapped to state |
| `BUILD_PLAN.archived.md` | Preserved as-is | Historical record |

### Roadmap-to-Work-Item Mapping

| ROADMAP.md Bucket | Work Item State |
|---|---|
| NOW items (in progress) | `implementing` |
| NOW items (not started) | `ready` |
| NEXT items | Not yet work items (noted in plan for later promotion) |
| LATER items | Not yet work items |
| PARKED items | Not yet work items |

### State Inference

- If ROADMAP.md has NOW items in progress → `deliver`
- If ROADMAP.md exists but no items started → `plan`
- If the evolution skill completed Phase 5 (confirmation) → `stabilize`

## Migration Event

The CLI logs a migration event:

```json
{
  "type": "migrate",
  "from_state": null,
  "to_state": "[inferred phase]",
  "reason": "Migrated from [product-discovery|product-evolution]",
  "data": {
    "migrated_from": "[skill name]",
    "legacy_artifacts": ["BUILD_PLAN.md", "AGENTS.md"],
    "items_migrated": 8,
    "items_completed": 5
  }
}
```

## Post-Migration

After migration:

1. The legacy artifacts remain in place. They are not deleted or modified.
2. `.workflow/state.json` is the new source of truth for workflow state.
3. The delivery plan artifact (BUILD_PLAN.md or ROADMAP.md) continues to serve as the human-readable plan, but status tracking moves to `.workflow/state.json`.
4. The agent should read `references/lifecycle.md` to understand valid transitions from the inferred state.
5. Legacy eval scripts (`eval_output_quality.py`, `eval_evolution_quality.py`) still validate their respective artifacts during the transition period.

## Backward Compatibility

- Projects can continue using legacy skills until they choose to migrate. The deprecation notices in product-discovery and product-evolution point to this migration path.
- A project cannot have both a legacy skill and product-delivery active simultaneously. The presence of `.workflow/state.json` indicates product-delivery is active.
- To revert a migration, delete the `.workflow/` directory. The legacy artifacts remain untouched.
