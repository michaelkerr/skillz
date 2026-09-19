"""Project setup — wire up product-delivery in a repo.

Called via:
    - MCP tool: workflow_setup (from within a harness conversation)
    - CLI: product-delivery setup
    - Standalone: python scripts/setup
"""

import json
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MCP_SERVER_CONFIG = {
    "command": "uvx",
    "args": ["product-delivery"],
}

AGENTS_RULE = """\
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
"""

ENV_SAMPLE = """\
# Product Delivery Configuration
# Copy to .env and customize. Do not commit .env to version control.
#
# All variables are prefixed PRODUCT_DELIVERY_ and are optional.
# Precedence: environment variables > .env file > defaults.

# Default project type for workflow init (greenfield or evolution).
# Leave blank to determine during intake conversation.
# PRODUCT_DELIVERY_PROJECT_TYPE=greenfield

# Guard enforcement mode:
#   strict - guards must pass or be explicitly waived (default)
#   warn   - log failures but allow transitions
#   skip   - disable guard checks entirely
# PRODUCT_DELIVERY_GUARD_MODE=strict

# Comma-separated states to skip during init (only discover and frame
# are skippable). Useful for small projects that don't need full discovery.
# PRODUCT_DELIVERY_SKIP_STATES=
"""

GITIGNORE_LINES = [".env", ".workflow/"]
MARKER = "product-delivery** lifecycle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Setup steps — each returns a dict describing what it did/would do
# ---------------------------------------------------------------------------

def _check_mcp_config(project: Path, subdir: str, filename: str) -> dict:
    config_path = project / subdir / filename
    existing = _read_json(config_path)
    servers = existing.get("mcpServers", {})

    if "product-delivery" in servers:
        return {"file": f"{subdir}/{filename}", "action": "skip",
                "detail": "already configured"}

    action = "update" if config_path.exists() else "create"
    other_servers = [k for k in servers if k != "product-delivery"]
    return {"file": f"{subdir}/{filename}", "action": action,
            "detail": f"add product-delivery server"
                       + (f" (alongside {', '.join(other_servers)})" if other_servers else "")}


def _apply_mcp_config(project: Path, subdir: str, filename: str):
    config_path = project / subdir / filename
    existing = _read_json(config_path)
    servers = existing.get("mcpServers", {})
    servers["product-delivery"] = MCP_SERVER_CONFIG.copy()
    if subdir == ".cursor":
        servers["product-delivery"]["envFile"] = "${workspaceFolder}/.env"
    existing["mcpServers"] = servers
    _write_json(config_path, existing)


def _check_agents_md(project: Path) -> dict:
    agents_path = project / "AGENTS.md"
    if agents_path.exists():
        if MARKER in agents_path.read_text():
            return {"file": "AGENTS.md", "action": "skip",
                    "detail": "workflow rule already present"}
        return {"file": "AGENTS.md", "action": "update",
                "detail": "append workflow rule to existing file"}
    return {"file": "AGENTS.md", "action": "create",
            "detail": "create with workflow rule"}


def _apply_agents_md(project: Path):
    agents_path = project / "AGENTS.md"
    if agents_path.exists():
        with open(agents_path, "a") as f:
            f.write("\n\n" + AGENTS_RULE)
    else:
        agents_path.write_text(f"# {project.name}\n\n{AGENTS_RULE}")


def _check_env(project: Path) -> list[dict]:
    results = []
    if not (project / ".env.sample").exists():
        results.append({"file": ".env.sample", "action": "create",
                        "detail": "configuration template"})
    else:
        results.append({"file": ".env.sample", "action": "skip",
                        "detail": "already exists"})

    if not (project / ".env").exists():
        results.append({"file": ".env", "action": "create",
                        "detail": "local config (gitignored)"})
    else:
        results.append({"file": ".env", "action": "skip",
                        "detail": "already exists"})
    return results


def _apply_env(project: Path):
    if not (project / ".env.sample").exists():
        (project / ".env.sample").write_text(ENV_SAMPLE)
    if not (project / ".env").exists():
        (project / ".env").write_text(ENV_SAMPLE)


