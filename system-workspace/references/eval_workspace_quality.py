"""
Output Quality Evaluator for system-workspace

Validates the structural correctness of the workspace-level artifacts:
workspace.json, AGENTS.md, and CLAUDE.md against the skill's requirements.
This tests whether the artifacts are well-formed, not whether the content
is good.

Input:  Path to a workspace directory containing the artifacts.
Output: Structured report to stdout.  Exit code 0 = all pass, 1 = any fail.

Usage:
    python eval_workspace_quality.py /path/to/workspace
    python eval_workspace_quality.py /path/to/workspace --format json
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
# workspace.json checks
# ---------------------------------------------------------------------------

class WorkspaceManifestChecker:

    def __init__(self, text: str, workspace_dir: Path, result: EvalResult):
        self.text = text
        self.workspace_dir = workspace_dir
        self.result = result
        self.manifest = None

    def check_file_present(self) -> bool:
        if not self.text.strip():
            self.result.findings.append(Finding(
                "manifest-present", "FAIL",
                "workspace.json is empty or missing",
                file="workspace.json",
            ))
            return False
        self.result.findings.append(Finding(
            "manifest-present", "PASS",
            "workspace.json exists and is non-empty",
            file="workspace.json",
        ))
        return True

    def check_valid_json(self) -> bool:
        try:
            self.manifest = json.loads(self.text)
            self.result.findings.append(Finding(
                "manifest-valid-json", "PASS",
                "workspace.json is valid JSON",
                file="workspace.json",
            ))
            return True
        except json.JSONDecodeError as e:
            self.result.findings.append(Finding(
                "manifest-valid-json", "FAIL",
                f"workspace.json is not valid JSON: {e}",
                file="workspace.json",
            ))
            return False

    def check_has_repos(self) -> bool:
        if not isinstance(self.manifest, dict):
            self.result.findings.append(Finding(
                "manifest-repos-key", "FAIL",
                "workspace.json root is not an object",
                file="workspace.json",
            ))
            return False

        repos = self.manifest.get("repos")
        if not isinstance(repos, list):
            self.result.findings.append(Finding(
                "manifest-repos-key", "FAIL",
                "workspace.json missing 'repos' array",
                file="workspace.json",
            ))
            return False

        if len(repos) < 2:
            self.result.findings.append(Finding(
                "manifest-repos-key", "FAIL",
                f"workspace.json has {len(repos)} repo(s); minimum is 2",
                file="workspace.json",
            ))
            return False

        self.result.findings.append(Finding(
            "manifest-repos-key", "PASS",
            f"workspace.json has {len(repos)} repos",
            file="workspace.json",
        ))
        return True

    def check_repo_fields(self):
        repos = self.manifest.get("repos", [])
        issues = []
        for i, repo in enumerate(repos):
            if not isinstance(repo, dict):
                issues.append(f"Entry {i} is not an object")
                continue
            if "path" not in repo:
                issues.append(f"Entry {i} missing 'path'")
            if "name" not in repo:
                issues.append(f"Entry {i} missing 'name'")
        if issues:
            self.result.findings.append(Finding(
                "manifest-repo-fields", "FAIL",
                "; ".join(issues),
                file="workspace.json",
            ))
        else:
            self.result.findings.append(Finding(
                "manifest-repo-fields", "PASS",
                "All repo entries have 'path' and 'name'",
                file="workspace.json",
            ))

    def check_unique_names(self):
        repos = self.manifest.get("repos", [])
        names = [r.get("name", "") for r in repos if isinstance(r, dict)]
        dupes = [n for n in set(names) if names.count(n) > 1]
        if dupes:
            self.result.findings.append(Finding(
                "manifest-unique-names", "FAIL",
                f"Duplicate repo names: {', '.join(dupes)}",
                file="workspace.json",
            ))
        else:
            self.result.findings.append(Finding(
                "manifest-unique-names", "PASS",
                "All repo names are unique",
                file="workspace.json",
            ))

    def check_paths_exist(self):
        repos = self.manifest.get("repos", [])
        missing = []
        for repo in repos:
            if not isinstance(repo, dict):
                continue
            path = repo.get("path", "")
            resolved = (self.workspace_dir / path).resolve()
            if not resolved.is_dir():
                missing.append(f"{repo.get('name', '?')} ({path})")
        if missing:
            self.result.findings.append(Finding(
                "manifest-paths-exist", "WARN",
                f"Repo directories not found: {', '.join(missing)}",
                file="workspace.json",
            ))
        else:
            self.result.findings.append(Finding(
                "manifest-paths-exist", "PASS",
                "All repo paths resolve to existing directories",
                file="workspace.json",
            ))

    def run_all(self):
        if not self.check_file_present():
            return
        if not self.check_valid_json():
            return
        if not self.check_has_repos():
            return
        self.check_repo_fields()
        self.check_unique_names()
        self.check_paths_exist()


# ---------------------------------------------------------------------------
# Workspace AGENTS.md checks
# ---------------------------------------------------------------------------

WORKSPACE_REQUIRED_SECTIONS = [
    "Repos",
    "Cross-repo contracts",
    "Shared conventions",
    "Do not",
]

SPECULATIVE_PATTERNS = [
    r"we might later",
    r"we may (eventually|later|someday)",
    r"in the future we could",
    r"might want to add",
    r"could potentially",
    r"down the road",
    r"eventually we.?ll",
    r"TODO:?\s*(maybe|consider|think about)",
]


class WorkspaceAgentsMdChecker:

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
        """All four required sections must appear as headings."""
        missing = []
        for section in WORKSPACE_REQUIRED_SECTIONS:
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
                "All four required sections present",
                file="AGENTS.md",
            ))

    def check_line_count(self):
        """Workspace AGENTS.md must be under 100 lines."""
        lines = len(self.text.splitlines())
        if lines > 100:
            self.result.findings.append(Finding(
                "agents-md-line-count", "FAIL",
                f"AGENTS.md is {lines} lines; must be under 100",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-line-count", "PASS",
                f"AGENTS.md is {lines} lines (under 100)",
                file="AGENTS.md",
            ))

    def check_no_per_repo_sections(self):
        """Workspace AGENTS.md should not contain per-repo sections."""
        per_repo_patterns = [
            r"##\s+Tech stack",
            r"##\s+Project structure",
            r"##\s+Commands",
            r"##\s+Module guide",
            r"##\s+Architecture overview",
            r"##\s+Build protocol",
            r"##\s+Work protocol",
            r"##\s+Known issues",
        ]
        found = []
        for pat in per_repo_patterns:
            if re.search(pat, self.text, re.IGNORECASE):
                match = re.search(pat, self.text, re.IGNORECASE)
                found.append(match.group(0).strip())
        if found:
            self.result.findings.append(Finding(
                "agents-md-no-per-repo", "FAIL",
                f"Workspace AGENTS.md contains per-repo sections that "
                f"belong in individual repo files: {', '.join(found)}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-no-per-repo", "PASS",
                "No per-repo sections found in workspace AGENTS.md",
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

    def check_repos_section_content(self):
        """Repos section should list repo names with descriptions."""
        match = re.search(
            r"##\s+Repos\s*\n(.*?)(?=\n##\s|\Z)",
            self.text,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return
        content = match.group(1).strip()
        entries = re.findall(r"[-*]\s+\*\*(.+?)\*\*", content)
        if not entries:
            entries = re.findall(r"[-*]\s+(.+?)(?:\s+--|:)", content)
        if len(entries) < 2:
            self.result.findings.append(Finding(
                "agents-md-repos-content", "WARN",
                f"Repos section lists fewer than 2 entries "
                f"({len(entries)} found)",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-repos-content", "PASS",
                f"Repos section lists {len(entries)} entries",
                file="AGENTS.md",
            ))

    def check_manifest_alignment(self, manifest_names: list[str]):
        """Repos listed in AGENTS.md should match workspace.json."""
        if not manifest_names:
            return
        agents_text_lower = self.text.lower()
        missing = [n for n in manifest_names if n.lower() not in agents_text_lower]
        if missing:
            self.result.findings.append(Finding(
                "agents-md-manifest-alignment", "WARN",
                f"Repos in workspace.json not mentioned in AGENTS.md: "
                f"{', '.join(missing)}",
                file="AGENTS.md",
            ))
        else:
            self.result.findings.append(Finding(
                "agents-md-manifest-alignment", "PASS",
                "All workspace.json repos are mentioned in AGENTS.md",
                file="AGENTS.md",
            ))

    def run_all(self, manifest_names: list[str] | None = None):
        if not self.check_file_present():
            return
        self.check_required_sections()
        self.check_line_count()
        self.check_no_per_repo_sections()
        self.check_no_speculation()
        self.check_repos_section_content()
        if manifest_names:
            self.check_manifest_alignment(manifest_names)


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

def evaluate_project(workspace_dir: Path) -> EvalResult:
    result = EvalResult()

    def _read(name: str) -> str:
        p = workspace_dir / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    manifest_text = _read("workspace.json")
    manifest_checker = WorkspaceManifestChecker(manifest_text, workspace_dir, result)
    manifest_checker.run_all()

    manifest_names = []
    if manifest_checker.manifest and isinstance(manifest_checker.manifest, dict):
        for repo in manifest_checker.manifest.get("repos", []):
            if isinstance(repo, dict) and "name" in repo:
                manifest_names.append(repo["name"])

    agents_checker = WorkspaceAgentsMdChecker(_read("AGENTS.md"), result)
    agents_checker.run_all(manifest_names=manifest_names)

    ClaudeMdStubChecker(_read("CLAUDE.md"), result).run_all()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_report(result: EvalResult):
    counts = result.counts
    status = "PASSED" if result.passed else "FAILED"
    print(f"\n{'=' * 60}")
    print(f"  Workspace Output Quality: {status}")
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
        print("Usage: python eval_workspace_quality.py <workspace-dir> [--format json]")
        sys.exit(2)

    workspace_dir = Path(sys.argv[1])
    if not workspace_dir.is_dir():
        print(f"Not a directory: {workspace_dir}")
        sys.exit(2)

    use_json = "--format" in sys.argv and "json" in sys.argv

    result = evaluate_project(workspace_dir)

    if use_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
