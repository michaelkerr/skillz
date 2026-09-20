"""Tests for MCP server tools — verifies tools return valid JSON and handle errors."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from product_delivery import server, engine


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "test-project"
    p.mkdir()
    return p


@pytest.fixture
def initialized(project):
    engine.init_workflow(project)
    return project


@pytest.fixture(autouse=True)
def reset_default_dir(tmp_path):
    original = server.DEFAULT_PROJECT_DIR
    server.DEFAULT_PROJECT_DIR = tmp_path / "default-project"
    server.DEFAULT_PROJECT_DIR.mkdir()
    yield
    server.DEFAULT_PROJECT_DIR = original


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class TestDetect:
    def test_not_setup(self, project):
        result = json.loads(server.workflow_detect(str(project)))
        assert result["state"] == "not_setup"
        assert "workflow_setup" in result["action"]

    def test_setup_no_workflow(self, project):
        claude_dir = project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "mcpServers": {"product-delivery": {"command": "uvx", "args": ["product-delivery"]}}
        }))
        result = json.loads(server.workflow_detect(str(project)))
        assert result["state"] == "setup_no_workflow"

    def test_active_workflow(self, initialized):
        result = json.loads(server.workflow_detect(str(initialized)))
        assert result["state"] == "active_workflow"
        assert result["phase"] == "intake"

    def test_legacy_migration(self, project):
        (project / "BUILD_PLAN.md").write_text("# Build Plan\n")
        result = json.loads(server.workflow_detect(str(project)))
        assert result["state"] == "legacy_migration"
        assert "BUILD_PLAN.md" in result["action"]


# ---------------------------------------------------------------------------
# Init / Status / Next
# ---------------------------------------------------------------------------

class TestCoreTools:
    def test_init(self, project):
        result = json.loads(server.workflow_init(project_dir=str(project)))
        assert result["phase"] == "intake"
        assert "workflow_id" in result

    def test_init_duplicate_returns_error(self, initialized):
        result = json.loads(server.workflow_init(project_dir=str(initialized)))
        assert result["error"] == "WorkflowExistsError"

    def test_status(self, initialized):
        result = json.loads(server.workflow_status(str(initialized)))
        assert result["phase"] == "intake"
        assert "work_items_summary" in result

    def test_next(self, initialized):
        result = json.loads(server.workflow_next(str(initialized)))
        assert result["current"] == "intake"
        assert len(result["allowed"]) > 0

    def test_transition(self, initialized):
        result = json.loads(server.workflow_transition(
            "discover", force=True, project_dir=str(initialized)
        ))
        assert "intake → discover" in result["transition"]

    def test_transition_guard_failure(self, initialized):
        result = json.loads(server.workflow_transition(
            "discover", project_dir=str(initialized)
        ))
        assert result["error"] == "GuardFailedError"

    def test_check(self, initialized):
        result = json.loads(server.workflow_check(str(initialized)))
        assert "transitions" in result

    def test_render(self, initialized):
        output = server.workflow_render(str(initialized))
        assert "Workflow Status" in output

    def test_config(self, initialized):
        result = json.loads(server.workflow_config(str(initialized)))
        assert result["project_dir"] == str(initialized)


# ---------------------------------------------------------------------------
# Work Items
# ---------------------------------------------------------------------------

class TestItemTools:
    @pytest.fixture
    def in_plan(self, initialized):
        engine.do_transition(initialized, "discover", force=True)
        engine.do_transition(initialized, "frame", force=True)
        engine.do_transition(initialized, "plan", force=True)
        return initialized

    def test_add_item(self, in_plan):
        result = json.loads(server.workflow_item_add(
            "Test item", project_dir=str(in_plan)
        ))
        assert result["item_id"] == "WI-001"
        assert result["state"] == "ready"

    def test_list_items(self, in_plan):
        server.workflow_item_add("Item A", project_dir=str(in_plan))
        server.workflow_item_add("Item B", project_dir=str(in_plan))

        result = json.loads(server.workflow_item_list(project_dir=str(in_plan)))
        assert result["summary"]["total"] == 2

    def test_item_transition(self, in_plan):
        server.workflow_item_add("Item", project_dir=str(in_plan))
        engine.do_transition(in_plan, "deliver", force=True)

        result = json.loads(server.workflow_item_transition(
            "WI-001", "implementing", project_dir=str(in_plan)
        ))
        assert "ready → implementing" in result["transition"]

    def test_item_waive(self, in_plan):
        server.workflow_item_add("Item", project_dir=str(in_plan))
        engine.do_transition(in_plan, "deliver", force=True)

        engine.transition_item(in_plan, "WI-001", "implementing")
        engine.transition_item(in_plan, "WI-001", "verifying")
        engine.transition_item(in_plan, "WI-001", "reviewing")

        result = json.loads(server.workflow_item_waive(
            "WI-001", "admin", "not needed", project_dir=str(in_plan)
        ))
        assert result["state"] == "waived"


# ---------------------------------------------------------------------------
# Block / Resume / Close
# ---------------------------------------------------------------------------

class TestLifecycleTools:
    def test_block_and_resume(self, initialized):
        result = json.loads(server.workflow_block(
            "waiting", "alice", project_dir=str(initialized)
        ))
        assert "blocked" in result["transition"]

        result = json.loads(server.workflow_resume(
            "resolved", project_dir=str(initialized)
        ))
        assert "intake" in result["transition"]

    def test_waive_guard(self, initialized):
        result = json.loads(server.workflow_waive_guard(
            "brief_who_populated", "admin", "testing",
            project_dir=str(initialized)
        ))
        assert result["guard"] == "brief_who_populated"

    def test_close(self, initialized):
        result = json.loads(server.workflow_close(
            force=True, project_dir=str(initialized)
        ))
        assert "closed" in result["transition"]


# ---------------------------------------------------------------------------
# Project Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    @pytest.fixture(autouse=True)
    def temp_registry(self, tmp_path):
        with patch.object(server, "REGISTRY_DIR", tmp_path / ".product-delivery"), \
             patch.object(server, "REGISTRY_PATH", tmp_path / ".product-delivery" / "projects.json"):
            yield

    def test_detect_registers_project(self, initialized):
        server.workflow_detect(str(initialized))
        registry = server._load_registry()
        assert str(initialized) in registry["projects"]
        assert registry["projects"][str(initialized)]["name"] == initialized.name

    def test_init_registers_project(self, project):
        server.workflow_init(project_dir=str(project))
        registry = server._load_registry()
        assert str(project) in registry["projects"]
        assert registry["projects"][str(project)]["phase"] == "intake"

    def test_projects_empty(self):
        result = json.loads(server.workflow_projects())
        assert result["count"] == 0

    def test_projects_lists_registered(self, initialized):
        server.workflow_detect(str(initialized))
        result = json.loads(server.workflow_projects())
        assert result["count"] == 1
        assert result["projects"][0]["name"] == initialized.name

    def test_projects_refresh(self, initialized):
        server.workflow_detect(str(initialized))
        engine.do_transition(initialized, "discover", force=True)

        result = json.loads(server.workflow_projects(refresh=True))
        assert result["projects"][0]["phase"] == "discover"
        assert result["projects"][0]["status"] == "active"

    def test_projects_refresh_missing_dir(self, project, tmp_path):
        import shutil
        gone = tmp_path / "gone-project"
        gone.mkdir()
        engine.init_workflow(gone)
        server.workflow_detect(str(gone))
        shutil.rmtree(gone)

        result = json.loads(server.workflow_projects(refresh=True))
        missing = [p for p in result["projects"] if p["project_dir"] == str(gone)]
        assert missing[0]["status"] == "directory_missing"

    def test_project_remove(self, initialized):
        server.workflow_detect(str(initialized))
        result = json.loads(server.workflow_project_remove(str(initialized)))
        assert result["removed"] is True

        registry = server._load_registry()
        assert str(initialized) not in registry["projects"]

    def test_project_remove_not_found(self):
        result = json.loads(server.workflow_project_remove("/nonexistent"))
        assert result["removed"] is False

    def test_multiple_projects(self, tmp_path):
        projects = []
        for name in ["alpha", "beta", "gamma"]:
            p = tmp_path / name
            p.mkdir()
            engine.init_workflow(p)
            server.workflow_detect(str(p))
            projects.append(p)

        result = json.loads(server.workflow_projects())
        assert result["count"] == 3

    def test_registry_updates_last_seen(self, initialized):
        server.workflow_detect(str(initialized))
        reg1 = server._load_registry()
        first_seen = reg1["projects"][str(initialized)]["last_seen"]

        server.workflow_detect(str(initialized))
        reg2 = server._load_registry()
        second_seen = reg2["projects"][str(initialized)]["last_seen"]

        assert second_seen >= first_seen

    def test_registry_updates_phase(self, initialized):
        server.workflow_detect(str(initialized))
        reg1 = server._load_registry()
        assert reg1["projects"][str(initialized)]["phase"] == "intake"

        engine.do_transition(initialized, "discover", force=True)
        server.workflow_detect(str(initialized))
        reg2 = server._load_registry()
        assert reg2["projects"][str(initialized)]["phase"] == "discover"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

class TestSetupTool:
    def test_dry_run(self, project):
        result = json.loads(server.workflow_setup(
            dry_run=True, project_dir=str(project)
        ))
        assert result["mode"] == "preview"
        assert result["changes_count"] > 0

    def test_apply(self, project):
        result = json.loads(server.workflow_setup(
            dry_run=False, project_dir=str(project)
        ))
        assert result["mode"] == "applied"
        assert (project / ".claude" / "settings.json").exists()
        assert (project / ".cursor" / "mcp.json").exists()
        assert (project / "AGENTS.md").exists()
        assert (project / ".env.sample").exists()

    def test_idempotent(self, project):
        server.workflow_setup(dry_run=False, project_dir=str(project))
        result = json.loads(server.workflow_setup(
            dry_run=True, project_dir=str(project)
        ))
        assert result["already_setup"] is True
