# Fix: Copilot Option Not Showing in Settings

## Problem
The "copilot" option is not appearing in the LLM Provider dropdown in VS Code settings, even though it's in the extension.

## ✅ Solution: Set it Manually via Settings JSON

### Step 1: Open User Settings JSON

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Press Enter

### Step 2: Add This Line

Add this to your settings.json:

```json
{
  "codeguard.llmProvider": "copilot"
}
```

**Full example:**
```json
{
  "workbench.colorTheme": "Dark+",
  "editor.fontSize": 14,
  "codeguard.llmProvider": "copilot"
}
```

### Step 3: Save the File

Press `Ctrl+S` to save

### Step 4: Reload VS Code

1. Press `Ctrl+Shift+P`
2. Type: `Developer: Reload Window`
3. Press Enter

---

## ✅ Alternative: Set to Built-in Model (No Setup Needed)

If you want to use the fast built-in model instead (no Copilot needed):

```json
{
  "codeguard.llmProvider": "codeguard-model"
}
```

This works immediately without any additional setup!

---

## Valid Options

You can set `codeguard.llmProvider` to any of these values:

- `"copilot"` - GitHub Copilot (no API key, requires Copilot extension)
- `"codeguard-model"` - Built-in fast model (no setup, works offline)
- `"gemini"` - Google Gemini (requires API key)
- `"openai"` - OpenAI (requires API key)
- `"custom"` - Local Ollama/custom endpoint
- `"mock"` - Testing/development mode

---

## Test It

After setting and reloading:

1. **Create test file** `test.py`:
```python
import os
os.system(f"ping {user_input}")
```

2. **Scan it:**
```
Ctrl+Shift+P → "Tocky Code: Scan Current File"
```

3. **Fix it:**
```
Click the wrench icon (🔧) on the finding
```

If you set `"copilot"` and Copilot is installed, it will use Copilot.
If you set `"codeguard-model"`, it will use the built-in model (instant, no setup).

---

## Why This Happens

VS Code sometimes caches the settings schema from extensions. By setting it directly in JSON, we bypass the UI cache.

---

## Verify Current Setting

To see what provider is currently set:

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Look for `"codeguard.llmProvider"`

---

## Quick Commands for Copy/Paste

**For Copilot:**
```json
"codeguard.llmProvider": "copilot"
```

**For Built-in Model (easiest):**
```json
"codeguard.llmProvider": "codeguard-model"
```

**For Gemini (if you have API key):**
```json
"codeguard.llmProvider": "gemini",
"codeguard.apiKey": "AIzaSy..."
```

---

## ✅ Recommendation

**Start with the built-in model to test that everything works:**

1. Open Settings JSON (`Ctrl+Shift+P` → `Preferences: Open User Settings (JSON)`)
2. Add: `"codeguard.llmProvider": "codeguard-model"`
3. Save and reload
4. Test scanning and fixing
5. Once confirmed working, switch to `"copilot"` if desired

The built-in model is fast, requires no setup, and will help verify the extension is working correctly!
