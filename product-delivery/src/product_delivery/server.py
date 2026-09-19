"""
Product Delivery MCP Server

Exposes the delivery workflow state machine as MCP tools, resources,
and prompts. Any harness that speaks MCP gets identical behavior.

Multi-project: every tool accepts an optional project_dir parameter.
When omitted, the server's startup directory is used.

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
        "Unified lifecycle server for software products. Manages a "
        "hierarchical state machine from intake through delivery and "
        "stabilization, with a nested work-item submachine. "
        "FIRST STEP: call workflow_detect to check the project state — "
        "it tells you whether to run setup, init, or resume. "
        "All tools accept an optional project_dir to target a specific "
        "project (defaults to the working directory). "
        "Read the product-delivery prompt for full skill instructions."
    ),
)

# Default project dir, set at startup. Tools use this when project_dir is omitted.
DEFAULT_PROJECT_DIR = Path.cwd()

# Locate the package's static files (references/, templates/)
PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent

# Config cache per project dir
_config_cache: dict[str, dict[str, str]] = {}


def _resolve(project_dir: str | None) -> Path:
    if project_dir:
        return Path(project_dir).resolve()
    return DEFAULT_PROJECT_DIR


def _load_env(project_dir: Path) -> dict[str, str]:
    cache_key = str(project_dir)
    if cache_key in _config_cache:
        return _config_cache[cache_key]

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

    _config_cache[cache_key] = config
    return config


def _get_config(project_dir: Path, key: str, default: str = "") -> str:
    config = _load_env(project_dir)
    return config.get(f"PRODUCT_DELIVERY_{key}", default)


def _error_response(e: Exception) -> str:
    return json.dumps({"error": type(e).__name__, "message": str(e)})


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------

@mcp.tool()
def workflow_detect(project_dir: str | None = None) -> str:
    """Detect the product-delivery state of a project.

    Call this FIRST when entering a project. Returns the current state
    and what action to take next:

    - "not_setup": No product-delivery config. Call workflow_setup to add it.
    - "setup_no_workflow": Config exists but no workflow started. Call workflow_init.
    - "active_workflow": Workflow in progress. Call workflow_status to see where it is.
    - "legacy_migration": Has BUILD_PLAN.md or ROADMAP.md from old skills.
                          Call workflow_init(from_migration=True).

    Args:
        project_dir: Project directory to check. Defaults to working directory.
    """
    p = _resolve(project_dir)

    has_workflow = (p / ".workflow" / "state.json").exists()
    has_agents_rule = False
    if (p / "AGENTS.md").exists():
        has_agents_rule = "product-delivery" in (p / "AGENTS.md").read_text()
    has_mcp_config = any(
        "product-delivery" in _read_json_safe(p / sub / f).get("mcpServers", {})
        for sub, f in [(".claude", "settings.json"), (".cursor", "mcp.json")]
    )
    has_build_plan = (p / "BUILD_PLAN.md").exists()
    has_roadmap = (p / "ROADMAP.md").exists()
    has_env = (p / ".env").exists()

    if has_workflow:
        try:
            status = engine.get_status(p)
            state = "active_workflow"
            phase = status.get("phase", "unknown")
            action = f"Workflow is in '{phase}' phase. Call workflow_status for details."
        except engine.WorkflowError:
            state = "active_workflow"
            phase = "error"
            action = "Workflow state file exists but could not be read. Check .workflow/state.json."
    elif has_build_plan or has_roadmap:
        state = "legacy_migration"
        legacy = []
        if has_build_plan:
            legacy.append("BUILD_PLAN.md")
        if has_roadmap:
            legacy.append("ROADMAP.md")
        phase = None
        action = (
            f"Found legacy artifact(s): {', '.join(legacy)}. "
            f"Call workflow_init(from_migration=True) to migrate."
        )
    elif has_mcp_config or has_agents_rule:
        state = "setup_no_workflow"
        phase = None
        action = "Project is configured but no workflow started. Call workflow_init to begin."
    else:
        state = "not_setup"
        phase = None
        action = (
            "No product-delivery config found. Call workflow_setup(dry_run=True) "
            "to preview setup, then workflow_setup(dry_run=False) to apply."
        )

    return json.dumps({
        "project_dir": str(p),
        "project_name": p.name,
        "state": state,
        "phase": phase,
        "action": action,
        "details": {
            "has_workflow": has_workflow,
            "has_mcp_config": has_mcp_config,
            "has_agents_rule": has_agents_rule,
            "has_env": has_env,
            "has_build_plan": has_build_plan,
            "has_roadmap": has_roadmap,
        },
    }, indent=2)


def _read_json_safe(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def workflow_init(
    project_type: str | None = None,
    from_migration: bool = False,
    project_dir: str | None = None,
) -> str:
    """Initialize a new delivery workflow in the project directory.

    Args:
        project_type: "greenfield" or "evolution". Leave empty to determine during intake.
                      Can be defaulted via PRODUCT_DELIVERY_PROJECT_TYPE in .env.
        from_migration: Detect existing BUILD_PLAN.md or ROADMAP.md and migrate.
        project_dir: Project directory. Defaults to working directory.
    """
    p = _resolve(project_dir)
    try:
        if project_type is None:
            project_type = _get_config(p, "PROJECT_TYPE") or None
        result = engine.init_workflow(p, project_type, from_migration)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_status(project_dir: str | None = None) -> str:
    """Get the current workflow state, work items, and recent events.

    Args:
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.get_status(_resolve(project_dir))
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_next(project_dir: str | None = None) -> str:
    """Show allowed transitions from the current state with guard status.

    Returns which states can be reached and whether each guard passes,
    so the agent can decide what to do next.

    Args:
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.get_next_transitions(_resolve(project_dir))
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_transition(
    target: str,
    evidence: list[str] | None = None,
    force: bool = False,
    reason: str | None = None,
    project_dir: str | None = None,
) -> str:
    """Attempt a state transition. Guards are checked automatically.

    Args:
        target: Target state (e.g. "discover", "frame", "plan", "deliver").
        evidence: Evidence keys to attach to this transition.
        force: Force past failed guards (logged as forced).
        reason: Human-readable reason for the transition.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.do_transition(_resolve(project_dir), target, evidence, force, reason)
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
    project_dir: str | None = None,
) -> str:
    """Add a work item to the delivery plan.

    Only valid in plan or deliver phase. The item starts in "ready" state.

    Args:
        name: Work item name/description.
        acceptance_criteria: AC-NNN IDs this item satisfies.
        risks: RISK-NNN IDs associated with this item.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.add_item(_resolve(project_dir), name, acceptance_criteria, risks)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_list(
    state_filter: str | None = None,
    project_dir: str | None = None,
) -> str:
    """List all work items, optionally filtered by state.

    Args:
        state_filter: Only show items in this state (e.g. "ready", "implementing").
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.list_items(_resolve(project_dir), state_filter)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_transition(
    item_id: str,
    target: str,
    reason: str | None = None,
    project_dir: str | None = None,
) -> str:
    """Transition a work item to a new state.

    Valid transitions: ready->implementing, implementing->verifying,
    verifying->reviewing, verifying->rework, reviewing->accepted,
    reviewing->rework, rework->implementing. Any item can be cancelled.

    Args:
        item_id: Work item ID (WI-NNN).
        target: Target state.
        reason: Reason for the transition.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.transition_item(_resolve(project_dir), item_id, target, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_item_waive(
    item_id: str,
    approver: str,
    reason: str,
    project_dir: str | None = None,
) -> str:
    """Waive a work item that is in reviewing state.

    Requires explicit approver and reason. The item moves to "waived"
    terminal state and counts toward the completion guard.

    Args:
        item_id: Work item ID (WI-NNN).
        approver: Who approved the waiver.
        reason: Why the item is being waived.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.waive_item(_resolve(project_dir), item_id, approver, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_check(project_dir: str | None = None) -> str:
    """Run guard checks for all available transitions from the current state.

    Returns which transitions are ready (all guards pass) and which are
    blocked, with per-guard status.

    Args:
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.check_guards(_resolve(project_dir))
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_block(
    reason: str,
    owner: str,
    project_dir: str | None = None,
) -> str:
    """Block the workflow. Records the current phase as the resume target.

    Args:
        reason: Why the workflow is blocked.
        owner: Who is responsible for resolving the blocker.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.block_workflow(_resolve(project_dir), reason, owner)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_resume(
    reason: str | None = None,
    project_dir: str | None = None,
) -> str:
    """Resume a blocked workflow back to its pre-blocked phase.

    Args:
        reason: Why the blocker is resolved.
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.resume_workflow(_resolve(project_dir), reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_waive_guard(
    guard: str,
    approver: str,
    reason: str,
    project_dir: str | None = None,
) -> str:
    """Waive a transition guard so the transition can proceed.

    The waiver is recorded with the approver and reason. The guard
    will show as "waived" instead of "fail" on subsequent checks.

    Args:
        guard: Guard name to waive (from workflow_check results).
        approver: Who approved the waiver.
        reason: Why the guard is being waived (risk accepted).
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.waive_guard(_resolve(project_dir), guard, approver, reason)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_close(
    reason: str | None = None,
    force: bool = False,
    project_dir: str | None = None,
) -> str:
    """Close the workflow (normally from stabilize phase).

    Args:
        reason: Reason for closing.
        force: Close from a non-stabilize phase (logged as forced).
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        result = engine.close_workflow(_resolve(project_dir), reason, force)
        return json.dumps(result, indent=2)
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_render(project_dir: str | None = None) -> str:
    """Render a human-readable markdown summary of the workflow status.

    Args:
        project_dir: Project directory. Defaults to working directory.
    """
    try:
        return engine.render_status(_resolve(project_dir))
    except engine.WorkflowError as e:
        return _error_response(e)


@mcp.tool()
def workflow_config(project_dir: str | None = None) -> str:
    """Show the active configuration from .env and environment variables.

    Returns all PRODUCT_DELIVERY_* settings and where they came from.

    Args:
        project_dir: Project directory. Defaults to working directory.
    """
    p = _resolve(project_dir)
    config = _load_env(p)
    return json.dumps({
        "project_dir": str(p),
        "config": config,
        "env_file": str(p / ".env"),
        "env_file_exists": (p / ".env").exists(),
    }, indent=2)


@mcp.tool()
def workflow_setup(
    dry_run: bool = True,
    project_dir: str | None = None,
) -> str:
    """Set up product-delivery in a project.

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
        project_dir: Project directory. Defaults to working directory.
    """
    from . import setup

    p = _resolve(project_dir)

    if dry_run:
        result = setup.plan_setup(p)
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
        result = setup.execute_setup(p)
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
    state_path = DEFAULT_PROJECT_DIR / ".workflow" / "state.json"
    if state_path.exists():
        return state_path.read_text()
    return '{"error": "No workflow initialized"}'


@mcp.resource("workflow://events")
def resource_events() -> str:
    """Workflow event log (events.jsonl contents)."""
    events_path = DEFAULT_PROJECT_DIR / ".workflow" / "events.jsonl"
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
    global DEFAULT_PROJECT_DIR
    if project_dir:
        DEFAULT_PROJECT_DIR = project_dir
    mcp.run()
