"""Tests for the setup module — config merging, idempotency, marker detection."""

import json
import pytest
from pathlib import Path

from product_delivery import setup


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "test-project"
    p.mkdir()
    return p


class TestPlanSetup:
    def test_plan_fresh_project(self, project):
        plan = setup.plan_setup(project)
        assert plan["changes_count"] > 0
        assert plan["already_setup"] is False
        assert plan["project_name"] == "test-project"

    def test_plan_already_setup(self, project):
        setup.execute_setup(project)
        plan = setup.plan_setup(project)
        assert plan["already_setup"] is True
        assert plan["changes_count"] == 0


class TestExecuteSetup:
    def test_creates_all_files(self, project):
        result = setup.execute_setup(project)
        assert result["applied_count"] > 0
        assert (project / ".claude" / "settings.json").exists()
        assert (project / ".cursor" / "mcp.json").exists()
        assert (project / "AGENTS.md").exists()
        assert (project / ".env.sample").exists()
        assert (project / ".env").exists()

    def test_mcp_config_content(self, project):
        setup.execute_setup(project)
        claude_config = json.loads((project / ".claude" / "settings.json").read_text())
        assert "product-delivery" in claude_config["mcpServers"]
        assert claude_config["mcpServers"]["product-delivery"]["command"] == "uvx"

    def test_cursor_config_has_env_file(self, project):
        setup.execute_setup(project)
        cursor_config = json.loads((project / ".cursor" / "mcp.json").read_text())
        pd = cursor_config["mcpServers"]["product-delivery"]
        assert "envFile" in pd

    def test_preserves_existing_mcp_servers(self, project):
        claude_dir = project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "mcpServers": {"other-server": {"command": "other"}}
        }))

        setup.execute_setup(project)
        config = json.loads((claude_dir / "settings.json").read_text())
        assert "other-server" in config["mcpServers"]
        assert "product-delivery" in config["mcpServers"]

    def test_agents_md_content(self, project):
        setup.execute_setup(project)
        content = (project / "AGENTS.md").read_text()
        assert "product-delivery" in content
        assert "workflow_status" in content

    def test_agents_md_append_existing(self, project):
        (project / "AGENTS.md").write_text("# My Project\n\nExisting content.\n")
        setup.execute_setup(project)
        content = (project / "AGENTS.md").read_text()
        assert "Existing content." in content
        assert "product-delivery" in content

    def test_gitignore_entries(self, project):
        setup.execute_setup(project)
        gi = (project / ".gitignore").read_text()
        assert ".env" in gi
        assert ".workflow/" in gi

    def test_gitignore_preserves_existing(self, project):
        (project / ".gitignore").write_text("node_modules/\n")
        setup.execute_setup(project)
        gi = (project / ".gitignore").read_text()
        assert "node_modules/" in gi
        assert ".env" in gi


class TestIdempotency:
    def test_double_setup_no_duplicates(self, project):
        setup.execute_setup(project)
        setup.execute_setup(project)

        content = (project / "AGENTS.md").read_text()
        assert content.count("product-delivery** lifecycle") == 1

    def test_double_setup_no_extra_gitignore(self, project):
        setup.execute_setup(project)
        setup.execute_setup(project)

        gi = (project / ".gitignore").read_text()
        assert gi.count(".env") == 1

    def test_double_setup_no_extra_mcp(self, project):
        setup.execute_setup(project)
        setup.execute_setup(project)

        config = json.loads((project / ".claude" / "settings.json").read_text())
        assert len(config["mcpServers"]) == 1
