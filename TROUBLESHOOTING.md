# Troubleshooting: "Fix Issue" Not Working

## Current Issue
When you click "Fix Issue" or "Propose Fix" on a vulnerability, it doesn't redirect to Copilot or generate a fix.

## Steps to Fix

### 1. **Reload VS Code Window**
After reinstalling the extension, you MUST reload VS Code:

**Method 1: Command Palette**
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: `Developer: Reload Window`
3. Press Enter

**Method 2: Close and Reopen**
- Close VS Code completely
- Reopen your project folder

### 2. **Verify Extension is Active**

Check if Tocky Code is loaded:
1. Look for the **shield icon** in the left sidebar (Activity Bar)
2. Click it to open the Tocky Code panel
3. You should see "Security Findings" and "Verification & Metrics"

### 3. **Check Copilot Status**

**Option A: If you have GitHub Copilot installed**
```
1. Press Ctrl+Shift+P
2. Type: "Copilot: Show Status"
3. Should show: "Ready" or "Active"
```

**Option B: If you DON'T have GitHub Copilot**
- Install it from: https://marketplace.visualstudio.com/items?itemName=GitHub.copilot
- Sign in with your GitHub account that has Copilot access
- OR use the built-in model instead (see step 5)

### 4. **Configure Provider**

Set the LLM provider in VS Code settings:

**Quick Method:**
1. Press `Ctrl+,` to open Settings
2. Search for: `codeguard llm`
3. Find: **Codeguard: Llm Provider**
4. Select one of:
   - `copilot` (recommended if you have Copilot)
   - `codeguard-model` (built-in, no setup needed)
   - `gemini` (requires API key)

**Settings JSON Method:**
1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Add:
```json
{
  "codeguard.llmProvider": "copilot"
}
```

Or use built-in model (no Copilot needed):
```json
{
  "codeguard.llmProvider": "codeguard-model"
}
```

### 5. **Test the Fix Flow**

#### Step-by-step test:

1. **Create a test file with a vulnerability:**

Create `test_vuln.py`:
```python
import os

# Vulnerable code - command injection
def run_command(user_input):
    os.system(f"ping {user_input}")

run_command("google.com")
```

2. **Scan the file:**
   - Open `test_vuln.py`
   - Press `Ctrl+Shift+P`
   - Type: `Tocky Code: Scan Current File`
   - Press Enter

3. **You should see:**
   - Notification: "Found X finding(s)"
   - Findings appear in the left sidebar under "Security Findings"

4. **Propose a fix:**
   - Click on the finding in the sidebar
   - Click the **wrench icon** (🔧) or right-click → "Propose Fix"
   
5. **What should happen:**
   
   **If using Copilot (llmProvider = "copilot"):**
   - Progress notification: "Generating minimal fix proposal..."
   - If Copilot is available: Fix is generated using Copilot
   - If Copilot is NOT available: Dialog appears with options:
     ```
     🤖 GitHub Copilot is not available. Use another provider?
     [Use Built-in Model] [Configure API Key] [Cancel]
     ```

   **If using built-in model (llmProvider = "codeguard-model"):**
   - Progress notification: "Generating minimal fix proposal..."
   - Fix is generated immediately using the fast built-in engine
   - Diff view opens showing the proposed fix

6. **Review the fix:**
   - A diff editor opens showing:
     - LEFT: Original vulnerable code
     - RIGHT: Fixed secure code
   - Explanation of what was fixed
   - Buttons: "Approve & Apply" or "Reject"

### 6. **Common Issues & Solutions**

#### Issue: "GitHub Copilot is not available"
**Solution:**
- Option 1: Install GitHub Copilot extension and sign in
- Option 2: Change provider to `codeguard-model`:
  ```
  Settings → Search "codeguard llm" → Select "codeguard-model"
  ```

#### Issue: Nothing happens when clicking "Propose Fix"
**Solutions:**
1. Check VS Code Developer Console for errors:
   - Press `Ctrl+Shift+I` (or `Cmd+Option+I` on Mac)
   - Look for red error messages
   - Share the error if you see one

2. Check Output panel:
   - Press `Ctrl+Shift+U`
   - Select "Tocky Code" from dropdown
   - Look for error messages

3. Verify extension is loaded:
   ```
   Press Ctrl+Shift+P
   Type: "Tocky Code"
   You should see all Tocky Code commands
   ```

#### Issue: "No active findings to propose fix for"
**Solution:**
- First scan a file with vulnerabilities
- Make sure the scan found issues
- Check the sidebar for findings

### 7. **Verify Configuration**

Run these checks:

1. **Check current provider:**
   - Press `Ctrl+,`
   - Search: `codeguard.llmProvider`
   - Current value should be: `copilot` or `codeguard-model`

2. **Check extension version:**
   ```
   code --list-extensions --show-versions | findstr tocky
   ```
   Should show: `tocky.tocky-code@0.1.0`

3. **Test Copilot availability** (if using Copilot):
   - Create a new file
   - Start typing code
   - Copilot suggestions should appear
   - If not, Copilot isn't properly set up

### 8. **Quick Test Command**

Open VS Code Terminal and run:
```bash
# Check if extension is installed
code --list-extensions | findstr tocky

# Expected output:
# tocky.tocky-code
```

### 9. **Full Reset (If nothing else works)**

1. Uninstall extension:
   ```bash
   code --uninstall-extension tocky.tocky-code
   ```

2. Close VS Code completely

3. Reinstall:
   ```bash
   code --install-extension E:\Miniproject\tocky-code-0.1.0.vsix
   ```

4. Reopen VS Code

5. Set provider:
   - Press `Ctrl+,`
   - Search: `codeguard.llmProvider`
   - Select: `codeguard-model` (easiest to test)

6. Test with the vulnerable Python file above

### 10. **Working Example Video Flow**

Here's what the complete flow should look like:

```
1. Open file with vulnerability
   ↓
2. Ctrl+Shift+P → "Tocky Code: Scan Current File"
   ↓
3. Notification: "Found 1 finding(s)"
   ↓
4. Shield icon in sidebar shows red badge (1)
   ↓
5. Click shield icon → See finding listed
   ↓
6. Click wrench icon (🔧) on the finding
   ↓
7. Progress: "Generating minimal fix proposal..."
   ↓
8. Diff editor opens with before/after code
   ↓
9. Explanation shown in the diff
   ↓
10. Click "Approve & Apply" to fix the code
```

---

## Debug Output

If it's still not working, share:

1. **VS Code version:**
   ```
   Help → About → Copy version info
   ```

2. **Extension list:**
   ```bash
   code --list-extensions --show-versions
   ```

3. **Developer Console errors:**
   - Press `Ctrl+Shift+I`
   - Go to Console tab
   - Copy any red errors

4. **Current settings:**
   ```json
   // Press Ctrl+Shift+P → "Preferences: Open User Settings (JSON)"
   // Copy the codeguard.* settings
   ```

5. **Output panel:**
   - Press `Ctrl+Shift+U`
   - Select "Tocky Code"
   - Copy the log output

---

## Quick Fix (Try This First!)

**The simplest solution to test immediately:**

1. Press `Ctrl+Shift+P`
2. Type: `Developer: Reload Window`
3. Press Enter
4. Open Settings (`Ctrl+,`)
5. Search: `codeguard.llmProvider`
6. Select: `codeguard-model`
7. Test the scan → fix flow with the vulnerable Python code above

This uses the built-in model (no Copilot or API key needed) and should work immediately!
