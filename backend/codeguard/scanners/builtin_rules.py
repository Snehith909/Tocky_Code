"""
Built-in security scanner rule engine.
Provides deterministic, zero-dependency static analysis for Python, JavaScript, TypeScript,
and secrets. Always available even when external CLI binaries are not installed.
"""

import ast
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


# Secret detection patterns
SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|secret|password|passwd|auth[_-]?token|access[_-]?token|private[_-]?key)\s*[:=]\s*["\']([a-zA-Z0-9_\-\.\/+=]{12,})["\']', "builtin.secret.hardcoded_credential", "CWE-798", Severity.HIGH),
    (r'(?i)AIza[0-9A-Za-z-_]{35}', "builtin.secret.google_api_key", "CWE-798", Severity.CRITICAL),
    (r'(?i)gh[pous]_[0-9a-zA-Z]{36}', "builtin.secret.github_token", "CWE-798", Severity.CRITICAL),
    (r'(?i)sk-[a-zA-Z0-9]{32,}', "builtin.secret.openai_api_key", "CWE-798", Severity.CRITICAL),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "builtin.secret.private_key", "CWE-312", Severity.CRITICAL),
]

# Python security patterns
PYTHON_PATTERNS = [
    (r'(\.execute\s*\(\s*["\'].*?%s.*?\))', "builtin.py.sql_injection_percent", "SQL query constructed with string formatting; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'(\.execute\s*\(\s*f["\'].*?\{.*?\}[\'"]\s*\))', "builtin.py.sql_injection_fstring", "SQL query constructed with f-string; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'(\.execute\s*\(\s*["\'].*?\+.*?\))', "builtin.py.sql_injection_concat", "SQL query constructed with string concatenation; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'((?:query|sql|stmt)\s*=\s*["\'].*?%s.*?["\']\s*%)', "builtin.py.sql_injection_percent", "SQL query constructed with string formatting; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'((?:query|sql|stmt)\s*=\s*f["\'].*?\{.*?\}[\'"])', "builtin.py.sql_injection_fstring", "SQL query constructed with f-string; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'((?:query|sql|stmt)\s*=\s*["\'].*?["\']\s*\+)', "builtin.py.sql_injection_concat", "SQL query constructed with string concatenation; risk of SQL injection", "CWE-89", Severity.HIGH),
    (r'(eval\s*\([^)]+\))', "builtin.py.unsafe_eval", "Use of eval() detected; arbitrary code execution vulnerability", "CWE-95", Severity.CRITICAL),
    (r'(exec\s*\([^)]+\))', "builtin.py.unsafe_exec", "Use of exec() detected; arbitrary code execution vulnerability", "CWE-95", Severity.CRITICAL),
    (r'(subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True[^)]*\))', "builtin.py.subprocess_shell_true", "Subprocess invoked with shell=True; command injection risk", "CWE-78", Severity.HIGH),
    (r'(pickle\.loads?\s*\([^)]+\))', "builtin.py.unsafe_deserialization", "Use of pickle loads/load; arbitrary object deserialization vulnerability", "CWE-502", Severity.HIGH),
    (r'(yaml\.load\s*\([^)]*(?!Loader=SafeLoader)[^)]*\))', "builtin.py.unsafe_yaml_load", "Unsafe yaml.load() without SafeLoader; arbitrary code execution risk", "CWE-20", Severity.HIGH),
]

# JavaScript/TypeScript security patterns
JS_TS_PATTERNS = [
    (r'(\.query\s*\(\s*[`\'"].*?\$\{.*?\}[\'"`]\s*\))', "builtin.js.sql_injection", "SQL query built with template literal interpolation", "CWE-89", Severity.HIGH),
    (r'(\.query\s*\(\s*["\'].*?\+.*?\))', "builtin.js.sql_injection_concat", "SQL query built with string concatenation", "CWE-89", Severity.HIGH),
    (r'(exec\s*\(\s*[`\'"].*?\$\{.*?\}[\'"`]\s*[\),])', "builtin.js.command_injection", "child_process.exec invoked with template literal interpolation; command injection risk", "CWE-78", Severity.CRITICAL),
    (r'(exec\s*\(\s*["\'].*?\+\s*[a-zA-Z0-9_]+)', "builtin.js.command_injection_concat", "child_process.exec with string concatenation; command injection risk", "CWE-78", Severity.CRITICAL),
    (r'(eval\s*\([^)]+\))', "builtin.js.unsafe_eval", "eval() allows arbitrary code execution", "CWE-95", Severity.CRITICAL),
    (r'(__proto__\s*=)', "builtin.js.prototype_pollution", "Direct assignment to __proto__ may cause prototype pollution", "CWE-1321", Severity.HIGH),
    (r'(document\.write\s*\([^)]+\))', "builtin.js.xss_document_write", "document.write can introduce DOM Cross-Site Scripting (XSS)", "CWE-79", Severity.MEDIUM),
    (r'(innerHTML\s*=\s*[^;]+)', "builtin.js.xss_inner_html", "Direct assignment to innerHTML can lead to Cross-Site Scripting (XSS)", "CWE-79", Severity.MEDIUM),
]


