"""
Output Quality Evaluator for product-startup

Validates the structural correctness of BUILD_PLAN.md, AGENTS.md,
and CLAUDE.md against the skill's requirements.  This tests whether
the artifacts are well-formed, not whether the content is good.

Input:  Path to a project directory containing the three files.
Output: Structured report to stdout.  Exit code 0 = all pass, 1 = any fail.

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


# ---------------------------------------------------------------------------
# Data structures (mirrors eval_skill_compliance.py)
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
# BUILD_PLAN.md checks
# ---------------------------------------------------------------------------

# Required fields per step, derived from the skill's "Build plan format" section.
STEP_FIELDS = ["Status", "What it does", "What good looks like", "Test", "Builds on", "Notes"]

# Valid status values.
VALID_STATUSES = {"not started", "in progress", "complete"}


def _parse_steps(text: str) -> list[dict]:
    """Parse BUILD_PLAN.md into a list of step dicts.

    Each dict has:
        name     - step name from the ### heading
        number   - integer step number
        fields   - dict of field name -> value
        raw      - the raw text block for this step
    """
    # Split on step headings: ### Step N: Name
    step_pattern = re.compile(
        r"^###\s+Step\s+(\d+)\s*:\s*(.+)$", re.MULTILINE
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
            block,
            re.DOTALL,
        ):
            fname = field_match.group(1).strip()
            fval = field_match.group(2).strip()
            fields[fname] = fval

        steps.append({
            "name": m.group(2).strip(),
            "number": int(m.group(1)),
            "fields": fields,
            "raw": block,
        })
    return steps


class BuildPlanChecker:

    def __init__(self, text: str, result: EvalResult):
        self.text = text
        self.result = result
        self.steps = _parse_steps(text)

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "build-plan-present", "FAIL",
                "BUILD_PLAN.md is empty or missing",
                file="BUILD_PLAN.md",
            ))
            return False
        self.result.findings.append(Finding(
            "build-plan-present", "PASS",
            "BUILD_PLAN.md exists and is non-empty",
            file="BUILD_PLAN.md",
        ))
        return True

    def check_product_summary(self):
        """The build plan must open with a product summary section."""
        if re.search(r"##\s+Product\s+summary", self.text, re.IGNORECASE):
            self.result.findings.append(Finding(
                "build-plan-summary", "PASS",
                "Product summary section present",
                file="BUILD_PLAN.md",
            ))
        else:
            self.result.findings.append(Finding(
                "build-plan-summary", "FAIL",
                "Missing '## Product summary' section",
                file="BUILD_PLAN.md",
            ))

    def check_step_count(self):
        """Skill says 5-12 typical, >15 is too big."""
        n = len(self.steps)
        if n == 0:
            self.result.findings.append(Finding(
                "step-count", "FAIL",
                "No steps found in BUILD_PLAN.md",
                file="BUILD_PLAN.md",
            ))
        elif n > 15:
            self.result.findings.append(Finding(
                "step-count", "FAIL",
                f"Found {n} steps; skill caps prototype scope at 15",
                file="BUILD_PLAN.md",
            ))
        elif n < 3:
            self.result.findings.append(Finding(
                "step-count", "WARN",
                f"Only {n} step(s); typical range is 5-12",
                file="BUILD_PLAN.md",
            ))
        else:
            self.result.findings.append(Finding(
                "step-count", "PASS",
                f"{n} steps (within 3-15 range)",
                file="BUILD_PLAN.md",
            ))

    def check_field_completeness(self):
        """Every step must have all six required fields."""
        all_complete = True
        for step in self.steps:
            missing = [f for f in STEP_FIELDS if f not in step["fields"]]
            if missing:
                all_complete = False
                self.result.findings.append(Finding(
                    "step-field-completeness", "FAIL",
                    f"Step {step['number']} ('{step['name']}') missing fields: "
                    f"{', '.join(missing)}",
                    file="BUILD_PLAN.md",
                ))
        if all_complete and self.steps:
            self.result.findings.append(Finding(
                "step-field-completeness", "PASS",
                f"All {len(self.steps)} steps have all six required fields",
                file="BUILD_PLAN.md",
            ))

    def check_status_values(self):
        """Status field must be one of the three valid values."""
        bad = []
        for step in self.steps:
            status = step["fields"].get("Status", "").strip().lower()
            if status and status not in VALID_STATUSES:
                bad.append((step["number"], status))
        if bad:
            detail = "; ".join(
                f"Step {n}: '{s}'" for n, s in bad
            )
            self.result.findings.append(Finding(
                "step-status-valid", "FAIL",
                f"Invalid status values: {detail}",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "step-status-valid", "PASS",
                "All step statuses are valid",
                file="BUILD_PLAN.md",
            ))

    def check_what_it_does_and_test(self):
        """'What it does' must be one behavior (no 'and' joining two
        user-visible behaviors).  This is a heuristic: we look for
        ', and ' or ' and ' joining two verb phrases."""
        violations = []
        for step in self.steps:
            wid = step["fields"].get("What it does", "")
            # Pattern: two clauses joined by "and" where both contain a verb
            # Heuristic: "and" preceded and followed by verb-like words
            # We flag ", and " or " and " when both sides look like actions.
            if re.search(
                r",\s+and\s+[a-z]", wid, re.IGNORECASE
            ) or re.search(
                r"\band\b.*\band\b", wid, re.IGNORECASE
            ):
                violations.append(step["number"])
        if violations:
            nums = ", ".join(str(n) for n in violations)
            self.result.findings.append(Finding(
                "one-behavior-per-step", "WARN",
                f"Steps {nums} may describe multiple behaviors in "
                f"'What it does' (check for compound actions joined by 'and')",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "one-behavior-per-step", "PASS",
                "No compound 'What it does' fields detected",
                file="BUILD_PLAN.md",
            ))

    def check_test_field_format(self):
        """Test field must be either 'manual' or an assertion with literal
        input and expected output."""
        issues = []
        for step in self.steps:
            test = step["fields"].get("Test", "").strip()
            if not test:
                continue
            is_manual = test.lower().strip('"').strip("'") == "manual"
            # A non-manual test should reference concrete input/output.
            # Heuristic: look for "given", "when", "should", "expect",
            # "returns", "displays", "shows", arrow patterns, or quotes.
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
                "test-field-format", "WARN",
                f"Steps {nums}: Test field is neither 'manual' nor an "
                f"assertion-style statement with input/output",
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "test-field-format", "PASS",
                "All Test fields are 'manual' or assertion-style",
                file="BUILD_PLAN.md",
            ))

    def check_builds_on_references(self):
        """'Builds on' references must point to existing, earlier steps.
        No circular references, no forward references, no missing targets."""
        step_numbers = {s["number"] for s in self.steps}
        issues = []
        for step in self.steps:
            builds_on = step["fields"].get("Builds on", "").strip().lower()
            if not builds_on or builds_on in ("nothing", "none", "n/a", "-"):
                continue
            # Extract step numbers from the reference.
            refs = re.findall(r"step\s+(\d+)", builds_on, re.IGNORECASE)
            if not refs:
                # Could be just a number.
                refs = re.findall(r"(\d+)", builds_on)
            for ref_str in refs:
                ref = int(ref_str)
                if ref not in step_numbers:
                    issues.append(
                        f"Step {step['number']} references non-existent Step {ref}"
                    )
                elif ref >= step["number"]:
                    issues.append(
                        f"Step {step['number']} references Step {ref} "
                        f"(forward/circular)"
                    )
        if issues:
            self.result.findings.append(Finding(
                "builds-on-valid", "FAIL",
                "; ".join(issues),
                file="BUILD_PLAN.md",
            ))
        elif self.steps:
            self.result.findings.append(Finding(
                "builds-on-valid", "PASS",
                "All 'Builds on' references point to valid earlier steps",
                file="BUILD_PLAN.md",
            ))

    def run_all(self):
        if not self.check_file_present():
            return
        self.check_product_summary()
        self.check_step_count()
        self.check_field_completeness()
        self.check_status_values()
        self.check_what_it_does_and_test()
        self.check_test_field_format()
        self.check_builds_on_references()


# ---------------------------------------------------------------------------
# AGENTS.md checks
# ---------------------------------------------------------------------------

AGENTS_REQUIRED_SECTIONS = [
    "What this is",
    "Build protocol",
    "Tech stack",
    "Project structure",
    "Commands",
    "Conventions",
    "Do not",
    "Decisions",
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


class AgentsMdChecker:

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
        """All nine required sections must appear as headings."""
        missing = []
        for section in AGENTS_REQUIRED_SECTIONS:
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
                "All nine required sections present",
                file="AGENTS.md",
            ))

    def check_no_speculation(self):
        """The skill forbids speculative content like 'we might later want to...'."""
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

    def check_build_protocol_content(self):
        """Build protocol section must reference BUILD_PLAN.md."""
        match = re.search(
            r"##\s+Build protocol\s*\n(.*?)(?=\n##\s|\Z)",
            self.text,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return
        content = match.group(1)
        if "BUILD_PLAN.md" in content or "build plan" in content.lower():
            self.result.findings.append(Finding(
                "agents-md-build-protocol-ref", "PASS",
                "Build protocol references BUILD_PLAN.md",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-build-protocol-ref", "WARN",
                "Build protocol does not reference BUILD_PLAN.md",
                file="AGENTS.md",
            ))

    def check_no_progress_tracking(self):
        """AGENTS.md must not contain progress tracking or session notes."""
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
        self.check_build_protocol_content()
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
# Top-level runner
# ---------------------------------------------------------------------------

def evaluate_project(project_dir: Path) -> EvalResult:
    result = EvalResult()

    def _read(name: str) -> str:
        p = project_dir / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    BuildPlanChecker(_read("BUILD_PLAN.md"), result).run_all()
    AgentsMdChecker(_read("AGENTS.md"), result).run_all()
    ClaudeMdStubChecker(_read("CLAUDE.md"), result).run_all()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(result: EvalResult):
    counts = result.counts
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'=' * 60}")
    print(f"  Output Quality: {status}")
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
        print("Usage: python eval_output_quality.py <project-dir> [--format json]")
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
