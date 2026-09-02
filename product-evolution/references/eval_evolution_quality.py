"""
Output Quality Evaluator for product-evolution

Validates the structural correctness of the evolved artifact set:
ROADMAP.md, AGENTS.md (evolved), CLAUDE.md (stub), ARCHITECTURE.md, DECISIONS.md.

This tests whether the artifacts are well-formed, not whether the content
is good. Companion to product-discovery's eval_output_quality.py but for
the graduated artifact set.

Input:  Path to a project directory containing the artifacts.
Output: Structured report to stdout.  Exit code 0 = all pass, 1 = any fail.

Usage:
    python eval_evolution_quality.py /path/to/project
    python eval_evolution_quality.py /path/to/project --format json
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    rule: str
    status: str          # PASS | FAIL | WARN | SKIP
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
# ROADMAP.md checks
# ---------------------------------------------------------------------------

ROADMAP_REQUIRED_SECTIONS = [
    ("Product summary", r"##\s+Product\s+summary"),
    ("What's built", r"##\s+What.?s\s+built"),
    ("Now", r"##\s+Now\b"),
    ("Next", r"##\s+Next\b"),
    ("Later", r"##\s+Later\b"),
    ("Parked", r"##\s+Parked\b"),
]

NOW_ITEM_FIELDS = ["Type", "What it does", "Done when", "Touches", "Risk", "Notes"]

VALID_TYPES = {"feature", "fix", "debt", "improvement", "infrastructure"}


def _parse_now_items(text: str) -> list[dict]:
    """Parse NOW section items from ROADMAP.md."""
    # Find the NOW section
    now_match = re.search(
        r"##\s+Now\b(.*?)(?=\n##\s|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not now_match:
        return []

    now_text = now_match.group(1)

    # Find items as ### headings within NOW
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
            block,
            re.DOTALL,
        ):
            fname = field_match.group(1).strip()
            fval = field_match.group(2).strip()
            fields[fname] = fval

        items.append({
            "name": m.group(1).strip(),
            "fields": fields,
            "raw": block,
        })
    return items


class RoadmapChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result
        self.now_items = _parse_now_items(text)

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "roadmap-present", "FAIL",
                "ROADMAP.md is empty or missing",
                file="ROADMAP.md",
            ))
            return False
        self.result.findings.append(Finding(
            "roadmap-present", "PASS",
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
                "roadmap-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "roadmap-sections", "PASS",
                "All six required sections present",
                file="ROADMAP.md",
            ))

    def check_now_items_exist(self):
        if not self.now_items:
            self.result.findings.append(Finding(
                "roadmap-now-items", "WARN",
                "No items found in NOW section",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "roadmap-now-items", "PASS",
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
                    "roadmap-now-fields", "FAIL",
                    f"NOW item '{item['name']}' missing fields: "
                    f"{', '.join(missing)}",
                    file="ROADMAP.md",
                ))
        if all_complete and self.now_items:
            self.result.findings.append(Finding(
                "roadmap-now-fields", "PASS",
                f"All {len(self.now_items)} NOW items have all six required fields",
                file="ROADMAP.md",
            ))

    def check_type_values(self):
        bad = []
        for item in self.now_items:
            type_val = item["fields"].get("Type", "").strip().lower()
            if type_val and type_val not in VALID_TYPES:
                bad.append((item["name"], type_val))
        if bad:
            detail = "; ".join(
                f"'{name}': '{t}'" for name, t in bad
            )
            self.result.findings.append(Finding(
                "roadmap-type-valid", "FAIL",
                f"Invalid type values: {detail}",
                file="ROADMAP.md",
            ))
        elif self.now_items:
            self.result.findings.append(Finding(
                "roadmap-type-valid", "PASS",
                "All NOW item types are valid",
                file="ROADMAP.md",
            ))

    def check_no_step_numbers(self):
        """Graduated roadmaps should not use step numbering."""
        if re.search(r"###\s+Step\s+\d+", self.text, re.IGNORECASE):
            self.result.findings.append(Finding(
                "roadmap-no-steps", "WARN",
                "ROADMAP.md contains '### Step N' headings -- "
                "graduated roadmaps use named items, not numbered steps",
                file="ROADMAP.md",
            ))
        else:
            self.result.findings.append(Finding(
                "roadmap-no-steps", "PASS",
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
# Evolved AGENTS.md checks
# ---------------------------------------------------------------------------

EVOLVED_AGENTS_SECTIONS = [
    "What this is",
    "Work protocol",
    "Tech stack",
    "Architecture overview",
    "Project structure",
    "Commands",
    "Conventions",
    "Module guide",
    "Do not",
    "Known issues",
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


class EvolvedAgentsMdChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "agents-md-present", "FAIL",
                "AGENTS.md is empty or missing",
                file="AGENTS.md",
            ))
            return False
        self.result.findings.append(Finding(
            "agents-md-present", "PASS",
            "AGENTS.md exists and is non-empty",
            file="AGENTS.md",
        ))
        return True

    def check_required_sections(self):
        missing = []
        for section in EVOLVED_AGENTS_SECTIONS:
            pattern = rf"##\s+{re.escape(section)}"
            if not re.search(pattern, self.text, re.IGNORECASE):
                missing.append(section)
        if missing:
            self.result.findings.append(Finding(
                "agents-md-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-sections", "PASS",
                "All ten required sections present",
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
            examples = "; ".join(
                f"line {n}: '{txt}'" for n, txt in hits[:3]
            )
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

    def check_work_protocol_refs(self):
        """Work protocol must reference ROADMAP.md, not BUILD_PLAN.md."""
        match = re.search(
            r"##\s+Work protocol\s*\n(.*?)(?=\n##\s|\Z)",
            self.text,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return
        content = match.group(1)

        refs_roadmap = "ROADMAP.md" in content or "roadmap" in content.lower()
        refs_buildplan = "BUILD_PLAN.md" in content

        if refs_roadmap and not refs_buildplan:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "PASS",
                "Work protocol references ROADMAP.md",
                file="AGENTS.md",
            ))
        elif refs_buildplan:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "FAIL",
                "Work protocol still references BUILD_PLAN.md -- "
                "should reference ROADMAP.md after graduation",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-protocol-refs", "WARN",
                "Work protocol does not reference ROADMAP.md",
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
                    f"AGENTS.md appears to contain progress tracking "
                    f"(matched: '{pat}')",
                    file="AGENTS.md",
                ))
                return
        self.result.findings.append(Finding(
            "agents-md-no-progress", "PASS",
            "No progress tracking or session notes detected",
            file="AGENTS.md",
        ))

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_required_sections()
        self.check_no_speculation()
        self.check_work_protocol_refs()
        self.check_no_progress_tracking()


# ---------------------------------------------------------------------------
# CLAUDE.md stub checks
# ---------------------------------------------------------------------------

class ClaudeMdStubChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "claude-md-present", "FAIL",
                "CLAUDE.md is empty or missing",
                file="CLAUDE.md",
            ))
            return False
        self.result.findings.append(Finding(
            "claude-md-present", "PASS",
            "CLAUDE.md exists and is non-empty",
            file="CLAUDE.md",
        ))
        return True

    def check_imports_agents(self):
        """CLAUDE.md should contain @agents.md to import the context file."""
        if "@agents.md" in self.text:
            self.result.findings.append(Finding(
                "claude-md-imports-agents", "PASS",
                "CLAUDE.md contains @agents.md import",
                file="CLAUDE.md",
            ))
        else:
            self.result.findings.append(Finding(
                "claude-md-imports-agents", "FAIL",
                "CLAUDE.md does not contain @agents.md import",
                file="CLAUDE.md",
            ))

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_imports_agents()


# ---------------------------------------------------------------------------
# ARCHITECTURE.md checks
# ---------------------------------------------------------------------------

ARCH_REQUIRED_SECTIONS = [
    ("System overview", r"##\s+System\s+overview"),
    ("Component map", r"##\s+Component\s+map"),
    ("Data flow", r"##\s+Data\s+flow"),
    ("Data model", r"##\s+Data\s+model"),
    ("Integration points", r"##\s+Integration\s+points"),
]


class ArchitectureChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "architecture-present", "FAIL",
                "ARCHITECTURE.md is empty or missing",
                file="ARCHITECTURE.md",
            ))
            return False
        self.result.findings.append(Finding(
            "architecture-present", "PASS",
            "ARCHITECTURE.md exists and is non-empty",
            file="ARCHITECTURE.md",
        ))
        return True

    def check_required_sections(self):
        missing = []
        for name, pattern in ARCH_REQUIRED_SECTIONS:
            if not re.search(pattern, self.text, re.IGNORECASE):
                missing.append(name)
        if missing:
            self.result.findings.append(Finding(
                "architecture-sections", "FAIL",
                f"Missing sections: {', '.join(missing)}",
                file="ARCHITECTURE.md",
            ))
        else:
            self.result.findings.append(Finding(
                "architecture-sections", "PASS",
                "All five required sections present",
                file="ARCHITECTURE.md",
            ))

    def check_component_entries(self):
        """Component map should have at least one ### entry with fields."""
        comp_section = re.search(
            r"##\s+Component\s+map\s*\n(.*?)(?=\n##\s|\Z)",
            self.text,
            re.DOTALL | re.IGNORECASE,
        )
        if not comp_section:
            return  # Caught by section check.

        entries = re.findall(r"###\s+.+", comp_section.group(1))
        if not entries:
            self.result.findings.append(Finding(
                "architecture-components", "WARN",
                "Component map section has no ### component entries",
                file="ARCHITECTURE.md",
            ))
        else:
            # Check that at least one entry has the expected fields
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

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_required_sections()
        self.check_component_entries()


