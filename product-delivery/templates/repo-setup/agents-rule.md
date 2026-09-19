## Development Workflow

This project uses the **product-delivery** lifecycle. All development
work flows through the workflow state machine.

Before starting any work:

1. Call `workflow_status` to check the current state.
2. If no workflow exists, call `workflow_init` to start one.
3. Load the `product_delivery` prompt for full skill instructions.

Rules:

- Follow the workflow transitions. Do not skip states or bypass guards.
- Use `workflow_next` to see what transitions are allowed.
- Transition work items through the submachine:
  ready → implementing → verifying → reviewing → accepted.
- Run tests before and after each work item.
- Record evidence for every transition.
- Update AGENTS.md when new patterns emerge during delivery.
