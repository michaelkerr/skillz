"""
Skill Compliance Evaluator for product-startup

Checks whether a conversation transcript follows the skill's operational
rules. This is a "did the model obey the instructions?" test, not a
"was the output good?" test.

Input:  JSON file -- array of {"role": "user"|"assistant"|"system", "content": "..."}
Output: Structured report to stdout. Exit code 0 = all pass, 1 = any fail.

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
# Pattern banks -- derived directly from the skill's operational rules
# ---------------------------------------------------------------------------

# Insufficient-answer patterns the skill requires pushback on.
# Each tuple: (pattern list for user turn, expected response patterns, rule name, label)

CATEGORY_WORD_TRIGGERS = [
    r"all kinds of",
    r"various\s+\w+",
    r"different\s+(platforms|users|sources|types|tools)",
    r"(many|most|all)\s+(people|users|customers|teams)",
    r"\beveryone\b",
    r"\banybody\b",
]

CATEGORY_WORD_RESPONSES = [
    r"pick one specific",
    r"one specific person",
    r"describe their context",
    r"what.?s their job",
    r"who specifically",
    r"by role or context",
]

QUALITY_WORD_TRIGGERS = [
    r"\bfast\b",
    r"\beasy\b",
    r"\bintuitive\b",
    r"\bclean\b",
    r"\bsimple\b",
    r"\bseamless\b",
    r"\bsmooth\b",
    r"\bfriendly\b",
]

QUALITY_WORD_RESPONSES = [
    r"what would you (see|measure)",
    r"what.?s the (bar|minimum|benchmark)",
    r"compared to what",
    r"how would you know",
    r"describe the moment",
]

DEFERRED_TRIGGERS = [
    r"\bit depends\b",
    r"\bprobably\b",
    r"maybe some kind of",
    r"something like\b",
    r"i.?m not sure",
    r"i haven.?t decided",
    r"not sure yet",
]

DEFERRED_RESPONSES = [
    r"(pick|let.?s pick) one concrete",
    r"in that case",
    r"one specific (case|example|scenario)",
    r"what happens\??$",
]

SOLUTION_TRIGGERS = [
    r"i want to build\b",
    r"i.?m building\b",
    r"let.?s build\b",
    r"(make|build|create) me a\b",
    r"can you (make|build|create)\b",
]

PROBLEM_RESPONSES = [
    r"what problem",
    r"problem does it solve",
    r"what.?s the pain",
    r"why do (they|you) need",
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

    def _pairs(self):
        """Yield (index, user_msg, assistant_msg) for consecutive pairs."""
        for i in range(len(self.transcript) - 1):
            if (self.transcript[i]["role"] == "user"
                    and self.transcript[i + 1]["role"] == "assistant"):
                yield i, self.transcript[i], self.transcript[i + 1]

    def _assistant_turns(self):
        return [m for m in self.transcript if m["role"] == "assistant"]

    @staticmethod
    def _clean_for_question_count(text: str) -> str:
        """Remove quoted examples and code blocks so their ? marks don't count."""
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r'"[^"]*\?"', "", text)
        text = re.sub(r"'[^']*\?'", "", text)
        # Remove example prompts in bold that contain ?
        text = re.sub(r"\*\*\"[^\"]*\?\"\*\*", "", text)
        return text

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    # -- checks --

    def check_one_question_per_turn(self):
        """Rule: 'Ask one question at a time. Do not present all questions as a list.'"""
        worst = 0
        worst_turn = None
        for i, turn in enumerate(self._assistant_turns()):
            cleaned = self._clean_for_question_count(turn["content"])
            q_count = cleaned.count("?")
            if q_count > worst:
                worst = q_count
                worst_turn = i
        # Allow up to 2 (main question + brief clarifier or confirmation).
        # 3+ is a violation.
        if worst <= 2:
            self.result.findings.append(Finding(
                "one-question-per-turn", "PASS",
                f"Max questions in a single turn: {worst}"
            ))
        else:
            self.result.findings.append(Finding(
                "one-question-per-turn", "FAIL",
                f"Assistant turn {worst_turn + 1} contains {worst} questions",
                turn=worst_turn
            ))

    def _check_pushback(self, triggers, responses, rule, label):
        """Generic: if user turn matches a trigger, next assistant turn must match a response."""
        triggered = False
        for idx, user, asst in self._pairs():
            if self._matches_any(user["content"], triggers):
                triggered = True
                if self._matches_any(asst["content"], responses):
                    self.result.findings.append(Finding(
                        rule, "PASS",
                        f"Turn {idx}: {label} detected, pushback given",
                        turn=idx
                    ))
                else:
                    self.result.findings.append(Finding(
                        rule, "FAIL",
                        f"Turn {idx}: user used {label} but no matching pushback followed",
                        turn=idx
                    ))
        if not triggered:
            self.result.findings.append(Finding(
                rule, "SKIP",
                f"No {label} detected in user turns (not testable in this transcript)"
            ))

    def check_category_word_pushback(self):
        self._check_pushback(
            CATEGORY_WORD_TRIGGERS, CATEGORY_WORD_RESPONSES,
            "category-word-pushback", "category words without instances"
        )

    def check_quality_word_pushback(self):
        self._check_pushback(
            QUALITY_WORD_TRIGGERS, QUALITY_WORD_RESPONSES,
            "quality-word-pushback", "quality words without measures"
        )

    def check_deferred_specifics_pushback(self):
        self._check_pushback(
            DEFERRED_TRIGGERS, DEFERRED_RESPONSES,
            "deferred-specifics-pushback", "deferred specifics"
        )

    def check_solution_without_problem(self):
        """If the user's first substantive turn is a solution, assistant must ask for the problem."""
        user_turns = [m for m in self.transcript if m["role"] == "user"]
        if not user_turns:
            self.result.findings.append(Finding(
                "solution-without-problem", "SKIP", "No user turns found"
            ))
            return
        first = user_turns[0]["content"]
        if self._matches_any(first, SOLUTION_TRIGGERS):
            # Find the assistant response to this
            for idx, user, asst in self._pairs():
                if user["content"] == first:
                    if self._matches_any(asst["content"], PROBLEM_RESPONSES):
                        self.result.findings.append(Finding(
                            "solution-without-problem", "PASS",
                            "User led with a solution, assistant asked about the problem",
                            turn=idx
                        ))
                    else:
                        self.result.findings.append(Finding(
                            "solution-without-problem", "FAIL",
                            "User led with a solution but assistant did not ask what problem it solves",
                            turn=idx
                        ))
                    return
        self.result.findings.append(Finding(
            "solution-without-problem", "SKIP",
            "User's first turn was not a solution statement"
        ))

    def check_product_summary_present(self):
        """The skill requires a Product Summary block before proceeding to the build plan."""
        all_assistant = "\n".join(t["content"] for t in self._assistant_turns())
        # Check for the five required fields
        fields = [
            r"\*\*Problem\*\*",
            r"\*\*User\*\*",
            r"\*\*Core interaction\*\*",
            r"\*\*Success criteria\*\*",
            r"\*\*Constraints\*\*",
        ]
        found = [bool(re.search(f, all_assistant, re.IGNORECASE)) for f in fields]
        if all(found):
            self.result.findings.append(Finding(
                "product-summary-present", "PASS",
                "All five Product Summary fields found in assistant output"
            ))
        else:
            missing = [
                name for name, f in zip(
                    ["Problem", "User", "Core interaction", "Success criteria", "Constraints"],
                    found
                ) if not f
            ]
            self.result.findings.append(Finding(
                "product-summary-present", "FAIL",
                f"Product Summary missing fields: {', '.join(missing)}"
            ))

    def check_confirmation_after_synthesis(self):
        """1.6 requires confirming the summary with the user before proceeding."""
        all_assistant = "\n".join(t["content"] for t in self._assistant_turns())
        confirm_patterns = [
            r"(right|correct|accurate)\s*\?",
            r"anything.*(wrong|missing|off)\s*\?",
            r"does (this|that) (capture|match|look)",
            r"confirm",
        ]
        if any(re.search(p, all_assistant, re.IGNORECASE) for p in confirm_patterns):
            self.result.findings.append(Finding(
                "synthesis-confirmation", "PASS",
                "Confirmation question found after synthesis"
            ))
        else:
            self.result.findings.append(Finding(
                "synthesis-confirmation", "WARN",
                "Could not detect a confirmation question after Product Summary"
            ))

    def check_no_multi_question_lists(self):
        """Detect assistant turns that present numbered question lists."""
        for i, turn in enumerate(self._assistant_turns()):
            content = turn["content"]
            # Look for numbered lists where items end in ?
            numbered_questions = re.findall(
                r"^\s*\d+[\.\)]\s+.*\?\s*$", content, re.MULTILINE
            )
            if len(numbered_questions) >= 3:
                self.result.findings.append(Finding(
                    "no-question-lists", "FAIL",
                    f"Assistant turn {i + 1} presents {len(numbered_questions)} questions as a numbered list",
                    turn=i
                ))
                return
        self.result.findings.append(Finding(
            "no-question-lists", "PASS",
            "No numbered question lists detected in assistant turns"
        ))

    def check_assumed_markers(self):
        """If the conversation ends abruptly (few turns), check for [ASSUMED] markers."""
        user_turns = [m for m in self.transcript if m["role"] == "user"]
        all_assistant = "\n".join(t["content"] for t in self._assistant_turns())
        # The [ASSUMED] pattern matters when the user skipped discovery
        skip_patterns = [
            r"just build",
            r"skip (this|the|discovery|questions)",
            r"don.?t need to (plan|discuss|talk)",
            r"let.?s just (start|code|go)",
        ]
        user_skipped = any(
            self._matches_any(t["content"], skip_patterns) for t in user_turns
        )
        if user_skipped:
            if "[ASSUMED]" in all_assistant:
                self.result.findings.append(Finding(
                    "assumed-markers", "PASS",
                    "User skipped discovery; [ASSUMED] markers present in output"
                ))
            else:
                self.result.findings.append(Finding(
                    "assumed-markers", "FAIL",
                    "User skipped discovery but no [ASSUMED] markers in output"
                ))
        else:
            self.result.findings.append(Finding(
                "assumed-markers", "SKIP",
                "User did not skip discovery (not testable)"
            ))

    # -- runner --

    def run_all(self) -> EvalResult:
        self.check_one_question_per_turn()
        self.check_no_multi_question_lists()
        self.check_category_word_pushback()
        self.check_quality_word_pushback()
        self.check_deferred_specifics_pushback()
        self.check_solution_without_problem()
        self.check_product_summary_present()
        self.check_confirmation_after_synthesis()
        self.check_assumed_markers()
        return self.result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(result: EvalResult):
    counts = result.counts
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'=' * 60}")
    print(f"  Skill Compliance: {status}")
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
        print("Usage: python eval_skill_compliance.py <transcript.json> [--format json]")
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