# ---------------------------------------------------------------------------
# DECISIONS.md checks
# ---------------------------------------------------------------------------

DECISION_FIELDS = [
    "Date", "Area", "Decision", "Context",
    "Alternatives considered", "Consequences",
]


class DecisionsChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "decisions-present", "FAIL",
                "DECISIONS.md is empty or missing",
                file="DECISIONS.md",
            ))
            return False
        self.result.findings.append(Finding(
            "decisions-present", "PASS",
            "DECISIONS.md exists and is non-empty",
            file="DECISIONS.md",
        ))
        return True

    def check_has_entries(self):
        entries = re.findall(r"###\s+D\d+\s*:", self.text)
        if not entries:
            self.result.findings.append(Finding(
                "decisions-entries", "FAIL",
                "No decision entries found (expected ### D1: ... format)",
                file="DECISIONS.md",
            ))
            return False
        self.result.findings.append(Finding(
            "decisions-entries", "PASS",
            f"{len(entries)} decision entry/entries found",
            file="DECISIONS.md",
        ))
        return True

    def check_entry_fields(self):
        """Each decision entry should have the six required fields."""
        entry_pattern = re.compile(
            r"###\s+(D\d+)\s*:\s*(.+?)(?=\n###\s+D\d+|\Z)",
            re.DOTALL,
        )
        entries = list(entry_pattern.finditer(self.text))
        if not entries:
            return  # Caught by check_has_entries.

        all_complete = True
        for m in entries:
            entry_id = m.group(1)
            entry_name = m.group(2).split("\n")[0].strip()
            block = m.group(0)
            missing = []
            for f in DECISION_FIELDS:
                if not re.search(rf"\*\*{re.escape(f)}\*\*", block, re.IGNORECASE):
                    missing.append(f)
            if missing:
                all_complete = False
                self.result.findings.append(Finding(
                    "decisions-fields", "FAIL",
                    f"{entry_id} ('{entry_name}') missing fields: "
                    f"{', '.join(missing)}",
                    file="DECISIONS.md",
                ))

        if all_complete:
            self.result.findings.append(Finding(
                "decisions-fields", "PASS",
                f"All {len(entries)} entries have all six required fields",
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

    def run_all(self):
        if not self.check_file_present():
            return
        if self.check_has_entries():
            self.check_entry_fields()
        self.check_usage_section()


# ---------------------------------------------------------------------------
# BUILD_PLAN.archived.md check
# ---------------------------------------------------------------------------

def check_build_plan_archived(project_dir: Path, result: EvalResult):
    """Check that BUILD_PLAN.md was archived, not deleted."""
    archived = project_dir / "BUILD_PLAN.archived.md"
    active = project_dir / "BUILD_PLAN.md"

    if archived.exists():
        result.findings.append(Finding(
            "build-plan-archived", "PASS",
            "BUILD_PLAN.archived.md exists",
        ))
    elif active.exists():
        result.findings.append(Finding(
            "build-plan-archived", "WARN",
            "BUILD_PLAN.md still exists (expected rename to BUILD_PLAN.archived.md)",
        ))
    else:
        result.findings.append(Finding(
            "build-plan-archived", "WARN",
            "Neither BUILD_PLAN.md nor BUILD_PLAN.archived.md found",
        ))


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------

def evaluate_project(project_dir: Path) -> EvalResult:
    result = EvalResult()

    def _read(name: str) -> str:
        p = project_dir / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    RoadmapChecker(_read("ROADMAP.md"), result).run_all()
    EvolvedAgentsMdChecker(_read("AGENTS.md"), result).run_all()
    ClaudeMdStubChecker(_read("CLAUDE.md"), result).run_all()
    ArchitectureChecker(_read("ARCHITECTURE.md"), result).run_all()
    DecisionsChecker(_read("DECISIONS.md"), result).run_all()
    check_build_plan_archived(project_dir, result)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(result: EvalResult):
    counts = result.counts
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'=' * 60}")
    print(f"  Evolution Output Quality: {status}")
    print(f"  {counts['PASS']} pass | {counts['FAIL']} fail | "
          f"{counts['WARN']} warn | {counts['SKIP']} skip")
    print(f"{'=' * 60}\n")
    for f in result.findings:
        icon = {"PASS": "+", "FAIL": "X", "WARN": "?", "SKIP": "-"}[f.status]
        file_str = f" [{f.file}]" if f.file else ""
        print(f"  [{icon}] {f.rule}{file_str}")
        print(f"      {f.detail}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python eval_evolution_quality.py <project-dir> [--format json]")
        sys.exit(2)

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"Not a directory: {project_dir}")
        sys.exit(2)

    use_json = "--format" in sys.argv and "json" in sys.argv

    result = evaluate_project(project_dir)

    if use_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
