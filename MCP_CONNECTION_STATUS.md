# MCP Connection Status and Setup Guide

## ⚠️ Current Status: MCP NOT Connected to Copilot Yet

### What's Ready:
- ✅ MCP server implemented (`backend/mcp_server/server.py`)
- ✅ Configuration file exists (`.vscode/mcp.json`)
- ✅ MCP Python module installed
- ✅ 6 tools ready: get_vulnerabilities, get_file_context, get_fix_instructions, apply_security_patch, verify_security_fix, scan_workspace

### What's NOT Ready:
- ❌ MCP server not registered with GitHub Copilot
- ❌ Connection not activated
- ❌ Data not flowing to Copilot yet

---

## 🔌 How MCP Connection Works

```
┌─────────────────────────────────────────────────────┐
│ GitHub Copilot Extension                             │
│ - Needs to know about MCP servers                   │
│ - Reads from specific config location               │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ MCP Server Configuration                             │
│ Location: ~/.config/github-copilot/mcp.json (Linux) │
│ Location: %APPDATA%/github-copilot/mcp.json (Win)   │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ Tocky MCP Server (backend/mcp_server/server.py)     │
│ - Exposes vulnerability data                        │
│ - Provides 6 tools to Copilot                       │
└─────────────────────────────────────────────────────┘
```

---

## ✅ Option 1: Full MCP Setup (For Future Use)

### Step 1: Create Copilot MCP Config Directory

```powershell
# Create the directory
New-Item -ItemType Directory -Path "$env:APPDATA\github-copilot" -Force
```

### Step 2: Copy MCP Configuration

```powershell
# Copy our MCP config to Copilot's config location
Copy-Item "E:\Miniproject\.vscode\mcp.json" "$env:APPDATA\github-copilot\mcp.json"
```

### Step 3: Reload VS Code

```
Ctrl+Shift+P → "Developer: Reload Window"
```

### Step 4: Test in Copilot Chat

Open Copilot Chat and try:
```
@workspace Use the tocky-code MCP server to show me all vulnerabilities
```

If connected, Copilot will query the MCP server!

---

## ⚠️ Current Limitation: Copilot MCP Support

**GitHub Copilot's MCP support is still rolling out.**

### Check Your Copilot Version:

1. Open Extensions (`Ctrl+Shift+X`)
2. Search: "GitHub Copilot"
3. Check version

**MCP Support Status:**
- **Copilot v1.150+** - Experimental MCP support
- **Copilot v1.160+** - Better MCP support
- **Earlier versions** - No MCP support yet

---

## ✅ Option 2: Use VS Code Language Model API (Already Working!)

**This is what we already have working!**

Instead of MCP, we're using **VS Code's Language Model API** which works TODAY:

### How It Works:

```typescript
// In copilotProvider.ts (already implemented)
const models = await vscode.lm.selectChatModels({ 
  vendor: 'copilot', 
  family: 'gpt-4o' 
});

const response = await model.sendRequest(messages);
```

This directly uses Copilot without MCP!

### Test It Now:

1. **Set provider to copilot:**
   ```json
   "codeguard.llmProvider": "copilot"
   ```

2. **Scan a file**
3. **Click "Propose Fix"**
4. **Copilot generates the fix!**

---

## 🎯 Current Working Setup

### Automatic Tocky Workflow

Opening the Tocky Code sidebar starts the visible workflow:

1. Tocky scans the workspace.
2. Findings are sent through the configured Copilot/CodeGuard remediation provider.
3. Each proposed patch is independently verified in an isolated workspace.
4. Only verified patches are applied, followed by a fresh rescan.
5. Copilot Chat opens with the workflow context so the user can observe the operation.

The extension cannot silently submit messages or force Copilot Chat to invoke MCP tools. MCP remains available for explicit Copilot Chat requests, while the automatic sidebar workflow uses the VS Code Language Model API when Copilot is available and the built-in provider otherwise.

