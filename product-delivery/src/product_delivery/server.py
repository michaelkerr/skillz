"""
Product Delivery MCP Server

Exposes the delivery workflow state machine as MCP tools, resources,
and prompts. Any harness that speaks MCP gets identical behavior.

Configuration via .env in the project directory (or PRODUCT_DELIVERY_*
environment variables):

    PRODUCT_DELIVERY_PROJECT_TYPE=greenfield|evolution
    PRODUCT_DELIVERY_GUARD_MODE=strict|warn|skip
    PRODUCT_DELIVERY_SKIP_STATES=discover,frame
"""

import json
import os
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP as MCPServer
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer

from . import engine

mcp = MCPServer(
    "product-delivery",
    version="1.0.0",
    instructions=(
        "Unified lifecycle server for software products. Provides tools to "
        "manage a hierarchical state machine from intake through delivery and "
        "stabilization, with a nested work-item submachine. "
        "To set up a new project: call workflow_setup(dry_run=True) to preview, "
        "then workflow_setup(dry_run=False) to apply, then workflow_init to start. "
        "Read the product-delivery prompt for conversational skill instructions."
    ),
)

# Resolved at startup; overridable via --project-dir
PROJECT_DIR = Path.cwd()

# Locate the package's static files (references/, templates/)
PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent

# Server config loaded from .env / environment
CONFIG: dict[str, str] = {}


def _load_env(project_dir: Path) -> dict[str, str]:
    """Load config from .env file and environment variables.

    Precedence: env vars > .env file > defaults.
    """
    config: dict[str, str] = {}

    env_file = project_dir / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key.startswith("PRODUCT_DELIVERY_"):
                    config[key] = value

    for key, value in os.environ.items():
        if key.startswith("PRODUCT_DELIVERY_"):
            config[key] = value

    return config


def _get_config(key: str, default: str = "") -> str:
    return CONFIG.get(f"PRODUCT_DELIVERY_{key}", default)


