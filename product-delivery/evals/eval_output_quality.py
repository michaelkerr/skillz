"""
Output Quality Evaluator for product-delivery

Validates the structural correctness of .workflow/state.json, events.jsonl,
BUILD_PLAN.md or ROADMAP.md, AGENTS.md, CLAUDE.md, ARCHITECTURE.md, and
DECISIONS.md against the skill's requirements.

Input:  Path to a project directory.
Output: Structured report to stdout. Exit code 0 = all pass, 1 = any fail.

Usage:
    python eval_output_quality.py /path/to/project
    python eval_output_quality.py /path/to/project --format json
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Finding:
    rule: str
    status: str  # PASS | FAIL | WARN | SKIP
    detail: str
    file: Optional[str] = None

    def to_dict(self):
        d = {"rule": self.rule, "status": self.status, "detail": self.detail}
        if self.file is not None:
            d["file"] = self.file
        return d


@dataclass
class EvalResult:
    findings: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.status == "FAIL" for f in self.findings)

    @property
    def counts(self) -> dict:
        c = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for f in self.findings:
            c[f.status] = c.get(f.status, 0) + 1
        return c

    def to_dict(self):
        return {
            "passed": self.passed,
            "counts": self.counts,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Workflow State Checker
# ---------------------------------------------------------------------------

VALID_PHASES = [
    "intake", "discover", "frame", "plan", "deliver",
    "release", "stabilize", "closed", "blocked", "aborted",
]

VALID_STATUSES = ["active", "blocked", "terminal"]

ID_PATTERNS = {
    "AC": re.compile(r"^AC-\d{3}$"),
    "RISK": re.compile(r"^RISK-\d{3}$"),
    "DEC": re.compile(r"^DEC-\d{3}$"),
    "WI": re.compile(r"^WI-\d{3}$"),
}


class WorkflowStateChecker:
    def __init__(self, project_dir: Path, result: EvalResult):
        self.project_dir = project_dir
        self.result = result
        self.wf_dir = project_dir / ".workflow"
        self.state = None

    def check_exists(self) -> bool:
        state_path = self.wf_dir / "state.json"
        if not state_path.exists():
            self.result.findings.append(Finding(
                "workflow-state-exists", "SKIP",
                ".workflow/state.json not found — skipping workflow checks",
                file=".workflow/state.json",
            ))
            return False
        try:
            with open(state_path) as f:
                self.state = json.load(f)
            self.result.findings.append(Finding(
                "workflow-state-exists", "PASS",
                ".workflow/state.json exists and is valid JSON",
                file=".workflow/state.json",
            ))
            return True
        except (json.JSONDecodeError, OSError) as e:
            self.result.findings.append(Finding(
                "workflow-state-exists", "FAIL",
                f".workflow/state.json is not valid JSON: {e}",
                file=".workflow/state.json",
            ))
            return False

    def check_required_fields(self):
        required = ["schema_version", "workflow_id", "revision", "phase", "status", "created_at", "updated_at"]
        missing = [f for f in required if f not in self.state]
        if missing:
            self.result.findings.append(Finding(
                "workflow-required-fields", "FAIL",
                f"Missing required fields: {', '.join(missing)}",
                file=".workflow/state.json",
            ))
        else:
            self.result.findings.append(Finding(
                "workflow-required-fields", "PASS",
                "All required fields present",
                file=".workflow/state.json",
            ))

    def check_phase_valid(self):
        phase = self.state.get("phase")
        if phase not in VALID_PHASES:
            self.result.findings.append(Finding(
                "workflow-phase-valid", "FAIL",
                f"Invalid phase: {phase}. Valid: {', '.join(VALID_PHASES)}",
                file=".workflow/state.json",
            ))
        else:
            self.result.findings.append(Finding(
                "workflow-phase-valid", "PASS",
                f"Phase '{phase}' is valid",
                file=".workflow/state.json",
            ))

    def check_status_consistent(self):
        phase = self.state.get("phase")
        status = self.state.get("status")
        expected = "terminal" if phase in ("closed", "aborted") else ("blocked" if phase == "blocked" else "active")
        if status != expected:
            self.result.findings.append(Finding(
                "workflow-status-consistent", "FAIL",
                f"Status '{status}' inconsistent with phase '{phase}' (expected '{expected}')",
                file=".workflow/state.json",
            ))
        else:
            self.result.findings.append(Finding(
                "workflow-status-consistent", "PASS",
                f"Status '{status}' consistent with phase '{phase}'",
                file=".workflow/state.json",
            ))

    def check_id_formats(self):
        errors = []
        for ac in self.state.get("acceptance_criteria", []):
            if not ID_PATTERNS["AC"].match(ac.get("id", "")):
                errors.append(f"Invalid AC ID: {ac.get('id')}")
        for risk in self.state.get("risks", []):
            if not ID_PATTERNS["RISK"].match(risk.get("id", "")):
                errors.append(f"Invalid RISK ID: {risk.get('id')}")
        for dec in self.state.get("decisions", []):
            if not ID_PATTERNS["DEC"].match(dec.get("id", "")):
                errors.append(f"Invalid DEC ID: {dec.get('id')}")
        for wid in self.state.get("work_items", {}):
            if not ID_PATTERNS["WI"].match(wid):
                errors.append(f"Invalid WI ID: {wid}")

        if errors:
            self.result.findings.append(Finding(
                "workflow-id-formats", "FAIL",
                f"ID format errors: {'; '.join(errors)}",
                file=".workflow/state.json",
            ))
        else:
            self.result.findings.append(Finding(
                "workflow-id-formats", "PASS",
                "All IDs follow NNN format",
                file=".workflow/state.json",
            ))

    def check_workflow_id_format(self):
        wf_id = self.state.get("workflow_id", "")
        if not re.match(r"^wf-[a-f0-9]{8}$", wf_id):
            self.result.findings.append(Finding(
                "workflow-id-valid", "FAIL",
                f"Invalid workflow_id format: {wf_id} (expected wf-XXXXXXXX)",
                file=".workflow/state.json",
            ))
        else:
            self.result.findings.append(Finding(
                "workflow-id-valid", "PASS",
                f"workflow_id format valid: {wf_id}",
                file=".workflow/state.json",
            ))


# ---------------------------------------------------------------------------
# Event Log Checker
# ---------------------------------------------------------------------------

class EventLogChecker:
    def __init__(self, project_dir: Path, result: EvalResult):
        self.project_dir = project_dir
        self.result = result
        self.events = []

    def check_exists(self) -> bool:
        events_path = self.project_dir / ".workflow" / "events.jsonl"
        if not events_path.exists():
            self.result.findings.append(Finding(
                "events-exist", "SKIP",
                ".workflow/events.jsonl not found",
                file=".workflow/events.jsonl",
            ))
            return False
        try:
            with open(events_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.events.append(json.loads(line))
            self.result.findings.append(Finding(
                "events-exist", "PASS",
                f".workflow/events.jsonl exists with {len(self.events)} event(s)",
                file=".workflow/events.jsonl",
            ))
            return True
        except (json.JSONDecodeError, OSError) as e:
            self.result.findings.append(Finding(
                "events-exist", "FAIL",
                f".workflow/events.jsonl parse error: {e}",
                file=".workflow/events.jsonl",
            ))
            return False

    def check_chronological(self):
        if len(self.events) < 2:
            return
        timestamps = [e.get("timestamp", "") for e in self.events]
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                self.result.findings.append(Finding(
                    "events-chronological", "FAIL",
                    f"Event {i} timestamp {timestamps[i]} is before event {i-1} timestamp {timestamps[i-1]}",
                    file=".workflow/events.jsonl",
                ))
                return
        self.result.findings.append(Finding(
            "events-chronological", "PASS",
            "Events are in chronological order",
            file=".workflow/events.jsonl",
        ))

    def check_idempotency_unique(self):
        keys = [e.get("idempotency_key") for e in self.events if e.get("idempotency_key")]
        dupes = set()
        seen = set()
        for k in keys:
            if k in seen:
                dupes.add(k)
            seen.add(k)
        if dupes:
            self.result.findings.append(Finding(
                "events-idempotency-unique", "FAIL",
                f"Duplicate idempotency keys: {', '.join(dupes)}",
                file=".workflow/events.jsonl",
            ))
        else:
            self.result.findings.append(Finding(
                "events-idempotency-unique", "PASS",
                "All idempotency keys are unique",
                file=".workflow/events.jsonl",
            ))

    def check_revisions_monotonic(self):
        revisions = [e.get("revision") for e in self.events if e.get("revision") is not None]
        for i in range(1, len(revisions)):
            if revisions[i] <= revisions[i - 1]:
                self.result.findings.append(Finding(
                    "events-revisions-monotonic", "WARN",
                    f"Revision {revisions[i]} at event {i} is not strictly increasing from {revisions[i-1]}",
                    file=".workflow/events.jsonl",
                ))
                return
        if revisions:
            self.result.findings.append(Finding(
                "events-revisions-monotonic", "PASS",
                "Event revisions are monotonically increasing",
                file=".workflow/events.jsonl",
            ))


# ---------------------------------------------------------------------------
# Greenfield Plan Checker (BUILD_PLAN.md / sequenced steps)
# ---------------------------------------------------------------------------

GREENFIELD_STEP_FIELDS = [
    "Status", "What it does", "What good looks like", "Test", "Depends on", "Notes",
]

GREENFIELD_VALID_STATUSES = {"ready", "implementing", "verifying", "reviewing", "accepted"}
LEGACY_VALID_STATUSES = {"not started", "in progress", "complete"}


def _parse_greenfield_steps(text: str) -> list:
    step_pattern = re.compile(
        r"^###\s+Step\s+(\d+)\s*:\s*(.+)$", re.MULTILINE,
    )
    matches = list(step_pattern.finditer(text))
    steps = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        fields = {}
        for field_match in re.finditer(
            r"-\s+\*\*(.+?)\*\*\s*:[ \t]*(.*?)(?=\n-\s+\*\*|\n###|\Z)",
            block, re.DOTALL,
        ):
            fields[field_match.group(1).strip()] = field_match.group(2).strip()

        steps.append({
            "name": m.group(2).strip(),
            "number": int(m.group(1)),
            "fields": fields,
            "raw": block,
        })
    return steps


class GreenFieldPlanChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result
        self.steps = _parse_greenfield_steps(text)

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "plan-present", "FAIL",
                "BUILD_PLAN.md is empty or missing",
                file="BUILD_PLAN.md",
            ))
            return False
        self.result.findings.append(Finding(
            "plan-present", "PASS",
            "BUILD_PLAN.md exists and is non-empty",
            file="BUILD_PLAN.md",
        ))
        return True

    def check_summary(self):
        if re.search(r"##\s+(Product\s+summary|Summary)", self.text, re.IGNORECASE):
            self.result.findings.append(Finding(
                "plan-summary", "PASS",
                "Summary section present",
                file="BUILD_PLAN.md",
            ))
        else:
            self.result.findings.append(Finding(
                "plan-summary", "FAIL",
                "Missing summary section",
                file="BUILD_PLAN.md",
            ))

    def check_step_count(self):
        n = len(self.steps)
        if n == 0:
            self.result.findings.append(Finding(
                "plan-step-count", "FAIL",
                "No steps found",
                file="BUILD_PLAN.md",
            ))
        elif n > 15:
            self.result.findings.append(Finding(
                "plan-step-count", "FAIL",
                f"Found {n} steps; scope caps at 15",
                file="BUILD_PLAN.md",
            ))
        elif n < 3:
            self.result.findings.append(Finding(
                "plan-step-count", "WARN",
                f"Only {n} step(s); typical range is 5-12",
                file="BUILD_PLAN.md",
            ))
        else:
            self.result.findings.append(Finding(
                "plan-step-count", "PASS",
                f"{n} steps (within 3-15 range)",
                file="BUILD_PLAN.md",
            ))

    def check_field_completeness(self):
        all_complete = True
        for step in self.steps:
            missing = [f for f in GREENFIELD_STEP_FIELDS if f not in step["fields"]]
            if missing:
                all_complete = False
                self.result.findings.append(Finding(
                    "plan-field-completeness", "FAIL",
                    f"Step {step['number']} ('{step['name']}') missing fields: "
                    f"{', '.join(missing)}",
                    file="BUILD_PLAN.md",
                ))
        if all_complete and self.steps:
            self.result.findings.append(Finding(
                "plan-field-completeness", "PASS",
                f"All {len(self.steps)} steps have required fields",
                file="BUILD_PLAN.md",
            ))

    def check_status_values(self):
        all_valid = GREENFIELD_VALID_STATUSES | LEGACY_VALID_STATUSES
        bad = []
        for step in self.steps:
            status = step["fields"].get("Status", "").strip().lower()
            if status and status not in all_valid:
                bad.append((step["number"], status))
        if bad:
            detail = "; ".join(f"Step {n}: '{s}'" for n, s in bad)
            self.result.findings.append(Finding(
                "plan-status-valid", "FAIL",
                f"Invalid status values: {detail}",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "plan-status-valid", "PASS",
                "All step statuses are valid",
                file="BUILD_PLAN.md",
            ))

    def check_one_behavior_per_step(self):
        violations = []
        for step in self.steps:
            wid = step["fields"].get("What it does", "")
            if re.search(r",\s+and\s+[a-z]", wid, re.IGNORECASE) or \
               re.search(r"\band\b.*\band\b", wid, re.IGNORECASE):
                violations.append(step["number"])
        if violations:
            nums = ", ".join(str(n) for n in violations)
            self.result.findings.append(Finding(
                "plan-one-behavior", "WARN",
                f"Steps {nums} may describe multiple behaviors in 'What it does'",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "plan-one-behavior", "PASS",
                "No compound 'What it does' fields detected",
                file="BUILD_PLAN.md",
            ))

    def check_test_field_format(self):
        issues = []
        for step in self.steps:
            test = step["fields"].get("Test", "").strip()
            if not test:
                continue
            is_manual = test.lower().strip('"').strip("'") == "manual"
            has_assertion = bool(re.search(
                r"(given|when|should|expect|returns?|displays?|shows?|"
                r"→|->|outputs?|results? in|produces)",
                test, re.IGNORECASE,
            ))
            if not is_manual and not has_assertion:
                issues.append(step["number"])
        if issues:
            nums = ", ".join(str(n) for n in issues)
            self.result.findings.append(Finding(
                "plan-test-format", "WARN",
                f"Steps {nums}: Test field is neither 'manual' nor assertion-style",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "plan-test-format", "PASS",
                "All Test fields are 'manual' or assertion-style",
                file="BUILD_PLAN.md",
            ))

    def check_depends_on_references(self):
        step_numbers = {s["number"] for s in self.steps}
        wi_ids = {s["fields"].get("ID", "").strip() for s in self.steps}
        issues = []
        for step in self.steps:
            dep = step["fields"].get("Depends on", step["fields"].get("Builds on", "")).strip().lower()
            if not dep or dep in ("nothing", "none", "n/a", "-"):
                continue
            # Check WI-NNN references
            wi_refs = re.findall(r"WI-(\d{3})", dep, re.IGNORECASE)
            step_refs = re.findall(r"step\s+(\d+)", dep, re.IGNORECASE)
            if not wi_refs and not step_refs:
                step_refs = re.findall(r"(\d+)", dep)
            for ref_str in step_refs:
                ref = int(ref_str)
                if ref not in step_numbers:
                    issues.append(f"Step {step['number']} references non-existent Step {ref}")
                elif ref >= step["number"]:
                    issues.append(f"Step {step['number']} references Step {ref} (forward/circular)")
            for ref_str in wi_refs:
                wi_id = f"WI-{ref_str}"
                if wi_id.upper() not in {w.upper() for w in wi_ids}:
                    issues.append(f"Step {step['number']} references non-existent {wi_id}")
        if issues:
            self.result.findings.append(Finding(
                "plan-depends-on-valid", "FAIL",
                "; ".join(issues),
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "plan-depends-on-valid", "PASS",
                "All dependency references are valid",
                file="BUILD_PLAN.md",
            ))

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_summary()
        self.check_step_count()
        self.check_field_completeness()
        self.check_status_values()
        self.check_one_behavior_per_step()
        self.check_test_field_format()
        self.check_depends_on_references()


# ---------------------------------------------------------------------------
# Evolution Plan Checker (ROADMAP.md / priority-bucketed items)
# ---------------------------------------------------------------------------

ROADMAP_REQUIRED_SECTIONS = [
    ("Product summary", r"##\s+(?:Product\s+summary|Summary|What.?s\s+built)"),
    ("Now", r"##\s+Now\b"),
    ("Next", r"##\s+Next\b"),
    ("Later", r"##\s+Later\b"),
    ("Parked", r"##\s+Parked\b"),
]

NOW_ITEM_FIELDS = ["Type", "What it does", "Done when", "Touches", "Risk", "Notes"]

VALID_ITEM_TYPES = {"feature", "fix", "debt", "improvement", "infrastructure"}


def _parse_now_items(text: str) -> list:
    now_match = re.search(
        r"##\s+Now\b(.*?)(?=\n##\s|\Z)", text, re.DOTALL | re.IGNORECASE,
    )
    if not now_match:
        return []
    now_text = now_match.group(1)
    item_pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    matches = list(item_pattern.finditer(now_text))
    items = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(now_text)
        block = now_text[start:end].strip()
        fields = {}
        for field_match in re.finditer(
            r"-\s+\*\*(.+?)\*\*\s*:[ \t]*(.*?)(?=\n-\s+\*\*|\n###|\Z)",
            block, re.DOTALL,
        ):
            fields[field_match.group(1).strip()] = field_match.group(2).strip()
        items.append({"name": m.group(1).strip(), "fields": fields, "raw": block})
    return items


class EvolutionPlanChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result
        self.now_items = _parse_now_items(text)

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "plan-present", "FAIL",
                "ROADMAP.md is empty or missing",
                file="ROADMAP.md",
            ))
            return False
        self.result.findings.append(Finding(
            "plan-present", "PASS",
            "ROADMAP.md exists and is non-empty",
            file="ROADMAP.md",
        ))
        return True

    def check_required_sections(self):
        missing = []
        for name, pattern in ROADMAP_REQUIRED_SECTIONS:
            if not re.search(pattern, self.text, re.IGNORECASE):
                missing.append(name)
        if missing:
            self.result.findings.append(Finding(
                "plan-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "plan-sections", "PASS",
                "All required sections present",
                file="ROADMAP.md",
            ))

    def check_now_items_exist(self):
        if not self.now_items:
            self.result.findings.append(Finding(
                "plan-now-items", "WARN",
                "No items found in NOW section",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "plan-now-items", "PASS",
                f"{len(self.now_items)} item(s) in NOW section",
                file="ROADMAP.md",
            ))

    def check_now_field_completeness(self):
        all_complete = True
        for item in self.now_items:
            missing = [f for f in NOW_ITEM_FIELDS if f not in item["fields"]]
            if missing:
                all_complete = False
                self.result.findings.append(Finding(
                    "plan-now-fields", "FAIL",
                    f"NOW item '{item['name']}' missing fields: {', '.join(missing)}",
                    file="ROADMAP.md",
                ))
        if all_complete and self.now_items:
            self.result.findings.append(Finding(
                "plan-now-fields", "PASS",
                f"All {len(self.now_items)} NOW items have required fields",
                file="ROADMAP.md",
            ))

    def check_type_values(self):
        bad = []
        for item in self.now_items:
            type_val = item["fields"].get("Type", "").strip().lower()
            if type_val and type_val not in VALID_ITEM_TYPES:
                bad.append((item["name"], type_val))
        if bad:
            detail = "; ".join(f"'{name}': '{t}'" for name, t in bad)
            self.result.findings.append(Finding(
                "plan-type-valid", "FAIL",
                f"Invalid type values: {detail}",
                file="ROADMAP.md",
            ))
        elif self.now_items:
            self.result.findings.append(Finding(
                "plan-type-valid", "PASS",
                "All NOW item types are valid",
                file="ROADMAP.md",
            ))

    def check_no_step_numbers(self):
        if re.search(r"###\s+Step\s+\d+", self.text, re.IGNORECASE):
            self.result.findings.append(Finding(
                "plan-no-steps", "WARN",
                "ROADMAP.md contains '### Step N' headings — "
                "evolution plans use named items, not numbered steps",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "plan-no-steps", "PASS",
                "No step-numbered headings found",
                file="ROADMAP.md",
            ))

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_required_sections()
        self.check_now_items_exist()
        self.check_now_field_completeness()
        self.check_type_values()
        self.check_no_step_numbers()


# ---------------------------------------------------------------------------
# Artifact Checkers
# ---------------------------------------------------------------------------

AGENTS_SECTIONS_STARTUP = [
    "What this is", "Build protocol", "Tech stack", "Project structure",
    "Commands", "Conventions", "Do not", "Decisions", "Known issues",
]

AGENTS_SECTIONS_EVOLVED = [
    "What this is", "Work protocol", "Tech stack", "Architecture overview",
    "Project structure", "Commands", "Conventions", "Module guide",
    "Do not", "Known issues",
]

SPECULATIVE_PATTERNS = [
    r"we might later",
    r"we may (eventually|later|someday)",
    r"in the future we could",
    r"might want to add",
    r"could potentially",
    r"down the road",
    r"phase \d+ might",
    r"eventually we.?ll",
    r"for later",
    r"TODO:?\s*(maybe|consider|think about)",
]


class AgentsMdChecker:
    def __init__(self, text: str, result: EvalResult, evolved: bool = False):
        self.text = text
        self.result = result
        self.evolved = evolved
        self.expected_sections = AGENTS_SECTIONS_EVOLVED if evolved else AGENTS_SECTIONS_STARTUP

    def check_exists(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "agents-md-exists", "FAIL",
                "AGENTS.md is empty or missing",
                file="AGENTS.md",
            ))
            return False
        self.result.findings.append(Finding(
            "agents-md-exists", "PASS",
            "AGENTS.md exists and is non-empty",
            file="AGENTS.md",
        ))
        return True

    def check_sections(self):
        found = re.findall(r"^##\s+(.+)$", self.text, re.MULTILINE)
        found_lower = [s.strip().lower() for s in found]
        missing = [s for s in self.expected_sections if s.lower() not in found_lower]
        if missing:
            self.result.findings.append(Finding(
                "agents-md-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-sections", "PASS",
                f"All {len(self.expected_sections)} required sections present",
                file="AGENTS.md",
            ))

    def check_no_speculation(self):
        hits = []
        for i, line in enumerate(self.text.splitlines(), 1):
            for pat in SPECULATIVE_PATTERNS:
                if re.search(pat, line, re.IGNORECASE):
                    hits.append((i, line.strip()[:80]))
                    break
        if hits:
            examples = "; ".join(f"line {n}: '{txt}'" for n, txt in hits[:3])
            self.result.findings.append(Finding(
                "agents-md-no-speculation", "FAIL",
                f"Speculative content found ({len(hits)} instance(s)): {examples}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-no-speculation", "PASS",
                "No speculative content detected",
                file="AGENTS.md",
            ))

    def check_protocol_refs(self):
        protocol_label = "Work protocol" if self.evolved else "Build protocol"
        plan_ref = "ROADMAP.md" if self.evolved else "BUILD_PLAN.md"
        wrong_ref = "BUILD_PLAN.md" if self.evolved else "ROADMAP.md"
        match = re.search(
            rf"##\s+{re.escape(protocol_label)}\s*\n(.*?)(?=\n##\s|\Z)",
            self.text, re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return
        content = match.group(1)
        refs_correct = plan_ref in content or plan_ref.lower().replace(".md", "") in content.lower()
        refs_wrong = wrong_ref in content
        if refs_correct and not refs_wrong:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "PASS",
                f"{protocol_label} references {plan_ref}",
                file="AGENTS.md",
            ))
        elif refs_wrong:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "FAIL",
                f"{protocol_label} references {wrong_ref} — should reference {plan_ref}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "WARN",
                f"{protocol_label} does not reference {plan_ref}",
                file="AGENTS.md",
            ))

    def check_no_progress_tracking(self):
        progress_patterns = [
            r"##\s+(Progress|Status|Session\s+notes|Log)",
            r"completed step \d+",
            r"session \d+:",
        ]
        for pat in progress_patterns:
            if re.search(pat, self.text, re.IGNORECASE):
                self.result.findings.append(Finding(
                    "agents-md-no-progress", "WARN",
                    f"AGENTS.md appears to contain progress tracking (matched: '{pat}')",
                    file="AGENTS.md",
                ))
                return
        self.result.findings.append(Finding(
            "agents-md-no-progress", "PASS",
            "No progress tracking or session notes detected",
            file="AGENTS.md",
        ))


class ClaudeMdChecker:
    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check(self):
        if not self.text.strip():
            self.result.findings.append(Finding(
                "claude-md-exists", "SKIP",
                "CLAUDE.md not found",
                file="CLAUDE.md",
            ))
            return
        if "@agents.md" in self.text.lower():
            self.result.findings.append(Finding(
                "claude-md-stub", "PASS",
                "CLAUDE.md contains @agents.md import",
                file="CLAUDE.md",
            ))
        else:
            self.result.findings.append(Finding(
                "claude-md-stub", "WARN",
                "CLAUDE.md does not contain @agents.md import",
                file="CLAUDE.md",
            ))


class ArchitectureChecker:
    REQUIRED_SECTIONS = [
        "System overview", "Component map", "Data flow",
        "Data model", "Integration points",
    ]

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_exists(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "architecture-exists", "SKIP",
                "ARCHITECTURE.md not found",
                file="ARCHITECTURE.md",
            ))
            return False
        self.result.findings.append(Finding(
            "architecture-exists", "PASS",
            "ARCHITECTURE.md exists",
            file="ARCHITECTURE.md",
        ))
        return True

    def check_sections(self):
        found = re.findall(r"^##\s+(.+)$", self.text, re.MULTILINE)
        found_lower = [s.strip().lower() for s in found]
        missing = [s for s in self.REQUIRED_SECTIONS if s.lower() not in found_lower]
        if missing:
            self.result.findings.append(Finding(
                "architecture-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="ARCHITECTURE.md",
            ))
        else:
            self.result.findings.append(Finding(
                "architecture-sections", "PASS",
                "All required sections present",
                file="ARCHITECTURE.md",
            ))

    def check_component_entries(self):
        comp_section = re.search(
            r"##\s+Component\s+map\s*\n(.*?)(?=\n##\s|\Z)",
            self.text, re.DOTALL | re.IGNORECASE,
        )
        if not comp_section:
            return
        entries = re.findall(r"###\s+.+", comp_section.group(1))
        if not entries:
            self.result.findings.append(Finding(
                "architecture-components", "WARN",
                "Component map section has no ### component entries",
                file="ARCHITECTURE.md",
            ))
        else:
            content = comp_section.group(1)
            has_purpose = bool(re.search(r"\*\*Purpose\*\*", content))
            has_entry = bool(re.search(r"\*\*Entry point\*\*", content))
            if has_purpose and has_entry:
                self.result.findings.append(Finding(
                    "architecture-components", "PASS",
                    f"{len(entries)} component(s) with structured fields",
                    file="ARCHITECTURE.md",
                ))
            else:
                self.result.findings.append(Finding(
                    "architecture-components", "WARN",
                    f"{len(entries)} component(s) found but missing "
                    f"expected fields (Purpose, Entry point)",
                    file="ARCHITECTURE.md",
                ))


class DecisionsChecker:
    REQUIRED_FIELDS = [
        "Date", "Area", "Decision", "Context",
        "Alternatives considered", "Consequences",
    ]

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_exists(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "decisions-exists", "SKIP",
                "DECISIONS.md not found",
                file="DECISIONS.md",
            ))
            return False
        self.result.findings.append(Finding(
            "decisions-exists", "PASS",
            "DECISIONS.md exists",
            file="DECISIONS.md",
        ))
        return True

    def check_entry_format(self):
        entries = re.findall(r"^###\s+(.+)$", self.text, re.MULTILINE)
        if not entries:
            self.result.findings.append(Finding(
                "decisions-entries", "WARN",
                "No decision entries found (### headings)",
                file="DECISIONS.md",
            ))
            return
        all_complete = True
        for entry in entries:
            entry_block_match = re.search(
                rf"###\s+{re.escape(entry)}(.+?)(?=###|\Z)",
                self.text, re.DOTALL,
            )
            if entry_block_match:
                block = entry_block_match.group(1)
                missing = [f for f in self.REQUIRED_FIELDS if f"**{f}**" not in block]
                if missing:
                    all_complete = False
                    self.result.findings.append(Finding(
                        "decisions-entry-fields", "WARN",
                        f"Entry '{entry}' missing fields: {', '.join(missing)}",
                        file="DECISIONS.md",
                    ))
        if all_complete:
            self.result.findings.append(Finding(
                "decisions-entry-fields", "PASS",
                f"All {len(entries)} decision entries have required fields",
                file="DECISIONS.md",
            ))

    def check_usage_section(self):
        if re.search(r"##\s+How to use this file", self.text, re.IGNORECASE):
            self.result.findings.append(Finding(
                "decisions-usage", "PASS",
                "'How to use this file' section present",
                file="DECISIONS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "decisions-usage", "WARN",
                "Missing '## How to use this file' section",
                file="DECISIONS.md",
            ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return ""


def run_eval(project_dir: Path) -> EvalResult:
    result = EvalResult()

    # Workflow state checks
    wsc = WorkflowStateChecker(project_dir, result)
    if wsc.check_exists():
        wsc.check_required_fields()
        wsc.check_phase_valid()
        wsc.check_status_consistent()
        wsc.check_id_formats()
        wsc.check_workflow_id_format()

    # Event log checks
    elc = EventLogChecker(project_dir, result)
    if elc.check_exists():
        elc.check_chronological()
        elc.check_idempotency_unique()
        elc.check_revisions_monotonic()

    # Determine if evolved format
    state = wsc.state or {}
    is_evolved = state.get("project_type") == "evolution"

    # Plan artifact checks
    if is_evolved:
        roadmap_text = _read_file(project_dir / "ROADMAP.md")
        EvolutionPlanChecker(roadmap_text, result).run_all()
    else:
        plan_text = _read_file(project_dir / "BUILD_PLAN.md")
        GreenFieldPlanChecker(plan_text, result).run_all()

    # AGENTS.md checks
    agents_text = _read_file(project_dir / "AGENTS.md")
    amc = AgentsMdChecker(agents_text, result, evolved=is_evolved)
    if amc.check_exists():
        amc.check_sections()
        amc.check_no_speculation()
        amc.check_protocol_refs()
        amc.check_no_progress_tracking()

    # CLAUDE.md checks
    claude_text = _read_file(project_dir / "CLAUDE.md")
    ClaudeMdChecker(claude_text, result).check()

    # Evolution-only artifacts
    if is_evolved:
        arch_text = _read_file(project_dir / "ARCHITECTURE.md")
        ac = ArchitectureChecker(arch_text, result)
        if ac.check_exists():
            ac.check_sections()
            ac.check_component_entries()

        dec_text = _read_file(project_dir / "DECISIONS.md")
        dc = DecisionsChecker(dec_text, result)
        if dc.check_exists():
            dc.check_entry_format()
            dc.check_usage_section()

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Product Delivery Output Quality Evaluator")
    parser.add_argument("project_dir", help="Path to the project directory")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory", file=sys.stderr)
        sys.exit(2)

    result = run_eval(project_dir)

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        counts = result.counts
        print(f"\n{'=' * 60}")
        print(f"Output Quality Eval: {'PASS' if result.passed else 'FAIL'}")
        print(f"{'=' * 60}")
        print(f"  PASS: {counts['PASS']}  FAIL: {counts['FAIL']}  WARN: {counts['WARN']}  SKIP: {counts['SKIP']}")
        print()
        for f in result.findings:
            marker = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "○"}[f.status]
            file_str = f" [{f.file}]" if f.file else ""
            print(f"  {marker} {f.rule}{file_str}: {f.detail}")
        print()

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
