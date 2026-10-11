"""
Command-line interface for CodeGuard AI.
Used directly from the terminal or invoked by the VS Code extension subprocess bridge.
"""

import argparse
import json
import sys
from pathlib import Path

from codeguard.orchestrator import ScanOrchestrator
from codeguard.models import Finding, PatchProposal
from codeguard.context_builder import build_minimal_context
from codeguard.llm_provider import get_llm_provider
from codeguard.verification import VerificationEvaluator
from codeguard.storage import StorageManager


def cmd_scan(args):
    orchestrator = ScanOrchestrator()
    summary = orchestrator.scan_target(args.target)

    if args.format == "json":
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(f"\n--- CodeGuard AI Scan Results ---")
        print(f"Target: {summary.workspace_path}")
        print(f"Languages: {', '.join(summary.languages_detected)}")
        print(f"Scanners Run: {', '.join(summary.scanners_run)}")
        if summary.scanners_unavailable:
            print(f"Scanners Unavailable: {', '.join(summary.scanners_unavailable)}")
        print(f"Duration: {summary.duration_ms} ms")
        print(f"Total Findings: {summary.total_findings}\n")

        for f in summary.findings:
            print(f"[{f.severity}] {f.file}:{f.start_line} ({f.tool} / {f.rule_id})")
            print(f"  Message: {f.message}")
            print(f"  Evidence: {f.evidence[:80]}...\n")


def cmd_propose_fix(args):
    workspace = Path(args.workspace).resolve()

    if args.finding_json:
        data = json.loads(args.finding_json)
        finding = Finding.from_dict(data)
    else:
        # Load from file if JSON path provided
        with open(args.finding_file, "r", encoding="utf-8") as fp:
            finding = Finding.from_dict(json.load(fp))

    context_data = build_minimal_context(str(workspace), finding)
    target_abs = workspace / finding.file
    content = target_abs.read_text(encoding="utf-8", errors="replace") if target_abs.exists() else finding.evidence

    provider = get_llm_provider(args.provider)
    patch = provider.generate_fix(finding, context_data, content)

    # Record patch in storage
    storage = StorageManager(str(workspace / ".codeguard" / "history.db"))
    storage.record_patch(patch)

    print(json.dumps(patch.to_dict(), indent=2))


def cmd_verify(args):
    workspace = Path(args.workspace).resolve()

    if args.finding_json:
        finding = Finding.from_dict(json.loads(args.finding_json))
    else:
        with open(args.finding_file, "r", encoding="utf-8") as fp:
            finding = Finding.from_dict(json.load(fp))

    if args.patch_json:
        patch = PatchProposal.from_dict(json.loads(args.patch_json))
    else:
        with open(args.patch_file, "r", encoding="utf-8") as fp:
            patch = PatchProposal.from_dict(json.load(fp))

    evaluator = VerificationEvaluator(str(workspace))
    res = evaluator.verify_patch(finding, patch, run_tests=not args.no_tests)

    # Record verification in storage
    storage = StorageManager(str(workspace / ".codeguard" / "history.db"))
    storage.record_verification(res)

    print(json.dumps(res.to_dict(), indent=2))


def cmd_metrics(args):
    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd()
    storage = StorageManager(str(workspace / ".codeguard" / "history.db"))
    metrics = storage.get_metrics()
    print(json.dumps(metrics, indent=2))


def cmd_explain(args):
    data = json.loads(args.finding_json)
    f = Finding.from_dict(data)

    explanation = {
        "finding_id": f.id,
        "rule_id": f.rule_id,
        "tool": f.tool,
        "severity": f.severity,
        "file": f.file,
        "line": f.start_line,
        "cwe": f.cwe or "N/A",
        "description": f.message,
        "remediation_guidance": f"Ensure all input passed to {f.rule_id} is properly validated or parameterized."
    }
    print(json.dumps(explanation, indent=2))


def main():
    parser = argparse.ArgumentParser(description="CodeGuard AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan target file or workspace")
    p_scan.add_argument("--target", required=True, help="Path to file or workspace directory")
    p_scan.add_argument("--format", choices=["json", "text"], default="json")
    p_scan.set_defaults(func=cmd_scan)

    # propose-fix
    p_fix = subparsers.add_parser("propose-fix", help="Propose minimal fix for a finding")
    p_fix.add_argument("--workspace", required=True, help="Workspace root directory")
    p_fix.add_argument("--finding-json", help="Finding serialized JSON")
    p_fix.add_argument("--finding-file", help="Path to JSON file containing finding")
    p_fix.add_argument("--provider", default="mock", help="LLM provider (mock, gemini)")
    p_fix.set_defaults(func=cmd_fix if "cmd_fix" in globals() else cmd_propose_fix)

    # verify
    p_ver = subparsers.add_parser("verify", help="Verify patch proposal in isolated sandbox")
    p_ver.add_argument("--workspace", required=True, help="Workspace root directory")
    p_ver.add_argument("--finding-json", help="Finding serialized JSON")
    p_ver.add_argument("--finding-file", help="Path to finding JSON file")
    p_ver.add_argument("--patch-json", help="Patch proposal serialized JSON")
    p_ver.add_argument("--patch-file", help="Path to patch JSON file")
    p_ver.add_argument("--no-tests", action="store_true", help="Skip running test suite")
    p_ver.set_defaults(func=cmd_verify)

    # metrics
    p_met = subparsers.add_parser("metrics", help="Show token and verification metrics")
    p_met.add_argument("--workspace", default=".", help="Workspace root directory")
    p_met.set_defaults(func=cmd_metrics)

    # explain
    p_exp = subparsers.add_parser("explain", help="Explain vulnerability finding")
    p_exp.add_argument("--finding-json", required=True, help="Finding serialized JSON")
    p_exp.set_defaults(func=cmd_explain)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
