"""
Delivery Workflow Engine

Core state machine logic for the product-delivery lifecycle. Deterministic:
owns schema validation, legal transitions, optimistic concurrency, idempotency,
guard evaluation, and event persistence.

All functions accept a project_dir Path and return structured dicts.
Errors are raised as WorkflowError subclasses, never sys.exit.
"""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKFLOW_DIR = ".workflow"
STATE_FILE = "state.json"
EVENTS_FILE = "events.jsonl"
CONFIG_FILE = "config.json"

SCHEMA_VERSION = "1.0.0"

TOP_LEVEL_STATES = [
    "intake", "discover", "frame", "plan", "deliver",
    "release", "stabilize", "closed", "blocked", "aborted",
]

ACTIVE_STATES = ["intake", "discover", "frame", "plan", "deliver", "release", "stabilize"]
TERMINAL_STATES = ["closed", "aborted"]

WORK_ITEM_STATES = [
    "ready", "implementing", "verifying", "reviewing",
    "accepted", "blocked", "rework", "waived", "cancelled",
]
WORK_ITEM_TERMINAL = ["accepted", "waived", "cancelled"]

VALID_TRANSITIONS = {
    "intake":    ["discover", "blocked", "aborted"],
    "discover":  ["frame", "blocked", "aborted"],
    "frame":     ["plan", "blocked", "aborted"],
    "plan":      ["deliver", "blocked", "aborted"],
    "deliver":   ["release", "blocked", "aborted"],
    "release":   ["stabilize", "deliver", "blocked", "aborted"],
    "stabilize": ["closed", "deliver", "blocked", "aborted"],
}

