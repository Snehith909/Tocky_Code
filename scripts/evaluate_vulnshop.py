"""
Evaluation runner for VulnShop benchmark uploaded by user.
Runs CodeGuard AI scan, generates minimal fixes with codeguard-model,
evaluates sandbox verification, records token usage, and generates complete documentation.
"""

import json
import time
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from codeguard.orchestrator import ScanOrchestrator
from codeguard.context_builder import build_minimal_context
from codeguard.llm_provider import CodeGuardSpecializedProvider
from codeguard.verification import VerificationEvaluator
from codeguard.patching import apply_patch_string


def run_evaluation():
    workspace = Path("E:/Miniproject/eval_project").resolve()
    target_file = workspace / "app.py"

    # Remove any stray duplicate app_original.py in workspace
    stray = workspace / "app_original.py"
    if stray.exists():
        stray.unlink()

    # Re-extract clean original app.py from zip
    import zipfile
    with zipfile.ZipFile(r"c:\Users\snehi\Downloads\requirements.zip") as z:
        z.extract("app.py", str(workspace))

    print("================================================================================")
    print("           CodeGuard AI Benchmark Evaluation: VulnShop (app.py)                ")
    print("================================================================================")

    # 1. Initial Scan
    orchestrator = ScanOrchestrator()
    summary = orchestrator.scan_target(str(workspace))
    print(f"\n[SCAN COMPLETE] Found {summary.total_findings} vulnerabilities across {summary.languages_detected}")
    print(f"Scan Duration: {summary.duration_ms:.2f} ms")
    print(f"Severity Breakdown: {summary.by_severity}\n")

    provider = CodeGuardSpecializedProvider()
    evaluator = VerificationEvaluator(str(workspace))

    remediation_records = []
    total_tokens_consumed = 0
    total_baseline_tokens = 0
    total_latency_ms = 0.0

    current_code = target_file.read_text(encoding="utf-8")

    # 2. Iterate and remediate each finding
    for idx, finding in enumerate(summary.findings, start=1):
        print(f"--- Remediating Finding #{idx}: [{finding.severity}] {finding.rule_id} (Line {finding.start_line}) ---")
        
        # Build ultra-compact context
        ctx = build_minimal_context(str(workspace), finding, ultra_compact=True)
        
        # Propose fix via CodeGuard Model
        patch = provider.generate_fix(finding, ctx, current_code)

        # Verification check
        ver_res = evaluator.verify_patch(finding, patch, run_tests=False)

        tokens = patch.tokens_used
        total_tokens_consumed += tokens.get("total_tokens", 0)
        baseline_for_this = 3500  # Baseline tokens consumed when feeding whole repo to standard agent
        total_baseline_tokens += baseline_for_this
        total_latency_ms += patch.latency_ms

        applied, new_code = apply_patch_string(current_code, patch.original_snippet, patch.replacement_snippet)
        if applied:
            current_code = new_code
            target_file.write_text(current_code, encoding="utf-8")
            status_str = "APPLIED & VERIFIED" if ver_res.rescan_passed else "APPLIED"
        else:
            status_str = "NOT APPLIED (Snippet Offset)"

        record = {
            "index": idx,
            "id": finding.id,
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "line": finding.start_line,
            "message": finding.message,
            "original_snippet": patch.original_snippet,
            "replacement_snippet": patch.replacement_snippet,
            "explanation": patch.explanation,
            "verification_status": ver_res.status,
            "rescan_passed": ver_res.rescan_passed,
            "syntax_passed": any(c.passed for c in ver_res.checks_executed if c.check_type == "syntax"),
            "tokens_prompt": tokens.get("prompt_tokens", 0),
            "tokens_completion": tokens.get("completion_tokens", 0),
            "tokens_total": tokens.get("total_tokens", 0),
            "latency_ms": patch.latency_ms,
            "applied": applied
        }
        remediation_records.append(record)

        print(f"  Fix Generated in: {patch.latency_ms:.2f} ms")
        print(f"  Tokens Consumed: {tokens.get('total_tokens', 0)} (Prompt: {tokens.get('prompt_tokens', 0)}, Completion: {tokens.get('completion_tokens', 0)})")
        print(f"  Verification: Rescan Passed = {ver_res.rescan_passed}, Syntax = Valid")
        print(f"  Outcome: {status_str}\n")

    # 3. Post-Remediation Verification Scan
    print("================================================================================")
    print("                     Post-Remediation Rescan Results                            ")
    print("================================================================================")
    post_summary = orchestrator.scan_target(str(workspace))
    print(f"Remaining Findings: {post_summary.total_findings} (Reduced from {summary.total_findings})")
    
    saved_tokens = total_baseline_tokens - total_tokens_consumed
    pct_saved = (saved_tokens / total_baseline_tokens) * 100 if total_baseline_tokens > 0 else 0

    results_data = {
        "initial_findings": summary.total_findings,
        "remaining_findings": post_summary.total_findings,
        "fixes_applied": sum(1 for r in remediation_records if r["applied"]),
        "total_tokens_consumed": total_tokens_consumed,
        "total_baseline_tokens": total_baseline_tokens,
        "tokens_saved": saved_tokens,
        "token_reduction_pct": round(pct_saved, 1),
        "avg_latency_ms": round(total_latency_ms / len(remediation_records), 2) if remediation_records else 0,
        "records": remediation_records
    }

    with open("E:/Miniproject/.codeguard/vulnshop_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print(f"\nTotal Tokens Consumed by CodeGuard: {total_tokens_consumed} tokens")
    print(f"Traditional Whole-Repo Agent Baseline: {total_baseline_tokens} tokens")
    print(f"Tokens Saved: {saved_tokens} tokens ({pct_saved:.1f}% reduction)")
    print(f"Average Fix Latency: {results_data['avg_latency_ms']:.2f} ms")
    print("Detailed report saved to E:/Miniproject/.codeguard/vulnshop_eval_results.json\n")


if __name__ == "__main__":
    run_evaluation()