def _error_response(e: Exception) -> str:
    return json.dumps({"error": type(e).__name__, "message": str(e)})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def workflow_init(
    project_type: str | None = None,
    from_migration: bool = False,
) -> str:
    """Initialize a new delivery workflow in the project directory.

    Args:
        project_type: "greenfield" or "evolution". Leave empty to determine during intake.
                      Can be defaulted via PRODUCT_DELIVERY_PROJECT_TYPE in .env.
        from_migration: Detect existing BUILD_PLAN.md or ROADMAP.md and migrate.
    """
    try:
        if project_type is None:
            project_type = _get_config("PROJECT_TYPE") or None
        result = engine.init_workflow(PROJECT_DIR, project_type, from_migration)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_status() -> str:
    """Get the current workflow state, work items, and recent events."""
    try:
        result = engine.get_status(PROJECT_DIR)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_next() -> str:
    """Show allowed transitions from the current state with guard status.

    Returns which states can be reached and whether each guard passes,
    so the agent can decide what to do next.
    """
    try:
        result = engine.get_next_transitions(PROJECT_DIR)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_transition(
    target: str,
    evidence: list[str] | None = None,
    force: bool = False,
    reason: str | None = None,
) -> str:
    """Attempt a state transition. Guards are checked automatically.

    Args:
        target: Target state (e.g. "discover", "frame", "plan", "deliver").
        evidence: Evidence keys to attach to this transition.
        force: Force past failed guards (logged as forced).
        reason: Human-readable reason for the transition.
    """
    try:
        result = engine.do_transition(PROJECT_DIR, target, evidence, force, reason)
        return json.dumps(result, indent=2)
    except engine.GuardFailedError as e:
        return json.dumps({
            "error": "GuardFailedError",
            "message": str(e),
            "guard_results": e.guard_results,
        })
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_add(
    name: str,
    acceptance_criteria: list[str] | None = None,
    risks: list[str] | None = None,
) -> str:
    """Add a work item to the delivery plan.

    Only valid in plan or deliver phase. The item starts in "ready" state.

    Args:
        name: Work item name/description.
        acceptance_criteria: AC-NNN IDs this item satisfies.
        risks: RISK-NNN IDs associated with this item.
    """
    try:
        result = engine.add_item(PROJECT_DIR, name, acceptance_criteria, risks)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_list(state_filter: str | None = None) -> str:
    """List all work items, optionally filtered by state.

    Args:
        state_filter: Only show items in this state (e.g. "ready", "implementing").
    """
    try:
        result = engine.list_items(PROJECT_DIR, state_filter)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_transition(
    item_id: str,
    target: str,
    reason: str | None = None,
) -> str:
    """Transition a work item to a new state.

    Valid transitions: ready→implementing, implementing→verifying,
    verifying→reviewing, verifying→rework, reviewing→accepted,
    reviewing→rework, rework→implementing. Any item can be cancelled.

    Args:
        item_id: Work item ID (WI-NNN).
        target: Target state.
        reason: Reason for the transition.
    """
    try:
        result = engine.transition_item(PROJECT_DIR, item_id, target, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_waive(
    item_id: str,
    approver: str,
    reason: str,
) -> str:
    """Waive a work item that is in reviewing state.

    Requires explicit approver and reason. The item moves to "waived"
    terminal state and counts toward the completion guard.

    Args:
        item_id: Work item ID (WI-NNN).
        approver: Who approved the waiver.
        reason: Why the item is being waived.
    """
    try:
        result = engine.waive_item(PROJECT_DIR, item_id, approver, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_check() -> str:
    """Run guard checks for all available transitions from the current state.

    Returns which transitions are ready (all guards pass) and which are
    blocked, with per-guard status.
    """
    try:
        result = engine.check_guards(PROJECT_DIR)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_block(reason: str, owner: str) -> str:
    """Block the workflow. Records the current phase as the resume target.

    Args:
        reason: Why the workflow is blocked.
        owner: Who is responsible for resolving the blocker.
    """
    try:
        result = engine.block_workflow(PROJECT_DIR, reason, owner)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_resume(reason: str | None = None) -> str:
    """Resume a blocked workflow back to its pre-blocked phase.

    Args:
        reason: Why the blocker is resolved.
    """
    try:
        result = engine.resume_workflow(PROJECT_DIR, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_waive_guard(
    guard: str,
    approver: str,
    reason: str,
) -> str:
    """Waive a transition guard so the transition can proceed.

    The waiver is recorded with the approver and reason. The guard
    will show as "waived" instead of "fail" on subsequent checks.

    Args:
        guard: Guard name to waive (from workflow_check results).
        approver: Who approved the waiver.
        reason: Why the guard is being waived (risk accepted).
    """
    try:
        result = engine.waive_guard(PROJECT_DIR, guard, approver, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_close(reason: str | None = None, force: bool = False) -> str:
    """Close the workflow (normally from stabilize phase).

    Args:
        reason: Reason for closing.
        force: Close from a non-stabilize phase (logged as forced).
    """
    try:
        result = engine.close_workflow(PROJECT_DIR, reason, force)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_render() -> str:
    """Render a human-readable markdown summary of the workflow status."""
    try:
        return engine.render_status(PROJECT_DIR)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_config() -> str:
    """Show the active configuration from .env and environment variables.

    Returns all PRODUCT_DELIVERY_* settings and where they came from.
    """
    return json.dumps({
        "project_dir": str(PROJECT_DIR),
        "config": CONFIG,
        "env_file": str(PROJECT_DIR / ".env"),
        "env_file_exists": (PROJECT_DIR / ".env").exists(),
    }, indent=2)


@mcp.tool()
def workflow_setup(dry_run: bool = True) -> str:
    """Set up product-delivery in the current project.

    Creates or updates: .claude/settings.json, .cursor/mcp.json,
    AGENTS.md (workflow rule), .env.sample, .env, and .gitignore.
    Merges into existing files without clobbering other settings.
    Idempotent — safe to run multiple times.

    Call with dry_run=True first to preview changes, then with
    dry_run=False to apply them. Present the preview to the user
    before applying.

    Args:
        dry_run: If True, preview what would change without writing.
                 If False, apply the changes.
    """
    from . import setup

    if dry_run:
        result = setup.plan_setup(PROJECT_DIR)
        result["mode"] = "preview"
        if result["already_setup"]:
            result["message"] = "Project is already set up for product-delivery. No changes needed."
        else:
            result["message"] = (
                f"Setup will make {result['changes_count']} change(s) to "
                f"{result['project_name']}. Call workflow_setup(dry_run=False) "
                f"to apply."
            )
    else:
        result = setup.execute_setup(PROJECT_DIR)
        result["mode"] = "applied"
        result["message"] = (
            f"Setup complete. {result['applied_count']} file(s) changed. "
            + (" ".join(result["next_steps"]))
        )

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

def _read_package_file(rel_path: str) -> str:
    full = PACKAGE_ROOT / rel_path
    if full.exists():
        return full.read_text()
    return f"File not found: {rel_path}"


@mcp.resource("workflow://state")
def resource_state() -> str:
    """Current workflow state (state.json contents)."""
    state_path = PROJECT_DIR / ".workflow" / "state.json"
    if state_path.exists():
        return state_path.read_text()
    return '{"error": "No workflow initialized"}'


@mcp.resource("workflow://events")
def resource_events() -> str:
    """Workflow event log (events.jsonl contents)."""
    events_path = PROJECT_DIR / ".workflow" / "events.jsonl"
    if events_path.exists():
        return events_path.read_text()
    return ""


@mcp.resource("workflow://template/brief")
def resource_template_brief() -> str:
    """Project brief template."""
    return _read_package_file("templates/brief.md")


@mcp.resource("workflow://template/plan")
def resource_template_plan() -> str:
    """Delivery plan template (greenfield sequenced steps / evolution priority buckets)."""
    return _read_package_file("templates/plan.md")


@mcp.resource("workflow://template/evidence-ledger")
def resource_template_evidence() -> str:
    """Evidence tracking template."""
    return _read_package_file("templates/evidence-ledger.md")


@mcp.resource("workflow://reference/lifecycle")
def resource_ref_lifecycle() -> str:
    """Full state machine specification and transition table."""
    return _read_package_file("references/lifecycle.md")


@mcp.resource("workflow://reference/guards")
def resource_ref_guards() -> str:
    """Guard catalog for every transition."""
    return _read_package_file("references/guards.md")


@mcp.resource("workflow://reference/evidence")
def resource_ref_evidence() -> str:
    """Evidence types and linking rules."""
    return _read_package_file("references/evidence.md")


@mcp.resource("workflow://reference/harness-compatibility")
def resource_ref_compat() -> str:
    """Capability matrix across AI coding harnesses."""
    return _read_package_file("references/harness-compatibility.md")


@mcp.resource("workflow://reference/migration")
def resource_ref_migration() -> str:
    """Migration guide from BUILD_PLAN.md / ROADMAP.md."""
    return _read_package_file("references/migration.md")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def product_delivery() -> str:
    """Load the product-delivery conversational skill instructions.

    This prompt provides the agent with the full conversational skill:
    how to run discovery, when to push back, pacing rules, evidence
    types, and interaction style. Load it into context when starting
    or resuming a product delivery workflow.
    """
    return _read_package_file("SKILL.md")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(project_dir: Path | None = None):
    global PROJECT_DIR, CONFIG
    if project_dir:
        PROJECT_DIR = project_dir
    CONFIG = _load_env(PROJECT_DIR)
    mcp.run()