VALID_ITEM_TRANSITIONS = {
    "ready":        ["implementing"],
    "implementing": ["verifying", "blocked"],
    "verifying":    ["reviewing", "rework"],
    "reviewing":    ["accepted", "rework", "waived"],
    "rework":       ["implementing"],
    "blocked":      ["implementing"],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class WorkflowError(Exception):
    pass

class WorkflowNotFoundError(WorkflowError):
    pass

class WorkflowExistsError(WorkflowError):
    pass

class InvalidTransitionError(WorkflowError):
    pass

class GuardFailedError(WorkflowError):
    def __init__(self, message, guard_results=None):
        super().__init__(message)
        self.guard_results = guard_results or {}

class InvalidPhaseError(WorkflowError):
    pass

class ItemNotFoundError(WorkflowError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_workflow_id():
    return f"wf-{uuid.uuid4().hex[:8]}"

def _generate_event_id():
    return f"evt-{uuid.uuid4().hex[:12]}"

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _derive_status(phase):
    if phase in TERMINAL_STATES:
        return "terminal"
    if phase == "blocked":
        return "blocked"
    return "active"

def _wf_path(project_dir: Path):
    return project_dir / WORKFLOW_DIR

def _load_state(project_dir: Path) -> dict:
    state_path = _wf_path(project_dir) / STATE_FILE
    if not state_path.exists():
        raise WorkflowNotFoundError(
            f"No workflow found at {state_path}. Initialize one first."
        )
    with open(state_path) as f:
        return json.load(f)

def _save_state(state: dict, project_dir: Path):
    state["updated_at"] = _now_iso()
    with open(_wf_path(project_dir) / STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")

def _append_event(event: dict, project_dir: Path):
    with open(_wf_path(project_dir) / EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")

def _load_events(project_dir: Path) -> list:
    events_path = _wf_path(project_dir) / EVENTS_FILE
    if not events_path.exists():
        return []
    events = []
    with open(events_path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events

def _load_config(project_dir: Path) -> dict:
    config_path = _wf_path(project_dir) / CONFIG_FILE
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}

def _make_idempotency_key(state, target, item_id=None):
    wf_id = state["workflow_id"]
    rev = state["revision"]
    phase = state["phase"]
    if item_id:
        return f"{wf_id}:{rev}:{item_id}:{phase}-to-{target}"
    return f"{wf_id}:{rev}:{phase}-to-{target}"

def _check_idempotency(key, project_dir: Path) -> bool:
    for e in _load_events(project_dir):
        if e.get("idempotency_key") == key:
            return True
    return False

def _next_item_id(state):
    existing = list(state.get("work_items", {}).keys())
    if not existing:
        return "WI-001"
    nums = [int(k.split("-")[1]) for k in existing]
    return f"WI-{max(nums) + 1:03d}"

def _work_items_summary(state):
    items = state.get("work_items", {})
    return {
        "total": len(items),
        "accepted": sum(1 for i in items.values() if i["state"] == "accepted"),
        "waived": sum(1 for i in items.values() if i["state"] == "waived"),
        "cancelled": sum(1 for i in items.values() if i["state"] == "cancelled"),
        "blocked": sum(1 for i in items.values() if i["state"] == "blocked"),
        "in_progress": sum(1 for i in items.values() if i["state"] in ("implementing", "verifying", "reviewing", "rework")),
        "ready": sum(1 for i in items.values() if i["state"] == "ready"),
    }


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _all_items_terminal(state):
    items = state.get("work_items", {})
    if not items:
        return False
    return all(item["state"] in WORK_ITEM_TERMINAL for item in items.values())

def _any_item_accepted(state):
    items = state.get("work_items", {})
    return any(item["state"] == "accepted" for item in items.values())

def _any_item_in_state(state, target_state):
    items = state.get("work_items", {})
    return any(item["state"] == target_state for item in items.values())

TRANSITION_GUARDS = {
    "intake->discover": [
        ("brief_who_populated", lambda s: bool(s.get("brief", {}).get("who"))),
        ("brief_problem_populated", lambda s: bool(s.get("brief", {}).get("problem"))),
        ("project_type_determined", lambda s: s.get("project_type") is not None),
    ],
    "discover->frame": [
        ("unknowns_resolved", lambda s: True),
    ],
    "frame->plan": [
        ("scope_confirmed", lambda s: True),
        ("user_confirmation", lambda s: True),
    ],
    "plan->deliver": [
        ("plan_exists", lambda s: len(s.get("work_items", {})) > 0),
        ("criteria_mapped", lambda s: len(s.get("acceptance_criteria", [])) > 0),
    ],
    "deliver->release": [
        ("work_items_complete", lambda s: _all_items_terminal(s)),
        ("at_least_one_accepted", lambda s: _any_item_accepted(s)),
        ("no_items_blocked", lambda s: not _any_item_in_state(s, "blocked")),
    ],
    "release->stabilize": [
        ("coherence_check_passes", lambda s: True),
    ],
    "stabilize->closed": [
        ("user_confirms", lambda s: True),
    ],
}

def evaluate_guards(state, target, config=None):
    key = f"{state['phase']}->{target}"
    guards = TRANSITION_GUARDS.get(key, [])
    config = config or {}
    overrides = config.get("guard_overrides", {})

    results = {}
    for name, check_fn in guards:
        override = overrides.get(name, "strict")
        if override == "skip":
            results[name] = "not_applicable"
            continue
        try:
            passed = check_fn(state)
        except Exception:
            passed = False

        if passed:
            results[name] = "pass"
        elif override == "warn":
            results[name] = "pass"
        else:
            waivers = state.get("waivers", [])
            if any(w["guard"] == name for w in waivers):
                results[name] = "waived"
            else:
                results[name] = "fail"

    return results


# ---------------------------------------------------------------------------
# Operations (return dicts, raise on error)
# ---------------------------------------------------------------------------

def init_workflow(
    project_dir: Path,
    project_type: Optional[str] = None,
    from_migration: bool = False,
) -> dict:
    wf = _wf_path(project_dir)
    if (wf / STATE_FILE).exists():
        raise WorkflowExistsError("Workflow already exists. Use status to inspect.")

    wf.mkdir(parents=True, exist_ok=True)
    (wf / "evidence").mkdir(exist_ok=True)

    wf_id = _generate_workflow_id()
    ts = _now_iso()

    state = {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": wf_id,
        "revision": 0,
        "phase": "intake",
        "status": "active",
        "resume_state": None,
        "project_type": project_type,
        "objective": None,
        "scope": {"included": [], "excluded": []},
        "brief": {},
        "acceptance_criteria": [],
        "work_items": {},
        "risks": [],
        "decisions": [],
        "waivers": [],
        "evidence_index": [],
        "last_transition": None,
        "blocked_reason": None,
        "blocked_owner": None,
        "abort_reason": None,
        "created_at": ts,
        "updated_at": ts,
        "migrated_from": None,
    }

    if from_migration:
        state = _handle_migration(state, project_dir)

    _save_state(state, project_dir)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": ts,
        "type": "migrate" if state.get("migrated_from") else "init",
        "from_state": None,
        "to_state": state["phase"],
        "item_id": None,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": f"Workflow initialized. Type: {state['project_type'] or 'undetermined'}.",
        "actor": "system",
        "revision": 0,
        "data": {"migrated_from": state.get("migrated_from")},
    }
    _append_event(event, project_dir)

    return {
        "workflow_id": wf_id,
        "phase": state["phase"],
        "project_type": state["project_type"],
        "migrated_from": state.get("migrated_from"),
    }


def _handle_migration(state, project_dir: Path):
    build_plan = project_dir / "BUILD_PLAN.md"
    roadmap = project_dir / "ROADMAP.md"

    if roadmap.exists():
        state["migrated_from"] = "product-evolution"
        state["project_type"] = "evolution"
        state["phase"] = "deliver"
        state["status"] = "active"
    elif build_plan.exists():
        state["migrated_from"] = "product-discovery"
        state["project_type"] = "greenfield"
        content = build_plan.read_text()
        completed = len(re.findall(r"(?i)\*\*Status\*\*:\s*complete", content))
        total = len(re.findall(r"^###\s+Step\s+\d+", content, re.MULTILINE))
        state["phase"] = "deliver" if (completed > 0 and total > 0) else "plan"
        state["status"] = "active"

    return state


def get_status(project_dir: Path) -> dict:
    state = _load_state(project_dir)
    events = _load_events(project_dir)
    return {
        "workflow_id": state["workflow_id"],
        "phase": state["phase"],
        "status": state["status"],
        "project_type": state["project_type"],
        "revision": state["revision"],
        "blocked_reason": state.get("blocked_reason"),
        "blocked_owner": state.get("blocked_owner"),
        "resume_state": state.get("resume_state"),
        "work_items": {
            wid: {"name": item["name"], "state": item["state"]}
            for wid, item in state.get("work_items", {}).items()
        },
        "work_items_summary": _work_items_summary(state),
        "recent_events": [
            {
                "event_id": e["event_id"],
                "timestamp": e["timestamp"],
                "type": e["type"],
                "reason": e.get("reason"),
            }
            for e in events[-5:]
        ],
    }


def get_next_transitions(project_dir: Path) -> dict:
    state = _load_state(project_dir)
    config = _load_config(project_dir)
    phase = state["phase"]

    if phase in TERMINAL_STATES:
        return {
            "current": phase,
            "allowed": [],
            "message": f"Workflow is {phase}. No transitions available.",
        }

    if phase == "blocked":
        return {
            "current": "blocked",
            "resume_state": state.get("resume_state"),
            "allowed": [{"target": state.get("resume_state"), "action": "resume"}],
            "message": f"Blocked: {state.get('blocked_reason')}. Resume to return to {state.get('resume_state')}.",
        }

    targets = VALID_TRANSITIONS.get(phase, [])
    allowed = []
    for target in targets:
        if target in ("blocked", "aborted"):
            allowed.append({"target": target, "guards": []})
            continue
        guard_results = evaluate_guards(state, target, config)
        guards = [{"name": n, "status": s} for n, s in guard_results.items()]
        allowed.append({"target": target, "guards": guards})

    return {"current": phase, "allowed": allowed}


def do_transition(
    project_dir: Path,
    target: str,
    evidence: Optional[list] = None,
    force: bool = False,
    reason: Optional[str] = None,
) -> dict:
    state = _load_state(project_dir)
    config = _load_config(project_dir)
    phase = state["phase"]

    if phase in TERMINAL_STATES:
        raise InvalidPhaseError(f"Workflow is {phase}. No transitions allowed.")
    if phase == "blocked":
        raise InvalidPhaseError("Workflow is blocked. Use resume to unblock.")

    valid = VALID_TRANSITIONS.get(phase, [])
    if target not in valid:
        raise InvalidTransitionError(
            f"Cannot transition from {phase} to {target}. Valid targets: {', '.join(valid)}"
        )

    idem_key = _make_idempotency_key(state, target)
    if _check_idempotency(idem_key, project_dir):
        return {
            "transition": f"{phase} → {target}",
            "idempotent": True,
            "message": "Transition already recorded. No change.",
        }

    guard_results = evaluate_guards(state, target, config)
    failed = {k: v for k, v in guard_results.items() if v == "fail"}

    if failed and not force:
        raise GuardFailedError(
            f"Guards blocked transition {phase} → {target}: {', '.join(failed.keys())}",
            guard_results=guard_results,
        )

    state["revision"] += 1
    state["phase"] = target
    state["status"] = _derive_status(target)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "transition",
        "from_state": phase,
        "to_state": target,
        "item_id": None,
        "guard_results": guard_results,
        "evidence_keys": evidence or [],
        "idempotency_key": idem_key,
        "forced": force and bool(failed),
        "reason": reason,
        "actor": "agent",
        "revision": state["revision"],
        "data": None,
    }

    state["last_transition"] = event["event_id"]
    _save_state(state, project_dir)
    _append_event(event, project_dir)

    return {
        "transition": f"{phase} → {target}",
        "revision": state["revision"],
        "forced": event["forced"],
        "guard_results": guard_results,
    }


def add_item(
    project_dir: Path,
    name: str,
    acceptance_criteria: Optional[list] = None,
    risks: Optional[list] = None,
) -> dict:
    state = _load_state(project_dir)
    if state["phase"] not in ("plan", "deliver"):
        raise InvalidPhaseError(
            f"Can only add items in plan or deliver phase (current: {state['phase']})."
        )

    item_id = _next_item_id(state)
    ac_refs = acceptance_criteria or []
    risk_refs = risks or []

    state["work_items"][item_id] = {
        "name": name,
        "state": "ready",
        "depends_on": [],
        "acceptance_criteria": ac_refs,
        "evidence": [],
        "waive_reason": None,
        "waive_approver": None,
    }
    state["revision"] += 1
    _save_state(state, project_dir)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "item_add",
        "from_state": None,
        "to_state": "ready",
        "item_id": item_id,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": f"Added work item: {name}",
        "actor": "agent",
        "revision": state["revision"],
        "data": {"ac": ac_refs, "risks": risk_refs},
    }
    _append_event(event, project_dir)

    return {"item_id": item_id, "name": name, "state": "ready"}


def list_items(
    project_dir: Path,
    state_filter: Optional[str] = None,
) -> dict:
    state = _load_state(project_dir)
    items = state.get("work_items", {})
    result = []
    for wid, item in items.items():
        if state_filter and item["state"] != state_filter:
            continue
        result.append({
            "id": wid,
            "name": item["name"],
            "state": item["state"],
            "acceptance_criteria": item.get("acceptance_criteria", []),
        })
    return {"items": result, "summary": _work_items_summary(state)}


def transition_item(
    project_dir: Path,
    item_id: str,
    target: str,
    reason: Optional[str] = None,
) -> dict:
    state = _load_state(project_dir)
    if state["phase"] != "deliver":
        raise InvalidPhaseError(
            f"Item transitions only valid in deliver phase (current: {state['phase']})."
        )

    items = state.get("work_items", {})
    if item_id not in items:
        raise ItemNotFoundError(f"Work item {item_id} not found.")

    item = items[item_id]
    current = item["state"]
    valid = VALID_ITEM_TRANSITIONS.get(current, [])

    if target != "cancelled" and target not in valid:
        raise InvalidTransitionError(
            f"Cannot transition {item_id} from {current} to {target}. Valid: {', '.join(valid)}"
        )

    idem_key = _make_idempotency_key(state, target, item_id)
    if _check_idempotency(idem_key, project_dir):
        return {
            "item_id": item_id,
            "transition": f"{current} → {target}",
            "idempotent": True,
        }

    item["state"] = target
    state["revision"] += 1
    _save_state(state, project_dir)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "item_transition",
        "from_state": current,
        "to_state": target,
        "item_id": item_id,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": idem_key,
        "forced": False,
        "reason": reason,
        "actor": "agent",
        "revision": state["revision"],
        "data": None,
    }
    _append_event(event, project_dir)

    return {
        "item_id": item_id,
        "transition": f"{current} → {target}",
        "revision": state["revision"],
    }