class BuiltinRulesScanner(BaseScannerAdapter):
    name = "builtin"
    supported_languages = ["python", "javascript", "typescript", "generic"]

    def is_available(self) -> bool:
        return True

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        target = Path(target_path)
        files_to_scan: List[Path] = []

        if target.is_file():
            files_to_scan.append(target)
        elif target.is_dir():
            # Scan recursively, skip node_modules, .git, venv
            skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "out", "dist"}
            for p in target.rglob("*"):
                if p.is_file():
                    # check if any parent in skip_dirs
                    if any(part in skip_dirs for part in p.parts):
                        continue
                    ext = p.suffix.lower()
                    if ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".env", ".yaml", ".yml", ".sql"]:
                        files_to_scan.append(p)

        findings: List[Finding] = []
        counter = 1

        for f in files_to_scan:
            try:
                rel_path = str(f.relative_to(target.parent if target.is_file() else target))
            except Exception:
                rel_path = str(f)

            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = content.splitlines()
            ext = f.suffix.lower()

            # 1. Scan for Secrets across all files
            for pattern, rule_id, cwe, sev in SECRET_PATTERNS:
                for line_idx, line in enumerate(lines, start=1):
                    match = re.search(pattern, line)
                    if match:
                        matched_str = match.group(0)
                        redacted = re.sub(r'["\']([a-zA-Z0-9_\-\.\/+=]{6,})["\']', '"[REDACTED_SECRET]"', matched_str)
                        findings.append(Finding(
                            id=f"CG-SEC-{counter:04d}",
                            tool=self.name,
                            rule_id=rule_id,
                            language="generic",
                            file=rel_path,
                            start_line=line_idx,
                            end_line=line_idx,
                            severity=sev.value,
                            message=f"Hardcoded sensitive secret or API key detected in {rel_path}",
                            evidence=redacted.strip(),
                            status=FindingStatus.OPEN.value,
                            cwe=cwe,
                            confidence="HIGH"
                        ))
                        counter += 1

            # 2. Python specific scan
            if ext == ".py":
                # AST analysis for python
                try:
                    tree = ast.parse(content, filename=str(f))
                    for node in ast.walk(tree):
                        # Detect eval/exec via AST
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            if node.func.id in ("eval", "exec"):
                                start_l = getattr(node, "lineno", 1)
                                end_l = getattr(node, "end_lineno", start_l)
                                line_text = lines[start_l - 1] if 0 <= start_l - 1 < len(lines) else f"{node.func.id}(...)"
                                findings.append(Finding(
                                    id=f"CG-PY-{counter:04d}",
                                    tool=self.name,
                                    rule_id=f"builtin.py.unsafe_{node.func.id}",
                                    language="python",
                                    file=rel_path,
                                    start_line=start_l,
                                    end_line=end_l,
                                    severity=Severity.CRITICAL.value,
                                    message=f"Direct invocation of {node.func.id}() enables arbitrary code execution",
                                    evidence=line_text.strip(),
                                    status=FindingStatus.OPEN.value,
                                    cwe="CWE-95",
                                    confidence="HIGH"
                                ))
                                counter += 1
                except Exception:
                    # Fallback to regex if AST fails on syntax error
                    pass

                # Regex patterns for Python
                for pattern, rule_id, msg, cwe, sev in PYTHON_PATTERNS:
                    if "eval" in rule_id or "exec" in rule_id:
                        # already checked or covered
                        continue
                    for line_idx, line in enumerate(lines, start=1):
                        match = re.search(pattern, line)
                        if match:
                            findings.append(Finding(
                                id=f"CG-PY-{counter:04d}",
                                tool=self.name,
                                rule_id=rule_id,
                                language="python",
                                file=rel_path,
                                start_line=line_idx,
                                end_line=line_idx,
                                severity=sev.value,
                                message=msg,
                                evidence=line.strip(),
                                status=FindingStatus.OPEN.value,
                                cwe=cwe,
                                confidence="HIGH"
                            ))
                            counter += 1

            # 3. JavaScript / TypeScript scan
            if ext in [".js", ".jsx", ".ts", ".tsx"]:
                lang = "typescript" if "ts" in ext else "javascript"
                for pattern, rule_id, msg, cwe, sev in JS_TS_PATTERNS:
                    for line_idx, line in enumerate(lines, start=1):
                        match = re.search(pattern, line)
                        if match:
                            findings.append(Finding(
                                id=f"CG-JS-{counter:04d}",
                                tool=self.name,
                                rule_id=rule_id,
                                language=lang,
                                file=rel_path,
                                start_line=line_idx,
                                end_line=line_idx,
                                severity=sev.value,
                                message=msg,
                                evidence=line.strip(),
                                status=FindingStatus.OPEN.value,
                                cwe=cwe,
                                confidence="HIGH"
                            ))
                            counter += 1

        return findings

    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        return []