**Right now, you have TWO ways to use Copilot:**

### Method 1: Direct Integration (Working Now!)
```
Tocky Scan → Click Fix → VS Code LM API → Copilot → Fix Generated
```
✅ Works immediately
✅ No MCP needed
✅ Set `"codeguard.llmProvider": "copilot"`

### Method 2: MCP Integration (Future/Advanced)
```
Copilot Chat → @workspace query → MCP Server → Tocky Database → Response
```
⚠️ Requires Copilot MCP support
⚠️ More complex setup
⚠️ Allows natural language queries

---

## 📊 Comparison: VS Code LM API vs MCP

| Feature | VS Code LM API | MCP |
|---------|---------------|-----|
| **Current Status** | ✅ Working now | ⚠️ Needs newer Copilot |
| **Setup** | ✅ Simple | ⚠️ Complex |
| **Fix Generation** | ✅ Yes | ✅ Yes |
| **Natural Language Queries** | ❌ No | ✅ Yes |
| **Batch Operations** | ❌ Manual | ✅ Automated |
| **Chat Integration** | ❌ No | ✅ Yes |

---

## 💡 Recommendation

### For Now: Use VS Code Language Model API

1. **Set provider:**
   ```json
   "codeguard.llmProvider": "copilot"
   ```

2. **Use normally:**
   - Scan files
   - Click fix
   - Copilot generates secure code
   - Apply fix

### For Future: Enable MCP When Available

When GitHub Copilot fully supports MCP:

1. Copy config to Copilot directory
2. Reload VS Code
3. Use natural language in Copilot Chat:
   ```
   @workspace Fix all SQL injections using Tocky's vulnerability data
   ```

---

## 🧪 Test MCP Server Manually

Want to test if the MCP server works?

```powershell
cd E:\Miniproject\backend
python mcp_server\server.py
```

The server should start and wait for connections. Press `Ctrl+C` to stop.

---

## ✅ What's Actually Working Right Now

### Current Working Flow:

1. ✅ **Scan** → Tocky scans code with Semgrep, Bandit, etc.
2. ✅ **Detect** → Vulnerabilities stored in database
3. ✅ **Click Fix** → Extension calls VS Code LM API
4. ✅ **Copilot** → Generates secure fix using context
5. ✅ **Apply** → Patch applied to file
6. ✅ **Verify** → Re-scan confirms fix

**You don't need MCP for this - it's already working!**

---

## 🔮 Future with MCP

When MCP is fully supported:

```
You: "@workspace Show all vulnerabilities"
Copilot: [Queries MCP] "Found 5 vulnerabilities:
         1. SQL Injection in database.py line 25
         2. Command Injection in admin.py line 42
         ..."

You: "@workspace Fix all critical ones"
Copilot: [Queries MCP for each]
         [Generates fixes]
         [Applies via MCP]
         [Verifies via MCP]
         "Fixed 3 critical vulnerabilities ✅"
```

---

## 🎯 Action Items

### To Use Copilot NOW (Recommended):

1. ✅ Set `"codeguard.llmProvider": "copilot"` in settings
2. ✅ Reload VS Code
3. ✅ Scan code
4. ✅ Click fix
5. ✅ Copilot generates secure code

### To Prepare for MCP (Optional):

1. ⏳ Wait for Copilot version with full MCP support
2. ⏳ Copy `.vscode/mcp.json` to `%APPDATA%\github-copilot\mcp.json`
3. ⏳ Test with `@workspace` commands in Copilot Chat

---

## 📝 Summary

**MCP Status:** ⚠️ NOT connected yet (requires newer Copilot version)

**VS Code LM API Status:** ✅ WORKING now

**Recommendation:** Use the working VS Code LM API integration for now. MCP is future-proofing for when GitHub Copilot fully supports it.

**You can still use Copilot to fix vulnerabilities - just not through MCP chat commands yet!**