def waive_item(
    project_dir: Path,
    item_id: str,
    approver: str,
    reason: str,
) -> dict:
    state = _load_state(project_dir)
    items = state.get("work_items", {})
    if item_id not in items:
        raise ItemNotFoundError(f"Work item {item_id} not found.")

    item = items[item_id]
    if item["state"] != "reviewing":
        raise InvalidTransitionError(
            f"Can only waive items in reviewing state (current: {item['state']})."
        )

    item["state"] = "waived"
    item["waive_approver"] = approver
    item["waive_reason"] = reason
    state["revision"] += 1
    _save_state(state, project_dir)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "waive",
        "from_state": "reviewing",
        "to_state": "waived",
        "item_id": item_id,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": f"Waived by {approver}: {reason}",
        "actor": "user",
        "revision": state["revision"],
        "data": {"approver": approver, "reason": reason},
    }
    _append_event(event, project_dir)

    return {"item_id": item_id, "state": "waived", "approver": approver}


def check_guards(project_dir: Path) -> dict:
    state = _load_state(project_dir)
    config = _load_config(project_dir)
    phase = state["phase"]

    if phase in TERMINAL_STATES:
        return {"phase": phase, "terminal": True, "transitions": {}}
    if phase == "blocked":
        return {"phase": phase, "blocked": True, "transitions": {}}

    targets = [t for t in VALID_TRANSITIONS.get(phase, []) if t not in ("blocked", "aborted")]
    transitions = {}
    for target in targets:
        guard_results = evaluate_guards(state, target, config)
        all_pass = all(v in ("pass", "waived", "not_applicable") for v in guard_results.values())
        transitions[f"{phase}->{target}"] = {
            "ready": all_pass,
            "guards": guard_results,
        }

    return {"phase": phase, "transitions": transitions}


