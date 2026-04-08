"""
Metro Package Review 1.0 – Shared types for checker modules.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def get_app_root() -> Path:
    """Return the application root, handling PyInstaller frozen bundles."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).parent.parent.resolve()


APP_ROOT = get_app_root()
REFERENCE_DOCS = APP_ROOT / "reference_docs"


@dataclass
class CheckFinding:
    """One granular finding from a checker."""
    file_name: str
    check_name: str
    status: str          # PASS | FAIL | WARNING
    detail: str


@dataclass
class ModuleResult:
    """Aggregated result for one checker module."""
    module_name: str
    files_checked: List[str] = field(default_factory=list)
    overall_passed: bool = True
    findings: List[CheckFinding] = field(default_factory=list)
    summary: str = ""
    granular_text: str = ""

    def add_finding(self, file_name: str, check_name: str, status: str, detail: str):
        self.findings.append(CheckFinding(file_name, check_name, status, detail))
        if status == "FAIL":
            self.overall_passed = False

    def build_granular_text(self) -> str:
        lines = [f"{'='*60}", f"  {self.module_name} — Granular Findings", f"{'='*60}", ""]
        if not self.findings:
            lines.append("No files found to check.")
            self.granular_text = "\n".join(lines)
            return self.granular_text

        current_file = None
        for f in self.findings:
            if f.file_name != current_file:
                current_file = f.file_name
                lines.append(f"--- {current_file} ---")
            lines.append(f"  [{f.status}] {f.check_name}: {f.detail}")
        lines.append("")
        self.granular_text = "\n".join(lines)
        return self.granular_text

    def build_summary(self) -> str:
        if not self.files_checked:
            self.summary = f"{self.module_name}: No files found in the input folder."
            return self.summary

        total = len(self.findings)
        passes = sum(1 for f in self.findings if f.status == "PASS")
        fails = sum(1 for f in self.findings if f.status == "FAIL")
        warns = sum(1 for f in self.findings if f.status == "WARNING")
        file_count = len(self.files_checked)

        status = "PASS" if self.overall_passed else "FAIL"
        parts = [
            f"{self.module_name} Review ({file_count} file(s)): {status}.",
        ]

        if self.overall_passed:
            parts.append(
                f"All {total} checks passed. The submission meets requirements."
            )
        else:
            parts.append(f"{fails} check(s) failed out of {total} total.")
            if warns:
                parts.append(f"{warns} warning(s) noted.")

            # Collect unique fail details (deduplicated)
            fail_reasons = []
            seen = set()
            for f in self.findings:
                if f.status == "FAIL" and f.detail not in seen:
                    seen.add(f.detail)
                    fail_reasons.append(f.detail)
            if fail_reasons:
                parts.append("Key issues: " + "; ".join(fail_reasons[:5]))
                if len(fail_reasons) > 5:
                    parts.append(f"...and {len(fail_reasons) - 5} additional issue(s).")

        self.summary = " ".join(parts)
        # Truncate to ~300 words
        words = self.summary.split()
        if len(words) > 295:
            self.summary = " ".join(words[:295]) + "..."
        return self.summary
