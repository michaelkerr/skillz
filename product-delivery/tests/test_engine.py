"""Tests for the workflow engine — state machine, transitions, guards, work items."""

import json
import pytest
from pathlib import Path

from product_delivery import engine


@pytest.fixture
def project(tmp_path):
    """Create a temp project directory."""
    return tmp_path / "test-project"


@pytest.fixture
def initialized(project):
    """Project with an initialized workflow in intake phase."""
    project.mkdir()
    engine.init_workflow(project)
    return project


@pytest.fixture
def in_deliver(project):
    """Project advanced to deliver phase with work items."""
    project.mkdir()
    engine.init_workflow(project, project_type="greenfield")

    state = engine._load_state(project)
    state["brief"] = {"who": "developers", "problem": "need tests"}
    state["acceptance_criteria"] = [{"id": "AC-001", "text": "tests pass"}]
    engine._save_state(state, project)

    engine.do_transition(project, "discover", force=True)
    engine.do_transition(project, "frame", force=True)
    engine.do_transition(project, "plan", force=True)

    engine.add_item(project, "Build feature A", ["AC-001"])
    engine.add_item(project, "Build feature B")

    engine.do_transition(project, "deliver", force=True)
    return project


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_workflow(self, project):
        project.mkdir()
        result = engine.init_workflow(project)
        assert result["phase"] == "intake"
        assert result["workflow_id"].startswith("wf-")
        assert (project / ".workflow" / "state.json").exists()
        assert (project / ".workflow" / "events.jsonl").exists()

    def test_sets_project_type(self, project):
        project.mkdir()
        result = engine.init_workflow(project, project_type="evolution")
        assert result["project_type"] == "evolution"

    def test_rejects_double_init(self, initialized):
        with pytest.raises(engine.WorkflowExistsError):
            engine.init_workflow(initialized)

    def test_state_file_valid_json(self, initialized):
        state = json.loads((initialized / ".workflow" / "state.json").read_text())
        assert state["schema_version"] == "1.0.0"
        assert state["revision"] == 0
        assert state["status"] == "active"

    def test_event_logged(self, initialized):
        events = engine._load_events(initialized)
        assert len(events) == 1
        assert events[0]["type"] == "init"


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migrate_from_build_plan(self, project):
        project.mkdir()
        (project / "BUILD_PLAN.md").write_text(
            "# Build Plan\n### Step 1\n**Status**: complete\n### Step 2\n**Status**: pending\n"
        )
        result = engine.init_workflow(project, from_migration=True)
        assert result["project_type"] == "greenfield"
        assert result["phase"] == "deliver"
        assert result["migrated_from"] == "product-discovery"

    def test_migrate_from_roadmap(self, project):
        project.mkdir()
        (project / "ROADMAP.md").write_text("# Roadmap\n## NOW\n- feature A\n")
        result = engine.init_workflow(project, from_migration=True)
        assert result["project_type"] == "evolution"
        assert result["phase"] == "deliver"
        assert result["migrated_from"] == "product-evolution"


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

class TestTransitions:
    def test_valid_transition(self, initialized):
        state = engine._load_state(initialized)
        state["brief"] = {"who": "users", "problem": "testing"}
        state["project_type"] = "greenfield"
        engine._save_state(state, initialized)

        result = engine.do_transition(initialized, "discover")
        assert "intake → discover" in result["transition"]
        assert result["revision"] == 1

    def test_invalid_transition(self, initialized):
        with pytest.raises(engine.InvalidTransitionError):
            engine.do_transition(initialized, "deliver")

    def test_forced_transition(self, initialized):
        result = engine.do_transition(initialized, "discover", force=True)
        assert result["forced"] is True

    def test_idempotent_transition(self, initialized):
        state = engine._load_state(initialized)
        idem_key = engine._make_idempotency_key(state, "discover")

        engine.do_transition(initialized, "discover", force=True)
        state_after_first = engine._load_state(initialized)

        # Replay same idempotency key by resetting phase back to intake
        state_reset = engine._load_state(initialized)
        state_reset["phase"] = "intake"
        state_reset["revision"] = 0
        engine._save_state(state_reset, initialized)

        result = engine.do_transition(initialized, "discover", force=True)
        assert result["idempotent"] is True

    def test_terminal_state_blocks_transitions(self, initialized):
        engine.do_transition(initialized, "aborted", force=True, reason="cancelled")
        with pytest.raises(engine.InvalidPhaseError):
            engine.do_transition(initialized, "discover", force=True)

    def test_guard_failure_without_force(self, initialized):
        with pytest.raises(engine.GuardFailedError) as exc_info:
            engine.do_transition(initialized, "discover")
        assert "guard_results" in dir(exc_info.value)

    def test_transition_records_evidence(self, initialized):
        result = engine.do_transition(
            initialized, "discover", evidence=["doc-1", "doc-2"], force=True
        )
        events = engine._load_events(initialized)
        last = events[-1]
        assert last["evidence_keys"] == ["doc-1", "doc-2"]


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