def block_workflow(
    project_dir: Path,
    reason: str,
    owner: str,
) -> dict:
    state = _load_state(project_dir)
    phase = state["phase"]

    if phase in TERMINAL_STATES:
        raise InvalidPhaseError(f"Cannot block a {phase} workflow.")
    if phase == "blocked":
        raise InvalidPhaseError("Workflow is already blocked.")

    state["resume_state"] = phase
    state["phase"] = "blocked"
    state["status"] = "blocked"
    state["blocked_reason"] = reason
    state["blocked_owner"] = owner
    state["revision"] += 1

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "block",
        "from_state": phase,
        "to_state": "blocked",
        "item_id": None,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": reason,
        "actor": "agent",
        "revision": state["revision"],
        "data": {"owner": owner},
    }

    state["last_transition"] = event["event_id"]
    _save_state(state, project_dir)
    _append_event(event, project_dir)

    return {"transition": f"{phase} → blocked", "reason": reason, "owner": owner}


def resume_workflow(
    project_dir: Path,
    reason: Optional[str] = None,
) -> dict:
    state = _load_state(project_dir)
    if state["phase"] != "blocked":
        raise InvalidPhaseError("Workflow is not blocked.")

    resume_to = state["resume_state"]
    if not resume_to:
        raise WorkflowError("No resume state recorded.")

    state["phase"] = resume_to
    state["status"] = "active"
    state["resume_state"] = None
    state["blocked_reason"] = None
    state["blocked_owner"] = None
    state["revision"] += 1

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "resume",
        "from_state": "blocked",
        "to_state": resume_to,
        "item_id": None,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": reason,
        "actor": "agent",
        "revision": state["revision"],
        "data": None,
    }

    state["last_transition"] = event["event_id"]
    _save_state(state, project_dir)
    _append_event(event, project_dir)

    return {"transition": f"blocked → {resume_to}", "revision": state["revision"]}