def _check_gitignore(project: Path) -> dict:
    gi_path = project / ".gitignore"
    existing = gi_path.read_text().splitlines() if gi_path.exists() else []
    missing = [l for l in GITIGNORE_LINES if l not in existing]
    if not missing:
        return {"file": ".gitignore", "action": "skip",
                "detail": "entries already present"}
    return {"file": ".gitignore", "action": "update",
            "detail": f"add {', '.join(missing)}"}


def _apply_gitignore(project: Path):
    gi_path = project / ".gitignore"
    existing = gi_path.read_text().splitlines() if gi_path.exists() else []
    missing = [l for l in GITIGNORE_LINES if l not in existing]
    if missing:
        with open(gi_path, "a") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("\n".join(missing) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan_setup(project: Path) -> dict:
    """Preview what setup would do without making changes.

    Returns a structured plan the agent can present to the user.
    """
    steps = []
    steps.append(_check_mcp_config(project, ".claude", "settings.json"))
    steps.append(_check_mcp_config(project, ".cursor", "mcp.json"))
    steps.append(_check_agents_md(project))
    steps.extend(_check_env(project))
    steps.append(_check_gitignore(project))

    changes = [s for s in steps if s["action"] != "skip"]
    unchanged = [s for s in steps if s["action"] == "skip"]

    has_workflow = (project / ".workflow" / "state.json").exists()

    return {
        "project_dir": str(project),
        "project_name": project.name,
        "steps": steps,
        "changes_count": len(changes),
        "unchanged_count": len(unchanged),
        "has_existing_workflow": has_workflow,
        "already_setup": len(changes) == 0,
    }


def execute_setup(project: Path) -> dict:
    """Run setup — create/update all config files.

    Returns a structured result of what was done.
    """
    results = []

    for subdir, filename in [(".claude", "settings.json"), (".cursor", "mcp.json")]:
        check = _check_mcp_config(project, subdir, filename)
        if check["action"] != "skip":
            _apply_mcp_config(project, subdir, filename)
            check["applied"] = True
        results.append(check)

    check = _check_agents_md(project)
    if check["action"] != "skip":
        _apply_agents_md(project)
        check["applied"] = True
    results.append(check)

    for env_check in _check_env(project):
        results.append(env_check)
    _apply_env(project)

    check = _check_gitignore(project)
    if check["action"] != "skip":
        _apply_gitignore(project)
        check["applied"] = True
    results.append(check)

    applied = [r for r in results if r.get("applied")]
    skipped = [r for r in results if r["action"] == "skip"]

    has_workflow = (project / ".workflow" / "state.json").exists()

    return {
        "project_dir": str(project),
        "project_name": project.name,
        "results": results,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "has_existing_workflow": has_workflow,
        "next_steps": (
            ["Run workflow_init to start the delivery workflow",
             "Load the product_delivery prompt for skill instructions"]
            if not has_workflow else
            ["Run workflow_status to check current state",
             "Load the product_delivery prompt to resume"]
        ),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_setup(project: Path):
    """CLI-friendly setup with printed output."""
    print(f"\n  Product Delivery Setup")
    print(f"  Project: {project}\n")

    if not shutil.which("uv") and not shutil.which("uvx"):
        print("  ! uv/uvx not found. Install: https://docs.astral.sh/uv/\n")

    result = execute_setup(project)

    for r in result["results"]:
        symbol = {"create": "+", "update": "~", "skip": "·"}
        s = symbol.get(r["action"], " ")
        msg = f"  {s} {r['file']}"
        if r.get("detail"):
            msg += f"  ({r['detail']})"
        print(msg)

    print(f"\n  Done: {result['applied_count']} changed, "
          f"{result['skipped_count']} unchanged.")

    if result["applied_count"]:
        print("\n  Next steps:")
        print("    1. Review .env and uncomment settings you want")
        print("    2. Commit .env.sample, .claude/, .cursor/, AGENTS.md")
        print("    3. Open the project in Claude Code or Cursor")
        print("    4. The agent will see the MCP server and follow the workflow")

    print()
