# Tocky Code MCP Integration

## Overview

This directory contains the **Model Context Protocol (MCP)** server that enables GitHub Copilot to directly access Tocky Code's vulnerability findings and automatically generate security fixes.

## Architecture

```
GitHub Copilot
     ↓ (queries via MCP)
Tocky MCP Server (server.py)
     ↓ (accesses)
Tocky Code Backend (orchestrator, storage, scanners)
     ↓ (scans)
Your Codebase
```

## Available MCP Tools

The MCP server exposes these tools to GitHub Copilot:

### 1. `get_vulnerabilities`
Get all detected vulnerabilities with filtering options.

**Parameters:**
- `severity` (optional): Filter by CRITICAL, HIGH, MEDIUM, LOW, INFO
- `language` (optional): Filter by programming language

**Returns:**
```json
{
  "total_vulnerabilities": 5,
  "vulnerabilities": [
    {
      "id": "VULN-001",
      "type": "sql_injection",
      "severity": "CRITICAL",
      "file": "database.py",
      "line": 25,
      "message": "SQL injection vulnerability",
      "evidence": "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')"
    }
  ]
}
```

### 2. `get_file_context`
Retrieve source code context around a vulnerability.

**Parameters:**
- `file` (required): File path
- `line` (required): Line number
- `context_lines` (optional, default: 10): Lines before/after to include

**Returns:**
```json
{
  "file": "database.py",
  "target_line": 25,
  "line_range": "15-35",
  "code": "...(source code)...",
  "vulnerable_line": "cursor.execute(f'SELECT...')"
}
```

### 3. `get_fix_instructions`
Get detailed remediation guidance for a vulnerability.

**Parameters:**
- `vulnerability_id` (required): The vulnerability ID

**Returns:**
```json
{
  "vulnerability_id": "VULN-001",
  "type": "sql_injection",
  "root_cause": "Unsafe concatenation of user input...",
  "security_impact": "Attackers can read, modify...",
  "remediation": "Use parameterized queries...",
  "references": ["https://cwe.mitre.org/..."]
}
```

### 4. `apply_security_patch`
Apply a security fix to a file (with validation and backup).

**Parameters:**
- `file` (required): File to patch
- `original_code` (required): Code to replace
- `fixed_code` (required): Secure replacement
- `vulnerability_id` (required): ID being fixed

**Returns:**
```json
{
  "status": "success",
  "message": "Patch applied successfully",
  "backup_created": "/path/to/backup"
}
```

### 5. `verify_security_fix`
Verify that a fix resolved the vulnerability.

**Parameters:**
- `vulnerability_id` (required): ID to verify
- `run_tests` (optional, default: true): Run tests

**Returns:**
```json
{
  "vulnerability_id": "VULN-001",
  "status": "VERIFIED",
  "rescan_passed": true,
  "message": "Vulnerability successfully fixed"
}
```

### 6. `scan_workspace`
Trigger a new security scan.

**Parameters:**
- `target_path` (optional): Specific path to scan

**Returns:**
```json
{
  "scan_completed": true,
  "total_findings": 12,
  "by_severity": {"CRITICAL": 2, "HIGH": 5, ...}
}
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend/mcp_server
pip install -r requirements.txt
```

### 2. Configure GitHub Copilot

The MCP server is configured in `.vscode/mcp.json`. GitHub Copilot will automatically discover and connect to it.

### 3. Test the MCP Server

Run manually to test:
```bash
cd backend
python -m mcp_server.server
```

### 4. Use with Copilot

Once configured, you can use Copilot Chat with commands like:

```
@workspace Scan for vulnerabilities and show me the critical ones
```

```
@workspace Get details about vulnerability VULN-001 and propose a fix
```

```
@workspace Apply security fixes for all SQL injection vulnerabilities
```

## Automated Workflow

### Typical Flow:

1. **Scan** - Tocky scans the workspace
2. **Detect** - Vulnerabilities are stored in the database
3. **Query** - Copilot asks MCP server for vulnerabilities
4. **Analyze** - Copilot retrieves code context
5. **Generate** - Copilot creates security patch
6. **Apply** - MCP server applies patch (with backup)
7. **Verify** - Re-scan confirms fix
8. **Report** - Status updated in dashboard

## Security Features

✅ **Automatic Backups** - Creates `.tocky-backup` files before patching
✅ **Path Validation** - Ensures patches only affect workspace files
✅ **Code Validation** - Verifies original code exists before patching
✅ **Audit Trail** - Logs all patch applications
✅ **Re-scanning** - Confirms vulnerabilities are resolved
✅ **Rollback Support** - Backup files enable easy rollback

## Environment Variables

- `TOCKY_WORKSPACE` - Workspace path (auto-set by VS Code)

## Troubleshooting

### Server not starting
```bash
# Check Python path
python --version

# Test import
python -c "from mcp.server import Server; print('MCP OK')"
```

### Copilot not detecting server
1. Check `.vscode/mcp.json` exists
2. Reload VS Code window
3. Check Copilot settings → MCP Servers

### Tools not appearing
1. Ensure Tocky has scanned at least once
2. Check `.codeguard/history.db` exists
3. Verify workspace path is correct

## Development

### Adding New Tools

1. Add tool definition in `_register_tools()`
2. Implement handler method
3. Update this README
4. Test with Copilot

### Testing

```bash
# Run server in debug mode
PYTHONPATH=backend python backend/mcp_server/server.py

# Test with MCP inspector (if available)
mcp dev backend/mcp_server/server.py
```

## Integration with VS Code Extension

The VS Code extension can notify the MCP server of new scans:

```typescript
// After scan completes
vscode.commands.executeCommand('mcp.notifyUpdate', {
  server: 'tocky-code',
  event: 'scan_completed'
});
```

## Future Enhancements

- [ ] Batch fix application
- [ ] Fix preview/diff before applying
- [ ] Integration with CI/CD pipelines
- [ ] Custom remediation templates
- [ ] Machine learning for fix quality prediction
- [ ] Multi-file refactoring support

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [GitHub Copilot MCP Integration](https://github.com/features/copilot)
- [Tocky Code Documentation](../README.md)
