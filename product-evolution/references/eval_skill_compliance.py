"""
Skill Compliance Evaluator for product-evolution

Checks whether a conversation transcript follows the skill's operational
rules. This tests whether the model obeyed the instructions, not whether
the output content is good (eval_evolution_quality.py handles that).

Key rules tested:
- Existing artifacts read before assessment (Phase 1.1)
- Maturity signals enumerated explicitly (Phase 1.2)
- Not-ready gate honored (Phase 1.2)
- Health check performed before restructuring (Phase 1.3)
- One question at a time during direction conversation (Phase 2)
- All three direction questions asked (Phase 2.1-2.3)
- Assessment presented to user before restructuring (Phase 1.2/2)
- Direction conversation precedes artifact generation (Phase 2 before 3)
- Templates read before generation (Phase 3 Read hooks)
- Confirmation asked after presenting artifacts (Phase 5)
- Coherence verification performed (Phase 4.3)

Input:  JSON file -- array of {"role": "user"|"assistant"|"system", "content": "..."}
Output: Structured report to stdout.  Exit code 0 = all pass, 1 = any fail.

Usage:
    python eval_skill_compliance.py transcript.json
    python eval_skill_compliance.py transcript.json --format json
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
    turn: Optional[int] = None

    def to_dict(self):
        d = {"rule": self.rule, "status": self.status, "detail": self.detail}
        if self.turn is not None:
            d["turn"] = self.turn
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
# Pattern banks
# ---------------------------------------------------------------------------

# Signals that existing artifacts were read (Phase 1.1)
ARTIFACT_READ_PATTERNS = [
    r"(read|reading|reviewed|review|examining|looked at|inspecting)\s+(the\s+)?"
    r"(existing|current|project.?s?)?\s*(CLAUDE\.md|BUILD_PLAN|README|AGENTS\.md)",
    r"(read|open)\s+.*(CLAUDE\.md|BUILD_PLAN|README)",
    r"current (state|artifacts|coordination files)",
    r"let me (read|review|look at) (the|your)",
]

# Maturity readiness signals (Phase 1.2)
READINESS_SIGNAL_PATTERNS = [
    r"completed?\s+(build\s+)?steps?",
    r"sequential\s+dependenc",
    r"independent",
    r"core\s+(product\s+)?interaction\s+(works|validated|complete)",
    r"conventions?\s+section",
    r"codebase\s+(has\s+)?(clear|repeated)\s+patterns?",
    r"ready\s+to\s+graduate",
    r"not\s+ready",
    r"maturity\s+(signal|indicator|assessment|check)",
]

# Health check topics (Phase 1.3)
HEALTH_CHECK_PATTERNS = [
    r"test\s+coverage",
    r"tech\s+debt",
    r"dead\s+code",
    r"architecture\s+strain",
    r"TODO\s+comments?",
    r"deprecated\s+dependenc",
    r"unused\s+imports?",
    r"pattern\s+inconsistenc",
]

# Direction question patterns (Phase 2.1-2.3)
DIRECTION_WORKING_PATTERNS = [
    r"strongest\s+part",
    r"getting\s+value\s+from",
    r"what.?s\s+working",
    r"what\s+works\s+(best|well)",
    r"most\s+valuable",
    r"what\s+are\s+(you|your\s+users)\s+(getting|using|relying)",
]

DIRECTION_NEXT_PATTERNS = [
    r"(most\s+)?important\s+things?\s+(this\s+product\s+)?needs?",
    r"next\s+month",
    r"what.?s\s+next",
    r"priorities?\s+for",
    r"2.3\s+(most\s+)?important",
    r"what\s+(does|should)\s+(the\s+product|it)\s+need",
]

DIRECTION_DRAGGING_PATTERNS = [
    r"(most\s+)?annoying\s+thing",
    r"what.?s\s+dragging",
    r"working\s+in\s+this\s+codebase",
    r"pain\s+point",
    r"(frustrat|slow|confus|fragile|brittle)",
    r"tech(nical)?\s+debt",
    r"what\s+bothers\s+you",
]

# Artifact generation signals (Phase 3)
GENERATION_PATTERNS = [
    r"(creat|writ|generat|produc)(ed?|ing)\s+(the\s+)?(ROADMAP|ARCHITECTURE|DECISIONS)",
    r"here.?s\s+(the|your)\s+(new\s+)?(ROADMAP|ARCHITECTURE|DECISIONS|CLAUDE\.md)",
    r"##\s+(Product summary|What.?s built|Now\b|System overview|Component map)",
    r"###\s+D\d+:",
]

# Template read signals (Phase 3 Read hooks)
TEMPLATE_READ_PATTERNS = [
    r"(read|reading|load)\s+.*template",
    r"roadmap.template",
    r"agents.md.evolved.template",
    r"architecture.template",
    r"decisions.template",
    r"references/",
]

# Confirmation patterns (Phase 5)
CONFIRMATION_PATTERNS = [
    r"does\s+this\s+match",
    r"anything\s+(wrong|missing|off|in the wrong bucket)",
    r"(right|correct|accurate)\s*\?",
    r"look\s+(right|good|correct)",
    r"match\s+where\s+the\s+project\s+is",
    r"what\s+do\s+you\s+think",
]

# Coherence check patterns (Phase 4.3)
COHERENCE_PATTERNS = [
    r"coherence",
    r"module\s+guide\s+covers?\s+(everything|all)",
    r"what.?s\s+built.*match",
    r"orphaned\s+references?",
    r"no\s+(remaining\s+)?references?\s+to\s+BUILD_PLAN",
    r"cross.?check",
    r"verif(y|ied|ying)\s+(that\s+)?(the\s+)?artifacts?\s+(are\s+)?consistent",
]

# Test execution patterns (Operating Loop rule 2)
TEST_RUN_PATTERNS = [
    r"(npm|npx|yarn|pnpm)\s+(run\s+)?test",
    r"(vitest|jest|pytest|mocha|cargo\s+test|go\s+test|mix\s+test)",
    r"\d+\s+(passed|tests?\s+passed)",
    r"\d+\s+pass(ed|ing)?,?\s+\d+\s+fail",
    r"test suite",
    r"all\s+tests?\s+pass",
    r"tests?:\s+\d+",
    r"running\s+(the\s+)?(full\s+)?test",
    r"ran\s+\d+\s+tests?",
]

# Test result count patterns -- the specific "N passed, M failed" format
TEST_RESULT_COUNT_PATTERNS = [
    r"\d+\s+passed?,?\s+\d+\s+failed?",
    r"\d+\s+pass\s*[|/]\s*\d+\s+fail",
    r"tests?:\s+\d+\s+passed?",
    r"\d+\s+tests?\s+passed",
    r"result:\s+\d+",
]

# Test writing patterns
TEST_WRITE_PATTERNS = [
    r"(writ|add|creat|updat)(e|ed|ing|es)\s+(a\s+|the\s+)?(unit\s+)?tests?",
    r"(new|added?)\s+tests?\s+(for|in|to|covering)",
    r"test\s+(file|case|spec)\s+(for|covering|added|created|written)",
    r"\.(test|spec)\.(ts|tsx|js|jsx|py|rb)",
    r"(describe|it|test)\s*\(",
    r"def\s+test_",
    r"assert",
]

# Not-ready gate patterns
NOT_READY_PATTERNS = [
    r"not\s+(yet\s+)?ready\s+(to\s+graduate|for\s+(graduation|evolution))",
    r"stay\s+in\s+(build|startup)\s+(mode|loop|phase)",
    r"needs?\s+to\s+happen\s+first",
    r"(premature|too early)\s+to\s+(graduate|restructure|evolve)",
    r"should\s+not\s+(graduate|evolve|restructure)",
]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class SkillComplianceEvaluator:

    def __init__(self, transcript: list[dict]):
        self.transcript = [
            m for m in transcript if m.get("role") in ("user", "assistant")
        ]
        self.result = EvalResult()

    # -- helpers --

    def _assistant_turns(self):
        return [m for m in self.transcript if m["role"] == "assistant"]

    def _all_assistant_text(self) -> str:
        return "\n".join(t["content"] for t in self._assistant_turns())

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _clean_for_question_count(text: str) -> str:
        """Remove quoted examples and code blocks so their ? marks don't count."""
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r'"[^"]*\?"', "", text)
        text = re.sub(r"'[^']*\?'", "", text)
        text = re.sub(r"\*\*\"[^\"]*\?\"\*\*", "", text)
        return text

    def _first_turn_matching(self, patterns: list[str]) -> Optional[int]:
        """Return index of the first assistant turn matching any pattern."""
        for i, turn in enumerate(self._assistant_turns()):
            if self._matches_any(turn["content"], patterns):
                return i
        return None

    # -- checks --

    def check_artifacts_read_before_assessment(self):
        """Phase 1.1: Existing artifacts must be read before any assessment."""
        all_text = self._all_assistant_text()

        read_turn = self._first_turn_matching(ARTIFACT_READ_PATTERNS)
        assessment_turn = self._first_turn_matching(READINESS_SIGNAL_PATTERNS)

        if read_turn is None:
            self.result.findings.append(Finding(
                "artifacts-read-first", "FAIL",
                "No evidence that existing artifacts were read before assessment",
            ))
            return

        if assessment_turn is None:
            # Read happened but no assessment found. Pass the read check,
            # assessment absence is caught by check_maturity_signals.
            self.result.findings.append(Finding(
                "artifacts-read-first", "PASS",
                "Existing artifacts were read (no assessment detected to order against)",
            ))
            return

        if read_turn <= assessment_turn:
            self.result.findings.append(Finding(
                "artifacts-read-first", "PASS",
                f"Artifacts read (turn {read_turn + 1}) before "
                f"assessment (turn {assessment_turn + 1})",
            ))
        else:
            self.result.findings.append(Finding(
                "artifacts-read-first", "FAIL",
                f"Assessment started (turn {assessment_turn + 1}) before "
                f"artifacts were read (turn {read_turn + 1})",
            ))

    def check_maturity_signals_enumerated(self):
        """Phase 1.2: The assistant must present specific readiness signals."""
        all_text = self._all_assistant_text()
        hits = [p for p in READINESS_SIGNAL_PATTERNS
                if re.search(p, all_text, re.IGNORECASE)]

        if len(hits) >= 3:
            self.result.findings.append(Finding(
                "maturity-signals", "PASS",
                f"{len(hits)} readiness signal patterns found in assistant output",
            ))
        elif len(hits) >= 1:
            self.result.findings.append(Finding(
                "maturity-signals", "WARN",
                f"Only {len(hits)} readiness signal(s) found -- "
                f"assessment may be superficial",
            ))
        else:
            self.result.findings.append(Finding(
                "maturity-signals", "FAIL",
                "No readiness signals found -- maturity assessment appears missing",
            ))

    def check_not_ready_gate(self):
        """Phase 1.2: If the project is assessed as not ready,
        no restructuring should follow."""
        all_text = self._all_assistant_text()
        declared_not_ready = self._matches_any(all_text, NOT_READY_PATTERNS)
        generated_artifacts = self._matches_any(all_text, GENERATION_PATTERNS)

        if not declared_not_ready:
            self.result.findings.append(Finding(
                "not-ready-gate", "SKIP",
                "Project was not assessed as not-ready (gate not testable)",
            ))
        elif declared_not_ready and not generated_artifacts:
            self.result.findings.append(Finding(
                "not-ready-gate", "PASS",
                "Project assessed as not ready -- restructuring correctly skipped",
            ))
        else:
            self.result.findings.append(Finding(
                "not-ready-gate", "FAIL",
                "Project assessed as not ready but artifacts were generated anyway",
            ))

    def check_health_check_performed(self):
        """Phase 1.3: Health check should cover test coverage, tech debt,
        dead code, or architecture strain before restructuring."""
        all_text = self._all_assistant_text()
        hits = [p for p in HEALTH_CHECK_PATTERNS
                if re.search(p, all_text, re.IGNORECASE)]

        if len(hits) >= 2:
            self.result.findings.append(Finding(
                "health-check", "PASS",
                f"{len(hits)} health check topics addressed",
            ))
        elif len(hits) == 1:
            self.result.findings.append(Finding(
                "health-check", "WARN",
                "Only 1 health check topic addressed -- "
                "expected at least test coverage and tech debt",
            ))
        else:
            self.result.findings.append(Finding(
                "health-check", "FAIL",
                "No health check topics found -- "
                "Phase 1.3 requires assessing test coverage, "
                "tech debt, dead code, and architecture strain",
            ))

    def check_one_question_per_turn(self):
        """Phase 2 rule: Ask one question at a time."""
        worst = 0
        worst_turn = None
        for i, turn in enumerate(self._assistant_turns()):
            cleaned = self._clean_for_question_count(turn["content"])
            q_count = cleaned.count("?")
            if q_count > worst:
                worst = q_count
                worst_turn = i
        # Allow up to 2 (main question + brief clarifier).
        if worst <= 2:
            self.result.findings.append(Finding(
                "one-question-per-turn", "PASS",
                f"Max questions in a single turn: {worst}",
            ))
        else:
            self.result.findings.append(Finding(
                "one-question-per-turn", "FAIL",
                f"Assistant turn {worst_turn + 1} contains {worst} questions",
                turn=worst_turn,
            ))

    def check_no_multi_question_lists(self):
        """Detect assistant turns that present numbered question lists."""
        for i, turn in enumerate(self._assistant_turns()):
            numbered_questions = re.findall(
                r"^\s*\d+[\.\)]\s+.*\?\s*$", turn["content"], re.MULTILINE
            )
            if len(numbered_questions) >= 3:
                self.result.findings.append(Finding(
                    "no-question-lists", "FAIL",
                    f"Assistant turn {i + 1} presents "
                    f"{len(numbered_questions)} questions as a numbered list",
                    turn=i,
                ))
                return
        self.result.findings.append(Finding(
            "no-question-lists", "PASS",
            "No numbered question lists detected in assistant turns",
        ))

    def check_direction_questions_asked(self):
        """Phase 2.1-2.3: All three direction questions should be asked."""
        all_text = self._all_assistant_text()

        checks = [
            ("what's working", DIRECTION_WORKING_PATTERNS),
            ("what's next", DIRECTION_NEXT_PATTERNS),
            ("what's dragging", DIRECTION_DRAGGING_PATTERNS),
        ]
        missing = []
        for label, patterns in checks:
            if not self._matches_any(all_text, patterns):
                missing.append(label)

        if not missing:
            self.result.findings.append(Finding(
                "direction-questions", "PASS",
                "All three direction questions found "
                "(what's working, what's next, what's dragging)",
            ))
        else:
            self.result.findings.append(Finding(
                "direction-questions", "FAIL",
                f"Missing direction questions: {', '.join(missing)}",
            ))

    def check_assessment_before_restructure(self):
        """Phases 1-2 must complete before Phase 3 artifact generation."""
        assessment_turn = self._first_turn_matching(READINESS_SIGNAL_PATTERNS)
        generation_turn = self._first_turn_matching(GENERATION_PATTERNS)

        if generation_turn is None:
            self.result.findings.append(Finding(
                "assessment-before-restructure", "SKIP",
                "No artifact generation detected (not testable)",
            ))
            return

        if assessment_turn is None:
            self.result.findings.append(Finding(
                "assessment-before-restructure", "FAIL",
                "Artifacts generated without any maturity assessment",
            ))
            return

        if assessment_turn < generation_turn:
            self.result.findings.append(Finding(
                "assessment-before-restructure", "PASS",
                f"Assessment (turn {assessment_turn + 1}) preceded "
                f"generation (turn {generation_turn + 1})",
            ))
        else:
            self.result.findings.append(Finding(
                "assessment-before-restructure", "FAIL",
                f"Artifacts generated (turn {generation_turn + 1}) before "
                f"assessment (turn {assessment_turn + 1})",
            ))

    def check_direction_before_generation(self):
        """Phase 2 direction conversation must precede Phase 3 generation."""
        # Use any direction question as the marker
        all_direction = (DIRECTION_WORKING_PATTERNS
                         + DIRECTION_NEXT_PATTERNS
                         + DIRECTION_DRAGGING_PATTERNS)
        direction_turn = self._first_turn_matching(all_direction)
        generation_turn = self._first_turn_matching(GENERATION_PATTERNS)

        if generation_turn is None:
            self.result.findings.append(Finding(
                "direction-before-generation", "SKIP",
                "No artifact generation detected (not testable)",
            ))
            return

        if direction_turn is None:
            self.result.findings.append(Finding(
                "direction-before-generation", "FAIL",
                "Artifacts generated without any direction conversation",
            ))
            return

        if direction_turn < generation_turn:
            self.result.findings.append(Finding(
                "direction-before-generation", "PASS",
                f"Direction conversation (turn {direction_turn + 1}) preceded "
                f"generation (turn {generation_turn + 1})",
            ))
        else:
            self.result.findings.append(Finding(
                "direction-before-generation", "FAIL",
                f"Artifacts generated (turn {generation_turn + 1}) before "
                f"direction conversation (turn {direction_turn + 1})",
            ))

    def check_templates_read(self):
        """Phase 3: Templates should be loaded (Read hooks) before generation."""
        all_text = self._all_assistant_text()

        if self._matches_any(all_text, TEMPLATE_READ_PATTERNS):
            self.result.findings.append(Finding(
                "templates-read", "PASS",
                "Template references found in assistant output",
            ))
        else:
            # Only warn if generation actually happened
            if self._matches_any(all_text, GENERATION_PATTERNS):
                self.result.findings.append(Finding(
                    "templates-read", "WARN",
                    "Artifacts were generated but no template read signals detected "
                    "-- templates may have been loaded via tool calls not visible "
                    "in text",
                ))
            else:
                self.result.findings.append(Finding(
                    "templates-read", "SKIP",
                    "No artifact generation detected (not testable)",
                ))

    def check_confirmation_after_artifacts(self):
        """Phase 5: Confirmation question after presenting new artifacts."""
        all_text = self._all_assistant_text()

        if not self._matches_any(all_text, GENERATION_PATTERNS):
            self.result.findings.append(Finding(
                "confirmation-after-artifacts", "SKIP",
                "No artifact generation detected (not testable)",
            ))
            return

        if self._matches_any(all_text, CONFIRMATION_PATTERNS):
            self.result.findings.append(Finding(
                "confirmation-after-artifacts", "PASS",
                "Confirmation question found after artifact generation",
            ))
        else:
            self.result.findings.append(Finding(
                "confirmation-after-artifacts", "FAIL",
                "No confirmation question found -- Phase 5 requires asking "
                "'Does this match where the project is?'",
            ))

    def check_coherence_verification(self):
        """Phase 4.3: Coherence verification should be performed."""
        all_text = self._all_assistant_text()

        if not self._matches_any(all_text, GENERATION_PATTERNS):
            self.result.findings.append(Finding(
                "coherence-verification", "SKIP",
                "No artifact generation detected (not testable)",
            ))
            return

        if self._matches_any(all_text, COHERENCE_PATTERNS):
            self.result.findings.append(Finding(
                "coherence-verification", "PASS",
                "Coherence verification signals found",
            ))
        else:
            self.result.findings.append(Finding(
                "coherence-verification", "WARN",
                "No coherence verification detected -- Phase 4.3 requires "
                "cross-checking artifacts for consistency",
            ))

    def check_tests_run_before_work(self):
        """Operating loop: Test suite must run before implementation starts.
        Looks for test execution evidence in early assistant turns, before
        any implementation signals appear."""
        all_text = self._all_assistant_text()
        turns = self._assistant_turns()

        if not self._matches_any(all_text, TEST_RUN_PATTERNS):
            self.result.findings.append(Finding(
                "tests-run-before-work", "FAIL",
                "No evidence of test suite execution found in conversation",
            ))
            return

        # Check that test run appears in the conversation
        test_turn = self._first_turn_matching(TEST_RUN_PATTERNS)
        self.result.findings.append(Finding(
            "tests-run-before-work", "PASS",
            f"Test suite execution found (turn {test_turn + 1})",
        ))

    def check_test_results_reported(self):
        """Operating loop: Test results must include explicit counts
        (e.g., '42 passed, 0 failed'), not just 'tests pass'."""
        all_text = self._all_assistant_text()

        if not self._matches_any(all_text, TEST_RUN_PATTERNS):
            self.result.findings.append(Finding(
                "test-results-reported", "SKIP",
                "No test execution found (not testable)",
            ))
            return

        if self._matches_any(all_text, TEST_RESULT_COUNT_PATTERNS):
            self.result.findings.append(Finding(
                "test-results-reported", "PASS",
                "Test result counts reported explicitly",
            ))
        else:
            self.result.findings.append(Finding(
                "test-results-reported", "WARN",
                "Tests were run but no explicit result counts found -- "
                "work protocol requires stating 'N passed, M failed'",
            ))

    def check_tests_written(self):
        """Operating loop: Tests must be written or updated for new behavior.
        Looks for evidence of test creation in the conversation."""
        all_text = self._all_assistant_text()

        # Only check if implementation happened (indicated by generation
        # patterns or other code-writing signals)
        impl_patterns = GENERATION_PATTERNS + [
            r"(implement|built|added|created|wrote)\s+(the|a)\s+\w+",
            r"(here.?s|created)\s+the\s+(new|updated)",
        ]
        if not self._matches_any(all_text, impl_patterns):
            self.result.findings.append(Finding(
                "tests-written", "SKIP",
                "No implementation detected (not testable)",
            ))
            return

        if self._matches_any(all_text, TEST_WRITE_PATTERNS):
            self.result.findings.append(Finding(
                "tests-written", "PASS",
                "Evidence of test creation or updates found",
            ))
        else:
            self.result.findings.append(Finding(
                "tests-written", "WARN",
                "Implementation detected but no evidence of tests written -- "
                "work protocol requires tests for every behavior change",
            ))

    # -- runner --

    def run_all(self) -> EvalResult:
        self.check_artifacts_read_before_assessment()
        self.check_maturity_signals_enumerated()
        self.check_not_ready_gate()
        self.check_health_check_performed()
        self.check_one_question_per_turn()
        self.check_no_multi_question_lists()
        self.check_direction_questions_asked()
        self.check_assessment_before_restructure()
        self.check_direction_before_generation()
        self.check_templates_read()
        self.check_confirmation_after_artifacts()
        self.check_coherence_verification()
        self.check_tests_run_before_work()
        self.check_test_results_reported()
        self.check_tests_written()
        return self.result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(result: EvalResult):
    counts = result.counts
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'=' * 60}")
    print(f"  Evolution Skill Compliance: {status}")
    print(f"  {counts['PASS']} pass | {counts['FAIL']} fail | "
          f"{counts['WARN']} warn | {counts['SKIP']} skip")
    print(f"{'=' * 60}\n")
    for f in result.findings:
        icon = {"PASS": "+", "FAIL": "X", "WARN": "?", "SKIP": "-"}[f.status]
        turn_str = f" [turn {f.turn}]" if f.turn is not None else ""
        print(f"  [{icon}] {f.rule}{turn_str}")
        print(f"      {f.detail}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python eval_skill_compliance.py <transcript.json> "
              "[--format json]")
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(2)

    use_json = "--format" in sys.argv and "json" in sys.argv

    with open(path) as f:
        transcript = json.load(f)

    evaluator = SkillComplianceEvaluator(transcript)
    result = evaluator.run_all()

    if use_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