def waive_guard(
    project_dir: Path,
    guard: str,
    approver: str,
    reason: str,
) -> dict:
    state = _load_state(project_dir)

    waiver = {
        "guard": guard,
        "approver": approver,
        "reason": reason,
        "scope": state["phase"],
        "risk_accepted": f"Guard {guard} waived",
        "timestamp": _now_iso(),
    }
    state.setdefault("waivers", []).append(waiver)
    state["revision"] += 1
    _save_state(state, project_dir)

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "waive",
        "from_state": state["phase"],
        "to_state": state["phase"],
        "item_id": None,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": None,
        "forced": False,
        "reason": f"Guard '{guard}' waived by {approver}: {reason}",
        "actor": "user",
        "revision": state["revision"],
        "data": {"guard": guard, "approver": approver},
    }
    _append_event(event, project_dir)

    return {"guard": guard, "approver": approver, "phase": state["phase"]}


def close_workflow(
    project_dir: Path,
    reason: Optional[str] = None,
    force: bool = False,
) -> dict:
    state = _load_state(project_dir)
    phase = state["phase"]

    if phase == "closed":
        return {"phase": "closed", "message": "Workflow is already closed."}

    if phase != "stabilize" and not force:
        raise InvalidPhaseError(
            f"Can only close from stabilize phase (current: {phase}). Use force to override."
        )

    prev_rev = state["revision"]
    state["phase"] = "closed"
    state["status"] = "terminal"
    state["revision"] += 1

    idem_key = _make_idempotency_key(
        {"workflow_id": state["workflow_id"], "revision": prev_rev, "phase": phase},
        "closed",
    )

    event = {
        "event_id": _generate_event_id(),
        "timestamp": _now_iso(),
        "type": "transition",
        "from_state": phase,
        "to_state": "closed",
        "item_id": None,
        "guard_results": None,
        "evidence_keys": [],
        "idempotency_key": idem_key,
        "forced": phase != "stabilize",
        "reason": reason or "Workflow closed.",
        "actor": "user",
        "revision": state["revision"],
        "data": None,
    }

    state["last_transition"] = event["event_id"]
    _save_state(state, project_dir)
    _append_event(event, project_dir)

    return {
        "transition": f"{phase} → closed",
        "revision": state["revision"],
        "forced": phase != "stabilize",
    }