class TestGuards:
    def test_intake_guards_fail_empty_brief(self, initialized):
        results = engine.evaluate_guards(engine._load_state(initialized), "discover")
        assert results["brief_who_populated"] == "fail"
        assert results["brief_problem_populated"] == "fail"

    def test_intake_guards_pass(self, initialized):
        state = engine._load_state(initialized)
        state["brief"] = {"who": "devs", "problem": "needs tests"}
        state["project_type"] = "greenfield"
        engine._save_state(state, initialized)

        results = engine.evaluate_guards(state, "discover")
        assert all(v == "pass" for v in results.values())

    def test_waived_guard(self, initialized):
        engine.waive_guard(initialized, "brief_who_populated", "admin", "testing")
        state = engine._load_state(initialized)
        results = engine.evaluate_guards(state, "discover")
        assert results["brief_who_populated"] == "waived"

    def test_deliver_to_release_guards(self, in_deliver):
        results = engine.evaluate_guards(engine._load_state(in_deliver), "release")
        assert results["work_items_complete"] == "fail"


# ---------------------------------------------------------------------------
# Work Items
# ---------------------------------------------------------------------------

class TestWorkItems:
    def test_add_item(self, in_deliver):
        state = engine._load_state(in_deliver)
        state["phase"] = "plan"
        engine._save_state(state, in_deliver)

        result = engine.add_item(in_deliver, "New item", ["AC-001"])
        assert result["state"] == "ready"
        assert result["item_id"].startswith("WI-")

    def test_add_item_wrong_phase(self, initialized):
        with pytest.raises(engine.InvalidPhaseError):
            engine.add_item(initialized, "Bad item")

    def test_list_items(self, in_deliver):
        result = engine.list_items(in_deliver)
        assert result["summary"]["total"] == 2
        assert len(result["items"]) == 2

    def test_list_items_filtered(self, in_deliver):
        result = engine.list_items(in_deliver, state_filter="ready")
        assert all(item["state"] == "ready" for item in result["items"])

    def test_transition_item(self, in_deliver):
        result = engine.transition_item(in_deliver, "WI-001", "implementing")
        assert "ready → implementing" in result["transition"]

    def test_invalid_item_transition(self, in_deliver):
        with pytest.raises(engine.InvalidTransitionError):
            engine.transition_item(in_deliver, "WI-001", "accepted")

    def test_item_not_found(self, in_deliver):
        with pytest.raises(engine.ItemNotFoundError):
            engine.transition_item(in_deliver, "WI-999", "implementing")

    def test_cancel_item(self, in_deliver):
        result = engine.transition_item(in_deliver, "WI-001", "cancelled")
        assert "ready → cancelled" in result["transition"]

    def test_full_item_lifecycle(self, in_deliver):
        engine.transition_item(in_deliver, "WI-001", "implementing")
        engine.transition_item(in_deliver, "WI-001", "verifying")
        engine.transition_item(in_deliver, "WI-001", "reviewing")
        engine.transition_item(in_deliver, "WI-001", "accepted")

        items = engine.list_items(in_deliver)
        wi_001 = next(i for i in items["items"] if i["id"] == "WI-001")
        assert wi_001["state"] == "accepted"

    def test_rework_cycle(self, in_deliver):
        engine.transition_item(in_deliver, "WI-001", "implementing")
        engine.transition_item(in_deliver, "WI-001", "verifying")
        engine.transition_item(in_deliver, "WI-001", "rework")
        engine.transition_item(in_deliver, "WI-001", "implementing")
        engine.transition_item(in_deliver, "WI-001", "verifying")
        engine.transition_item(in_deliver, "WI-001", "reviewing")

        items = engine.list_items(in_deliver)
        wi_001 = next(i for i in items["items"] if i["id"] == "WI-001")
        assert wi_001["state"] == "reviewing"

    def test_waive_item(self, in_deliver):
        engine.transition_item(in_deliver, "WI-001", "implementing")
        engine.transition_item(in_deliver, "WI-001", "verifying")
        engine.transition_item(in_deliver, "WI-001", "reviewing")

        result = engine.waive_item(in_deliver, "WI-001", "admin", "not needed")
        assert result["state"] == "waived"

    def test_waive_item_wrong_state(self, in_deliver):
        with pytest.raises(engine.InvalidTransitionError):
            engine.waive_item(in_deliver, "WI-001", "admin", "nope")


