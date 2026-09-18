"""
Skill Compliance Evaluator for product-delivery

Validates that a conversation transcript follows the skill's behavioral rules.
Merges checks from product-discovery and product-evolution compliance evaluators
and adds state-machine-specific checks.

Input:  Path to a conversation transcript JSON file.
Output: Structured report to stdout. Exit code 0 = all pass, 1 = any fail.

Usage:
    python eval_skill_compliance.py <transcript.json>
    python eval_skill_compliance.py <transcript.json> --format json
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

    def to_dict(self):
        return {"rule": self.rule, "status": self.status, "detail": self.detail}


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


def _get_assistant_messages(transcript: list) -> list[str]:
    return [m["content"] for m in transcript if m.get("role") == "assistant" and isinstance(m.get("content"), str)]


def _get_all_text(transcript: list) -> str:
    parts = []
    for m in transcript:
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Shared checks (from both legacy skills)
# ---------------------------------------------------------------------------

def check_one_question_per_turn(assistant_msgs: list[str], result: EvalResult):
    violations = 0
    for msg in assistant_msgs:
        questions = re.findall(r"\?", msg)
        if len(questions) > 3:
            violations += 1
    if violations > 0:
        result.findings.append(Finding(
            "one-question-per-turn", "WARN",
            f"{violations} assistant message(s) contain more than 3 question marks (possible multi-question turn)",
        ))
    else:
        result.findings.append(Finding(
            "one-question-per-turn", "PASS",
            "Assistant messages generally ask one question at a time",
        ))


def check_no_numbered_question_lists(assistant_msgs: list[str], result: EvalResult):
    for msg in assistant_msgs:
        if re.search(r"^\s*\d+\.\s+.+\?\s*$", msg, re.MULTILINE):
            result.findings.append(Finding(
                "no-question-lists", "WARN",
                "Found numbered list of questions in an assistant message",
            ))
            return
    result.findings.append(Finding(
        "no-question-lists", "PASS",
        "No numbered question lists found",
    ))


def check_category_word_pushback(all_text: str, result: EvalResult):
    category_patterns = [
        r"all kinds of",
        r"various .*(data|sources|users|platforms)",
        r"different (types|kinds) of",
    ]
    user_uses_vague = any(re.search(p, all_text, re.IGNORECASE) for p in category_patterns)
    if not user_uses_vague:
        result.findings.append(Finding(
            "category-word-pushback", "SKIP",
            "No category words detected in conversation",
        ))
        return

    pushback_patterns = [
        r"pick one specific",
        r"name (a |one )specific",
        r"which specific",
        r"who specifically",
        r"describe their context",
    ]
    has_pushback = any(re.search(p, all_text, re.IGNORECASE) for p in pushback_patterns)
    if has_pushback:
        result.findings.append(Finding(
            "category-word-pushback", "PASS",
            "Assistant pushed back on category words",
        ))
    else:
        result.findings.append(Finding(
            "category-word-pushback", "FAIL",
            "Category words used but no pushback detected",
        ))


def check_quality_word_pushback(all_text: str, result: EvalResult):
    quality_words = [r"\bfast\b", r"\beasy\b", r"\bintuitive\b", r"\bsimple\b", r"\bclean\b"]
    has_quality = any(re.search(w, all_text, re.IGNORECASE) for w in quality_words)
    if not has_quality:
        result.findings.append(Finding(
            "quality-word-pushback", "SKIP",
            "No quality words detected",
        ))
        return

    pushback_patterns = [
        r"what would you (see|measure)",
        r"what.s the (bar|minimum|threshold)",
        r"compared to what",
        r"how would you know",
    ]
    has_pushback = any(re.search(p, all_text, re.IGNORECASE) for p in pushback_patterns)
    if has_pushback:
        result.findings.append(Finding(
            "quality-word-pushback", "PASS",
            "Assistant pushed back on quality words",
        ))
    else:
        result.findings.append(Finding(
            "quality-word-pushback", "WARN",
            "Quality words used but no pushback detected",
        ))


# ---------------------------------------------------------------------------
# Discovery-path checks
# ---------------------------------------------------------------------------

def check_product_summary_present(all_text: str, result: EvalResult):
    if re.search(r"(product summary|project brief)", all_text, re.IGNORECASE):
        result.findings.append(Finding(
            "brief-present", "PASS",
            "Product summary or project brief present in conversation",
        ))
    else:
        result.findings.append(Finding(
            "brief-present", "WARN",
            "No product summary or project brief detected",
        ))


def check_synthesis_confirmation(all_text: str, result: EvalResult):
    patterns = [
        r"does this (look|sound) right",
        r"is this (correct|accurate)",
        r"confirm",
        r"right\?",
        r"anything (wrong|missing|to change)",
    ]
    if any(re.search(p, all_text, re.IGNORECASE) for p in patterns):
        result.findings.append(Finding(
            "synthesis-confirmation", "PASS",
            "Synthesis confirmation question detected",
        ))
    else:
        result.findings.append(Finding(
            "synthesis-confirmation", "WARN",
            "No synthesis confirmation detected",
        ))


def check_assumed_markers(all_text: str, result: EvalResult):
    if "[ASSUMED]" in all_text:
        result.findings.append(Finding(
            "assumed-markers", "PASS",
            "[ASSUMED] markers present where gaps were filled",
        ))
    else:
        result.findings.append(Finding(
            "assumed-markers", "SKIP",
            "No [ASSUMED] markers (not necessarily needed)",
        ))


# ---------------------------------------------------------------------------
# Evolution-path checks
# ---------------------------------------------------------------------------

def check_artifacts_read_before_assessment(all_text: str, result: EvalResult):
    read_patterns = [r"read.*AGENTS\.md", r"read.*BUILD_PLAN", r"read.*ROADMAP", r"reading.*existing"]
    assessment_patterns = [r"maturity.*assess", r"ready to (graduate|evolve)", r"health check"]

    has_read = any(re.search(p, all_text, re.IGNORECASE) for p in read_patterns)
    has_assessment = any(re.search(p, all_text, re.IGNORECASE) for p in assessment_patterns)

    if not has_assessment:
        result.findings.append(Finding(
            "artifacts-read-before-assessment", "SKIP",
            "No maturity assessment detected (likely greenfield path)",
        ))
    elif has_read:
        result.findings.append(Finding(
            "artifacts-read-before-assessment", "PASS",
            "Existing artifacts read before assessment",
        ))
    else:
        result.findings.append(Finding(
            "artifacts-read-before-assessment", "WARN",
            "Assessment performed but no evidence of reading existing artifacts first",
        ))


def check_health_check_performed(all_text: str, result: EvalResult):
    patterns = [
        r"test coverage",
        r"tech debt",
        r"dead code",
        r"architecture strain",
        r"health check",
        r"codebase health",
    ]
    if any(re.search(p, all_text, re.IGNORECASE) for p in patterns):
        result.findings.append(Finding(
            "health-check-performed", "PASS",
            "Codebase health check evidence found",
        ))
    else:
        result.findings.append(Finding(
            "health-check-performed", "SKIP",
            "No health check evidence (may be greenfield path)",
        ))


def check_direction_questions(all_text: str, result: EvalResult):
    working = re.search(r"what.s (working|the strongest)", all_text, re.IGNORECASE)
    next_q = re.search(r"(most important|what.s next|next month)", all_text, re.IGNORECASE)
    dragging = re.search(r"(most annoying|what.s dragging|dragging)", all_text, re.IGNORECASE)

    found = sum(1 for q in [working, next_q, dragging] if q)
    if found == 0:
        result.findings.append(Finding(
            "direction-questions-asked", "SKIP",
            "No direction questions detected (likely greenfield path)",
        ))
    elif found == 3:
        result.findings.append(Finding(
            "direction-questions-asked", "PASS",
            "All three direction questions asked",
        ))
    else:
        result.findings.append(Finding(
            "direction-questions-asked", "WARN",
            f"Only {found}/3 direction questions detected",
        ))


def check_tests_run(all_text: str, result: EvalResult):
    patterns = [
        r"\d+\s+passed",
        r"\d+\s+failed",
        r"tests? pass",
        r"test suite",
        r"all tests",
    ]
    if any(re.search(p, all_text, re.IGNORECASE) for p in patterns):
        result.findings.append(Finding(
            "tests-run", "PASS",
            "Test execution evidence found",
        ))
    else:
        result.findings.append(Finding(
            "tests-run", "WARN",
            "No test execution evidence found",
        ))


def check_test_results_reported(all_text: str, result: EvalResult):
    if re.search(r"\d+\s+passed,?\s+\d+\s+failed", all_text, re.IGNORECASE):
        result.findings.append(Finding(
            "test-results-reported", "PASS",
            "Test results reported with counts",
        ))
    else:
        result.findings.append(Finding(
            "test-results-reported", "WARN",
            "No specific test count reporting found (expected 'N passed, M failed')",
        ))


# ---------------------------------------------------------------------------
# State machine checks (new for product-delivery)
# ---------------------------------------------------------------------------

def check_state_transitions_logged(all_text: str, result: EvalResult):
    patterns = [
        r"workflow (init|transition|status)",
        r"transition.*→",
        r"Transitioned:",
        r"phase.*→",
        r"state\.json",
    ]
    if any(re.search(p, all_text) for p in patterns):
        result.findings.append(Finding(
            "state-transitions-logged", "PASS",
            "State transition logging evidence found",
        ))
    else:
        result.findings.append(Finding(
            "state-transitions-logged", "WARN",
            "No state transition logging detected",
        ))


def check_evidence_referenced(all_text: str, result: EvalResult):
    patterns = [
        r"EVD-\d{3}",
        r"evidence",
        r"\.workflow/evidence",
    ]
    if any(re.search(p, all_text) for p in patterns):
        result.findings.append(Finding(
            "evidence-referenced", "PASS",
            "Evidence references found in conversation",
        ))
    else:
        result.findings.append(Finding(
            "evidence-referenced", "WARN",
            "No evidence references detected",
        ))


def check_stable_ids_used(all_text: str, result: EvalResult):
    id_patterns = [r"AC-\d{3}", r"WI-\d{3}", r"RISK-\d{3}", r"DEC-\d{3}"]
    found = [p for p in id_patterns if re.search(p, all_text)]
    if found:
        result.findings.append(Finding(
            "stable-ids-used", "PASS",
            f"Stable IDs found: {', '.join(found)}",
        ))
    else:
        result.findings.append(Finding(
            "stable-ids-used", "WARN",
            "No stable IDs (AC-NNN, WI-NNN, etc.) detected",
        ))


def check_coherence_verification(all_text: str, result: EvalResult):
    patterns = [
        r"coherence",
        r"cross-artifact",
        r"verify.*consistency",
        r"orphaned references",
    ]
    if any(re.search(p, all_text, re.IGNORECASE) for p in patterns):
        result.findings.append(Finding(
            "coherence-verification", "PASS",
            "Coherence verification evidence found",
        ))
    else:
        result.findings.append(Finding(
            "coherence-verification", "SKIP",
            "No coherence verification detected (may not have reached release phase)",
        ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_eval(transcript: list) -> EvalResult:
    result = EvalResult()
    assistant_msgs = _get_assistant_messages(transcript)
    all_text = _get_all_text(transcript)

    # Shared checks
    check_one_question_per_turn(assistant_msgs, result)
    check_no_numbered_question_lists(assistant_msgs, result)
    check_category_word_pushback(all_text, result)
    check_quality_word_pushback(all_text, result)

    # Discovery-path checks
    check_product_summary_present(all_text, result)
    check_synthesis_confirmation(all_text, result)
    check_assumed_markers(all_text, result)

    # Evolution-path checks
    check_artifacts_read_before_assessment(all_text, result)
    check_health_check_performed(all_text, result)
    check_direction_questions(all_text, result)

    # Delivery checks
    check_tests_run(all_text, result)
    check_test_results_reported(all_text, result)

    # State machine checks
    check_state_transitions_logged(all_text, result)
    check_evidence_referenced(all_text, result)
    check_stable_ids_used(all_text, result)
    check_coherence_verification(all_text, result)

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Product Delivery Skill Compliance Evaluator")
    parser.add_argument("transcript", help="Path to conversation transcript JSON")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Error: {transcript_path} not found", file=sys.stderr)
        sys.exit(2)

    with open(transcript_path) as f:
        transcript = json.load(f)

    if not isinstance(transcript, list):
        print("Error: transcript must be a JSON array of messages", file=sys.stderr)
        sys.exit(2)

    result = run_eval(transcript)

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        counts = result.counts
        print(f"\n{'=' * 60}")
        print(f"Skill Compliance Eval: {'PASS' if result.passed else 'FAIL'}")
        print(f"{'=' * 60}")
        print(f"  PASS: {counts['PASS']}  FAIL: {counts['FAIL']}  WARN: {counts['WARN']}  SKIP: {counts['SKIP']}")
        print()
        for f in result.findings:
            marker = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "○"}[f.status]
            print(f"  {marker} {f.rule}: {f.detail}")
        print()

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
