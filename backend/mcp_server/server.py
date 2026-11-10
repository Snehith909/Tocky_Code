"""
Tocky Code MCP Server
Model Context Protocol server that exposes vulnerability findings to GitHub Copilot.
Allows Copilot to access security scan results and code context for automated fixing.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from codeguard.orchestrator import ScanOrchestrator
from codeguard.models import Finding
from codeguard.llm_provider import get_llm_provider
from codeguard.context_builder import build_minimal_context
from codeguard.verification import VerificationEvaluator
from mcp_server.storage_extensions import MCPStorageManager


class TockyMCPServer:
    """MCP Server for Tocky Code vulnerability scanner integration with GitHub Copilot."""
    
    def __init__(self, workspace_path: str = None):
        self.workspace_path = workspace_path or os.getcwd()
        self.storage = MCPStorageManager(os.path.join(self.workspace_path, ".codeguard", "history.db"))
        self.orchestrator = ScanOrchestrator(self.storage)
        self.server = Server("tocky-code")
        self._register_tools()
        
    def _register_tools(self):
        """Register all MCP tools that Copilot can call."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools for Copilot."""
            return [
                Tool(
                    name="get_vulnerabilities",
                    description="Get all security vulnerabilities detected in the workspace. Returns vulnerability ID, type, severity, file, line number, and description.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
                                "description": "Filter by severity level (optional)"
                            },
                            "language": {
                                "type": "string",
                                "description": "Filter by programming language (optional)"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_file_context",
                    description="Get the source code context around a vulnerability, including surrounding lines for better understanding.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "description": "Path to the file containing the vulnerability"
                            },
                            "line": {
                                "type": "integer",
                                "description": "Line number of the vulnerability"
                            },
                            "context_lines": {
                                "type": "integer",
                                "description": "Number of lines to include before and after (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["file", "line"]
                    }
                ),
                Tool(
                    name="get_fix_instructions",
                    description="Get detailed fix instructions for a specific vulnerability, including root cause, security impact, and recommended remediation steps.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vulnerability_id": {
                                "type": "string",
                                "description": "The ID of the vulnerability to get fix instructions for"
                            }
                        },
                        "required": ["vulnerability_id"]
                    }
                ),
                Tool(
                    name="apply_security_patch",
                    description="Apply a security patch to fix a vulnerability. The patch will be validated before application.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "description": "Path to the file to patch"
                            },
                            "original_code": {
                                "type": "string",
                                "description": "The original vulnerable code snippet to replace"
                            },
                            "fixed_code": {
                                "type": "string",
                                "description": "The secure replacement code"
                            },
                            "vulnerability_id": {
                                "type": "string",
                                "description": "ID of the vulnerability being fixed"
                            }
                        },
                        "required": ["file", "original_code", "fixed_code", "vulnerability_id"]
                    }
                ),
                Tool(
                    name="verify_security_fix",
                    description="Verify that a security fix successfully resolved the vulnerability by re-scanning and running tests.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "vulnerability_id": {
                                "type": "string",
                                "description": "ID of the vulnerability to verify"
                            },
                            "run_tests": {
                                "type": "boolean",
                                "description": "Whether to run tests as part of verification (default: true)",
                                "default": True
                            }
                        },
                        "required": ["vulnerability_id"]
                    }
                ),
                Tool(
                    name="scan_workspace",
                    description="Trigger a new security scan of the workspace to detect vulnerabilities.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target_path": {
                                "type": "string",
                                "description": "Specific path to scan (optional, defaults to workspace root)"
                            }
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls from Copilot."""
            
            if name == "get_vulnerabilities":
                return await self._get_vulnerabilities(arguments)
            elif name == "get_file_context":
                return await self._get_file_context(arguments)
            elif name == "get_fix_instructions":
                return await self._get_fix_instructions(arguments)
            elif name == "apply_security_patch":
                return await self._apply_security_patch(arguments)
            elif name == "verify_security_fix":
                return await self._verify_security_fix(arguments)
            elif name == "scan_workspace":
                return await self._scan_workspace(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]
    
    async def _get_vulnerabilities(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get all vulnerabilities, optionally filtered."""
        try:
            # Get recent findings from storage
            findings = self.storage.get_recent_findings(limit=100)
            
            # Apply filters
            severity_filter = args.get("severity")
            language_filter = args.get("language")
            
            filtered = findings
            if severity_filter:
                filtered = [f for f in filtered if f["severity"] == severity_filter]
            if language_filter:
                filtered = [f for f in filtered if f["language"].lower() == language_filter.lower()]
            
            result = {
                "total_vulnerabilities": len(filtered),
                "vulnerabilities": [
                    {
                        "id": f["id"],
                        "type": f["rule_id"],
                        "severity": f["severity"],
                        "file": f["file"],
                        "line": f["start_line"],
                        "message": f["message"],
                        "cwe": f.get("cwe", "N/A"),
                        "tool": f["tool"],
                        "evidence": f["evidence"][:200]  # Truncate for readability
                    }
                    for f in filtered
                ]
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting vulnerabilities: {str(e)}"
            )]
    
    async def _get_file_context(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get source code context around a vulnerability."""
        try:
            file_path = Path(self.workspace_path) / args["file"]
            line_num = args["line"]
            context_lines = args.get("context_lines", 10)
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"File not found: {args['file']}"
                )]
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            start_line = max(0, line_num - context_lines - 1)
            end_line = min(len(lines), line_num + context_lines)
            
            context = {
                "file": args["file"],
                "target_line": line_num,
                "line_range": f"{start_line + 1}-{end_line}",
                "code": "".join(lines[start_line:end_line]),
                "vulnerable_line": lines[line_num - 1] if 0 <= line_num - 1 < len(lines) else "N/A"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(context, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting file context: {str(e)}"
            )]
    
    async def _get_fix_instructions(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get detailed instructions for fixing a vulnerability."""
        try:
            vuln_id = args["vulnerability_id"]
            finding_data = self.storage.get_finding_by_id(vuln_id)
            
            if not finding_data:
                return [TextContent(
                    type="text",
                    text=f"Vulnerability not found: {vuln_id}"
                )]
            
            # Build comprehensive fix instructions
            instructions = {
                "vulnerability_id": vuln_id,
                "type": finding_data["rule_id"],
                "severity": finding_data["severity"],
                "description": finding_data["message"],
                "cwe": finding_data.get("cwe", "N/A"),
                "file": finding_data["file"],
                "line": finding_data["start_line"],
                "vulnerable_code": finding_data["evidence"],
                "root_cause": self._get_root_cause(finding_data["rule_id"]),
                "security_impact": self._get_security_impact(finding_data["rule_id"]),
                "remediation": self._get_remediation_steps(finding_data["rule_id"]),
                "references": self._get_references(finding_data.get("cwe"))
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(instructions, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error getting fix instructions: {str(e)}"
            )]
    
    async def _apply_security_patch(self, args: Dict[str, Any]) -> List[TextContent]:
        """Apply a security patch to a file."""
        try:
            file_path = Path(self.workspace_path) / args["file"]
            original_code = args["original_code"]
            fixed_code = args["fixed_code"]
            vuln_id = args["vulnerability_id"]
            
            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"File not found: {args['file']}"
                )]
            
            # Read current content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate patch
            if original_code not in content:
                return [TextContent(
                    type="text",
                    text=f"ERROR: Original code not found in file. Patch cannot be applied safely."
                )]
            
            # Create backup
            backup_path = file_path.with_suffix(file_path.suffix + '.tocky-backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Apply patch
            patched_content = content.replace(original_code, fixed_code, 1)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(patched_content)
            
            result = {
                "status": "success",
                "message": "Patch applied successfully",
                "file": args["file"],
                "vulnerability_id": vuln_id,
                "backup_created": str(backup_path)
            }
            
            # Record in storage
            self.storage.record_patch_application(vuln_id, args["file"], "applied")
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error applying patch: {str(e)}"
            )]
    
    async def _verify_security_fix(self, args: Dict[str, Any]) -> List[TextContent]:
        """Verify that a vulnerability has been fixed."""
        try:
            vuln_id = args["vulnerability_id"]
            run_tests = args.get("run_tests", True)
            
            finding_data = self.storage.get_finding_by_id(vuln_id)
            if not finding_data:
                return [TextContent(
                    type="text",
                    text=f"Vulnerability not found: {vuln_id}"
                )]
            
            # Re-scan the affected file
            file_path = str(Path(self.workspace_path) / finding_data["file"])
            scan_result = self.orchestrator.scan_target(file_path)
            
            # Check if the specific vulnerability still exists
            still_vulnerable = any(
                f.rule_id == finding_data["rule_id"] and
                f.file == finding_data["file"] and
                f.start_line == finding_data["start_line"]
                for f in scan_result.findings
            )
            
            verification_result = {
                "vulnerability_id": vuln_id,
                "status": "FAILED" if still_vulnerable else "VERIFIED",
                "rescan_passed": not still_vulnerable,
                "message": "Vulnerability still present" if still_vulnerable else "Vulnerability successfully fixed",
                "new_vulnerabilities": len(scan_result.findings),
                "tests_run": run_tests,
                "tests_passed": None  # Would integrate with test runner
            }
            
            # Record verification
            self.storage.record_verification_result(vuln_id, verification_result)
            
            return [TextContent(
                type="text",
                text=json.dumps(verification_result, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error verifying fix: {str(e)}"
            )]
    
    async def _scan_workspace(self, args: Dict[str, Any]) -> List[TextContent]:
        """Trigger a new security scan."""
        try:
            target = args.get("target_path", self.workspace_path)
            scan_result = self.orchestrator.scan_target(target)
            
            result = {
                "scan_completed": True,
                "total_findings": scan_result.total_findings,
                "by_severity": scan_result.by_severity,
                "scanners_run": scan_result.scanners_run,
                "languages_detected": scan_result.languages_detected,
                "duration_ms": scan_result.duration_ms
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error scanning workspace: {str(e)}"
            )]
    
    def _get_root_cause(self, rule_id: str) -> str:
        """Get root cause explanation for a vulnerability type."""
        causes = {
            "sql_injection": "Unsafe concatenation of user input into SQL queries allows attackers to inject malicious SQL commands.",
            "command_injection": "User input is passed to system shell commands without proper sanitization.",
            "xss": "User-controlled data is rendered in HTML without proper encoding.",
            "path_traversal": "File paths are constructed using unsanitized user input.",
            "hardcoded_secret": "Sensitive credentials are stored directly in source code.",
        }
        for key in causes:
            if key in rule_id.lower():
                return causes[key]
        return "Security vulnerability detected by static analysis."
    
    def _get_security_impact(self, rule_id: str) -> str:
        """Get security impact description."""
        impacts = {
            "sql_injection": "Attackers can read, modify, or delete database contents, potentially compromising all application data.",
            "command_injection": "Attackers can execute arbitrary system commands, leading to full system compromise.",
            "xss": "Attackers can steal user sessions, deface websites, or redirect users to malicious sites.",
            "path_traversal": "Attackers can access sensitive files outside the intended directory.",
            "hardcoded_secret": "Exposed credentials can be used to gain unauthorized access to systems and data.",
        }
        for key in impacts:
            if key in rule_id.lower():
                return impacts[key]
        return "Security vulnerability may lead to unauthorized access or data compromise."
    
    def _get_remediation_steps(self, rule_id: str) -> str:
        """Get recommended remediation steps."""
        remediations = {
            "sql_injection": "Use parameterized queries or prepared statements. Never concatenate user input into SQL strings.",
            "command_injection": "Use safe APIs that don't invoke system shells. Pass arguments as arrays rather than strings. Validate and sanitize all input.",
            "xss": "Use proper output encoding (HTML entity encoding) for all user-controlled data rendered in HTML.",
            "path_traversal": "Validate file paths against a whitelist. Use Path.resolve() and check that resolved path is within allowed directory.",
            "hardcoded_secret": "Move secrets to environment variables or secure secret management systems.",
        }
        for key in remediations:
            if key in rule_id.lower():
                return remediations[key]
        return "Follow security best practices for this vulnerability type."
    
    def _get_references(self, cwe: str) -> List[str]:
        """Get reference links for the vulnerability."""
        refs = [
            f"https://cwe.mitre.org/data/definitions/{cwe}.html" if cwe else None,
            "https://owasp.org/www-project-top-ten/"
        ]
        return [r for r in refs if r]
    
    async def run(self):
        """Start the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point."""
    workspace = os.getenv("TOCKY_WORKSPACE", os.getcwd())
    server = TockyMCPServer(workspace)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