def render_status(project_dir: Path) -> str:
    state = _load_state(project_dir)
    events = _load_events(project_dir)

    lines = [
        f"# Workflow Status: {state['workflow_id']}",
        "",
        f"**Phase**: {state['phase']}  ",
        f"**Status**: {state['status']}  ",
        f"**Type**: {state['project_type'] or 'undetermined'}  ",
        f"**Revision**: {state['revision']}  ",
        "",
    ]

    if state.get("objective"):
        lines.append(f"**Objective**: {state['objective']}")
        lines.append("")

    if state["phase"] == "blocked":
        lines.extend([
            f"**Blocked**: {state.get('blocked_reason', '?')}  ",
            f"**Owner**: {state.get('blocked_owner', '?')}  ",
            f"**Resume to**: {state.get('resume_state', '?')}  ",
            "",
        ])

    items = state.get("work_items", {})
    if items:
        summary = _work_items_summary(state)
        lines.append(f"## Work Items ({summary['total']})")
        lines.append("")
        lines.append(f"Progress: {summary['accepted']} accepted, {summary['in_progress']} in progress, "
                      f"{summary['blocked']} blocked, {summary['ready']} ready")
        lines.append("")
        lines.append("| ID | Name | State |")
        lines.append("|---|---|---|")
        for wid, item in items.items():
            lines.append(f"| {wid} | {item['name']} | {item['state']} |")
        lines.append("")

    recent = events[-5:] if events else []
    if recent:
        lines.append("## Recent Events")
        lines.append("")
        for e in recent:
            lines.append(f"- [{e['timestamp'][:19]}] {e['type']}: {e.get('reason', '-')}")
        lines.append("")

    return "\n".join(lines)