# ---------------------------------------------------------------------------
# Block / Resume
# ---------------------------------------------------------------------------

class TestBlockResume:
    def test_block_workflow(self, initialized):
        result = engine.block_workflow(initialized, "waiting on API key", "alice")
        assert "blocked" in result["transition"]

        state = engine._load_state(initialized)
        assert state["phase"] == "blocked"
        assert state["resume_state"] == "intake"

    def test_resume_workflow(self, initialized):
        engine.block_workflow(initialized, "waiting", "bob")
        result = engine.resume_workflow(initialized, "got it")
        assert "intake" in result["transition"]

        state = engine._load_state(initialized)
        assert state["phase"] == "intake"
        assert state["blocked_reason"] is None

    def test_block_terminal_fails(self, initialized):
        engine.do_transition(initialized, "aborted", force=True)
        with pytest.raises(engine.InvalidPhaseError):
            engine.block_workflow(initialized, "reason", "owner")

    def test_double_block_fails(self, initialized):
        engine.block_workflow(initialized, "first", "alice")
        with pytest.raises(engine.InvalidPhaseError):
            engine.block_workflow(initialized, "second", "bob")

    def test_resume_not_blocked_fails(self, initialized):
        with pytest.raises(engine.InvalidPhaseError):
            engine.resume_workflow(initialized)


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_from_stabilize(self, in_deliver):
        for wi in ["WI-001", "WI-002"]:
            engine.transition_item(in_deliver, wi, "implementing")
            engine.transition_item(in_deliver, wi, "verifying")
            engine.transition_item(in_deliver, wi, "reviewing")
            engine.transition_item(in_deliver, wi, "accepted")

        engine.do_transition(in_deliver, "release", force=True)
        engine.do_transition(in_deliver, "stabilize", force=True)
        result = engine.close_workflow(in_deliver)
        assert "closed" in result["transition"]
        assert result["forced"] is False

    def test_close_wrong_phase_fails(self, initialized):
        with pytest.raises(engine.InvalidPhaseError):
            engine.close_workflow(initialized)

    def test_force_close(self, initialized):
        result = engine.close_workflow(initialized, force=True)
        assert result["forced"] is True

    def test_close_already_closed(self, initialized):
        engine.close_workflow(initialized, force=True)
        result = engine.close_workflow(initialized)
        assert result["message"] == "Workflow is already closed."


# ---------------------------------------------------------------------------
# Status / Next / Check / Render
# ---------------------------------------------------------------------------

class TestQueries:
    def test_get_status(self, initialized):
        status = engine.get_status(initialized)
        assert status["phase"] == "intake"
        assert "work_items_summary" in status

    def test_get_next_transitions(self, initialized):
        result = engine.get_next_transitions(initialized)
        assert result["current"] == "intake"
        targets = [a["target"] for a in result["allowed"]]
        assert "discover" in targets

    def test_get_next_terminal(self, initialized):
        engine.do_transition(initialized, "aborted", force=True)
        result = engine.get_next_transitions(initialized)
        assert result["allowed"] == []

    def test_get_next_blocked(self, initialized):
        engine.block_workflow(initialized, "reason", "owner")
        result = engine.get_next_transitions(initialized)
        assert result["current"] == "blocked"

    def test_check_guards(self, initialized):
        result = engine.check_guards(initialized)
        assert "transitions" in result

    def test_render_status(self, initialized):
        output = engine.render_status(initialized)
        assert "Workflow Status" in output
        assert "intake" in output

    def test_status_not_found(self, project):
        project.mkdir()
        with pytest.raises(engine.WorkflowNotFoundError):
            engine.get_status(project)
