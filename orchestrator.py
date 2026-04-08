"""
Orchestrator Module
===================
Collates results from all three checker modules and produces:
1.  Guidance on where to look as the reviewer (very short).
2.  A concise high-level package review comment (< 300 words).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from modules import ModuleResult


def _guidance(results: List[ModuleResult]) -> str:
    """Short reviewer guidance on where to focus attention."""
    focus_areas: list[str] = []
    for r in results:
        if not r.files_checked:
            continue
        if not r.overall_passed:
            fail_count = sum(1 for f in r.findings if f.status == "FAIL")
            focus_areas.append(f"{r.module_name} ({fail_count} failure(s))")

    if not focus_areas:
        return "All modules passed. Spot-check a sample of assets and properties for completeness."

    return "Focus review on: " + "; ".join(focus_areas) + "."


def _collated_summary(results: List[ModuleResult]) -> str:
    """Generate a concise package-wide summary (< 300 words)."""
    parts: list[str] = []
    overall_pass = all(r.overall_passed for r in results)
    checked = [r for r in results if r.files_checked]
    skipped = [r for r in results if not r.files_checked]

    ts = datetime.now().strftime("%d %B %Y %H:%M")
    parts.append(f"Package Review — {ts}")
    parts.append(f"Overall: {'PASS' if overall_pass else 'FAIL'}.")

    if skipped:
        names = ", ".join(r.module_name for r in skipped)
        parts.append(f"Not checked (no files): {names}.")

    for r in checked:
        total = len(r.findings)
        fails = sum(1 for f in r.findings if f.status == "FAIL")
        warns = sum(1 for f in r.findings if f.status == "WARNING")
        status = "PASS" if r.overall_passed else "FAIL"
        line = f"{r.module_name}: {status} — {total} checks"
        if fails:
            line += f", {fails} failure(s)"
        if warns:
            line += f", {warns} warning(s)"
        line += "."

        if not r.overall_passed:
            # Add top issue categories
            issue_types: dict[str, int] = {}
            for f in r.findings:
                if f.status == "FAIL":
                    issue_types[f.check_name] = issue_types.get(f.check_name, 0) + 1
            if issue_types:
                top = sorted(issue_types.items(), key=lambda x: -x[1])[:3]
                line += " Key issues: " + ", ".join(
                    f"{name} ({cnt})" for name, cnt in top
                ) + "."
        parts.append(line)

    summary = " ".join(parts)
    words = summary.split()
    if len(words) > 295:
        summary = " ".join(words[:295]) + "..."
    return summary


def _contractor_response(results: List[ModuleResult]) -> str:
    """Build a general contractor-facing issues summary.

    Keeps language broad so the onus is on the responder to address,
    while giving enough context (headings + examples) for clarity.
    """
    checked = [r for r in results if r.files_checked and not r.overall_passed]

    if not checked:
        return (
            "No issues were identified in this submission. "
            "The package appears to meet the requirements reviewed."
        )

    lines: list[str] = [
        "Following a review of the submitted package, a number of issues "
        "have been identified that require attention prior to acceptance.",
        "",
        "Issues including but not limited to:",
        "",
    ]

    for r in checked:
        # Group failures by check category
        categories: dict[str, list[str]] = {}
        for f in r.findings:
            if f.status == "FAIL":
                categories.setdefault(f.check_name, []).append(f.detail)

        if not categories:
            continue

        lines.append(f"  {r.module_name}")
        lines.append(f"  {'-' * len(r.module_name)}")

        for check_name, details in categories.items():
            # Deduplicate and pick a small sample as examples
            unique = list(dict.fromkeys(details))
            count = len(unique)

            # Synthesise a general statement
            lines.append(f"    • {check_name}")

            # Show up to 3 representative examples
            examples = unique[:3]
            for ex in examples:
                lines.append(f"        – e.g. {ex}")

            if count > len(examples):
                lines.append(
                    f"        – and {count - len(examples)} further instance(s) "
                    f"of a similar nature."
                )

        lines.append("")

    lines.append(
        "Please review and address the above. This list is indicative and "
        "not exhaustive — the full submission should be reviewed against the "
        "applicable requirements and resubmitted."
    )

    return "\n".join(lines)


def run(
    results: List[ModuleResult],
    output_folder: Path,
    log_callback=None,
    eir_version: str | None = None,
) -> str:
    """
    Collate module results into a high-level package review.

    Writes:
      - package_review_summary.txt   (collated high-level)
      - package_review_guidance.txt   (short reviewer guidance)

    Returns the collated summary text.
    """
    if log_callback:
        log_callback("")
        log_callback("=" * 50)
        log_callback("  ORCHESTRATOR — Collating Results")
        log_callback("=" * 50)

    guidance = _guidance(results)
    summary = _collated_summary(results)
    contractor_response = _contractor_response(results)

    # --- Write outputs ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    guidance_path = output_folder / "package_review_guidance.txt"
    guidance_path.write_text(guidance + "\n", encoding="utf-8")

    response_path = output_folder / "package_review_contractor_response.txt"
    response_path.write_text(contractor_response + "\n", encoding="utf-8")

    summary_path = output_folder / "package_review_summary.txt"
    eir_line = f"EIR Version: {eir_version}" if eir_version else "EIR Version: Built-in rules"
    full_output = "\n".join([
        "=" * 60,
        "  METRO PACKAGE REVIEW — HIGH-LEVEL SUMMARY",
        "=" * 60,
        "",
        eir_line,
        "",
        "REVIEWER GUIDANCE:",
        guidance,
        "",
        "PACKAGE COMMENTS:",
        summary,
        "",
        "=" * 60,
        "",
        "--- Per-Module Summaries ---",
        "",
    ])
    for r in results:
        full_output += f"[{r.module_name}]\n{r.summary}\n\n"

    summary_path.write_text(full_output, encoding="utf-8")

    if log_callback:
        log_callback("")
        log_callback("REVIEWER GUIDANCE:")
        log_callback(guidance)
        log_callback("")
        log_callback("PACKAGE COMMENTS:")
        log_callback(summary)
        log_callback("")
        log_callback("CONTRACTOR RESPONSE SUMMARY:")
        log_callback(contractor_response)
        log_callback("")
        log_callback(f"Output written to: {output_folder}")

    return summary
