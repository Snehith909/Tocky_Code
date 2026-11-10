/**
 * Dedicated API Key Configuration Webview Panel for Tocky Code.
 * Provides a rich form UI to enter, validate, and save LLM API keys
 * to both VS Code settings and the workspace .env file.
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export class ApiKeyWebviewPanel {
  public static readonly viewType = 'codeguard.apiKeyPanel';
  private static _panel: vscode.WebviewPanel | undefined;

  public static createOrShow(extensionUri: vscode.Uri, workspaceRoot?: string): void {
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    if (ApiKeyWebviewPanel._panel) {
      ApiKeyWebviewPanel._panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ApiKeyWebviewPanel.viewType,
      '🔑 Tocky Code — API Key Setup',
      column || vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );

    ApiKeyWebviewPanel._panel = panel;

    panel.onDidDispose(() => {
      ApiKeyWebviewPanel._panel = undefined;
    });

    panel.webview.onDidReceiveMessage(async (message) => {
      switch (message.type) {
        case 'saveKey':
          await ApiKeyWebviewPanel._handleSaveKey(message, workspaceRoot, panel);
          break;
        case 'testKey':
          await ApiKeyWebviewPanel._handleTestKey(message, panel);
          break;
        case 'loadCurrent':
          ApiKeyWebviewPanel._sendCurrentConfig(panel);
          break;
        case 'clearKey':
          await ApiKeyWebviewPanel._handleClearKey(workspaceRoot, panel);
          break;
        case 'openExternal':
          vscode.env.openExternal(vscode.Uri.parse(message.url));
          break;
      }
    });

    panel.webview.html = ApiKeyWebviewPanel._getHtml();
    setTimeout(() => ApiKeyWebviewPanel._sendCurrentConfig(panel), 300);
  }

  private static _sendCurrentConfig(panel: vscode.WebviewPanel): void {
    const config = vscode.workspace.getConfiguration('codeguard');
    const provider = config.get<string>('llmProvider', 'gemini');
    const apiKey = config.get<string>('apiKey', '');
    const model = config.get<string>('model', 'gemini-2.5-flash');
    const customEndpoint = config.get<string>('customLlmEndpoint', 'http://localhost:11434/api/generate');
    panel.webview.postMessage({
      type: 'currentConfig',
      provider,
      apiKey: apiKey ? apiKey.substring(0, 8) + '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : '',
      hasKey: apiKey.length > 0,
      model,
      customEndpoint,
    });
  }

  private static async _handleSaveKey(
    message: any,
    workspaceRoot: string | undefined,
    panel: vscode.WebviewPanel
  ): Promise<void> {
    const config = vscode.workspace.getConfiguration('codeguard');
    const { provider, apiKey, model, customEndpoint } = message;
    try {
      await config.update('llmProvider', provider, vscode.ConfigurationTarget.Global);
      if (apiKey && apiKey.trim()) {
        await config.update('apiKey', apiKey.trim(), vscode.ConfigurationTarget.Global);
      }
      if (model && model.trim()) {
        await config.update('model', model.trim(), vscode.ConfigurationTarget.Global);
      }
      if (provider === 'custom' && customEndpoint) {
        await config.update('customLlmEndpoint', customEndpoint.trim(), vscode.ConfigurationTarget.Global);
      }
      // Write to .env so Python backend picks up the key directly
      if (workspaceRoot && apiKey && apiKey.trim()) {
        ApiKeyWebviewPanel._writeToEnvFile(workspaceRoot, provider, apiKey.trim(), model?.trim() || '');
      }
      panel.webview.postMessage({
        type: 'saveResult',
        success: true,
        message: `API key saved for ${provider.toUpperCase()}! Tocky Code will now use it to fix detected vulnerabilities.`,
      });
      vscode.window.showInformationMessage(
        `Tocky Code: ${provider.toUpperCase()} API key configured successfully.`
      );
      // Notify the extension so it can auto-offer fix proposals using the new key
      vscode.commands.executeCommand('codeguard.onApiKeyUpdated', provider);
    } catch (err: any) {
      panel.webview.postMessage({
        type: 'saveResult',
        success: false,
        message: `Failed to save: ${err.message}`,
      });
    }
  }

  private static _writeToEnvFile(
    workspaceRoot: string,
    provider: string,
    apiKey: string,
    model: string
  ): void {
    const envPath = path.join(workspaceRoot, '.env');
    let content = '';
    if (fs.existsSync(envPath)) {
      content = fs.readFileSync(envPath, 'utf-8');
    }

    const keysToSet: Record<string, string> = {
      CODEGUARD_LLM_PROVIDER: provider,
    };
    if (model) { keysToSet['CODEGUARD_LLM_MODEL'] = model; }
    if (provider === 'gemini')     { keysToSet['GEMINI_API_KEY']    = apiKey; }
    if (provider === 'openai')     { keysToSet['OPENAI_API_KEY']    = apiKey; }
    if (provider === 'anthropic')  { keysToSet['ANTHROPIC_API_KEY'] = apiKey; }

    const lines = content.split('\n');
    const updated: string[] = [];
    const written = new Set<string>();

    for (const line of lines) {
      let replaced = false;
      for (const [k, v] of Object.entries(keysToSet)) {
        if (line.startsWith(k + '=') || line.startsWith('# ' + k + '=')) {
          updated.push(`${k}=${v}`);
          written.add(k);
          replaced = true;
          break;
        }
      }
      if (!replaced) { updated.push(line); }
    }

    for (const [k, v] of Object.entries(keysToSet)) {
      if (!written.has(k)) { updated.push(`${k}=${v}`); }
    }

    fs.writeFileSync(envPath, updated.join('\n'), 'utf-8');
  }

  private static async _handleTestKey(message: any, panel: vscode.WebviewPanel): Promise<void> {
    const { provider, apiKey } = message;
    if (!apiKey || !apiKey.trim()) {
      panel.webview.postMessage({ type: 'testResult', success: false, message: 'Please enter an API key to test.' });
      return;
    }
    let valid = false;
    let detail = '';
    if (provider === 'gemini') {
      valid = apiKey.trim().startsWith('AIza');
      detail = valid ? 'Key format valid (starts with AIza...)' : 'Invalid format — Gemini keys start with "AIza"';
    } else if (provider === 'openai') {
      valid = apiKey.trim().startsWith('sk-');
      detail = valid ? 'Key format valid (starts with sk-...)' : 'Invalid format — OpenAI keys start with "sk-"';
    } else {
      valid = true;
      detail = 'No format check needed for this provider';
    }
    panel.webview.postMessage({
      type: 'testResult',
      success: valid,
      message: (valid ? '\u2705 ' : '\u274c ') + detail,
    });
  }

  private static async _handleClearKey(
    workspaceRoot: string | undefined,
    panel: vscode.WebviewPanel
  ): Promise<void> {
    const config = vscode.workspace.getConfiguration('codeguard');
    await config.update('apiKey', '', vscode.ConfigurationTarget.Global);
    panel.webview.postMessage({ type: 'saveResult', success: true, message: 'API key cleared from settings.' });
    vscode.window.showInformationMessage('Tocky Code: API key cleared.');
  }

  private static _getHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tocky Code - API Key Setup</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family), -apple-system, sans-serif;
      background: var(--vscode-editor-background);
      color: var(--vscode-foreground);
      min-height: 100vh;
    }
    .hero {
      background: linear-gradient(135deg, #0d1117 0%, #0e2a4a 60%, #0d1117 100%);
      border-bottom: 2px solid #1e90d0;
      padding: 28px 32px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .hero-icon { font-size: 38px; }
    .hero-text h1 { font-size: 20px; font-weight: 700; color: #e6edf3; }
    .hero-text p  { font-size: 12px; color: #8b949e; margin-top: 4px; }
    .container { max-width: 680px; margin: 0 auto; padding: 24px 32px 48px; }
    .status-bar {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 16px; border-radius: 8px; margin-bottom: 24px;
      font-size: 12px; font-weight: 500;
      background: rgba(210,153,34,0.12); border: 1px solid #d29922; color: #d29922;
    }
    .status-bar.ok  { background: rgba(35,134,54,0.12); border-color: #238636; color: #3fb950; }
    .card {
      background: var(--vscode-sideBar-background, #161b22);
      border: 1px solid var(--vscode-widget-border, #30363d);
      border-radius: 10px; padding: 22px 24px; margin-bottom: 20px;
    }
    .card-title {
      font-size: 13px; font-weight: 600; margin-bottom: 16px;
      display: flex; align-items: center; gap: 8px;
    }
    .step {
      width: 22px; height: 22px; border-radius: 50%;
      background: linear-gradient(135deg, #1e90d0, #0e639c);
      color: white; font-size: 11px; font-weight: 700;
      display: flex; align-items: center; justify-content: center;
    }
    .provider-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .prov-btn {
      border: 2px solid var(--vscode-widget-border, #30363d);
      border-radius: 8px; padding: 12px 14px; cursor: pointer;
      background: transparent; text-align: left;
      color: var(--vscode-foreground); transition: all 0.15s;
      width: 100%;
    }
    .prov-btn:hover  { border-color: #1e90d0; background: rgba(30,144,208,0.06); }
    .prov-btn.active { border-color: #1e90d0; background: rgba(30,144,208,0.14); box-shadow: 0 0 0 1px #1e90d0; }
    .pname { font-size: 13px; font-weight: 600; }
    .pdesc { font-size: 10px; color: #8b949e; margin-top: 3px; }
    .badge { font-size: 9px; padding: 1px 6px; border-radius: 10px; font-weight: 700; background: #238636; color: white; margin-left: 5px; }
    .form-group { margin-bottom: 16px; }
    label { display: block; font-size: 12px; font-weight: 500; margin-bottom: 6px; }
    .req { color: #f85149; margin-left: 2px; }
    .opt { color: #8b949e; font-weight: 400; font-size: 11px; margin-left: 4px; }
    .iw { position: relative; }
    input[type=text], input[type=password], select {
      width: 100%; padding: 9px 40px 9px 14px;
      background: var(--vscode-input-background, #0d1117);
      border: 1px solid var(--vscode-input-border, #30363d);
      border-radius: 6px; color: var(--vscode-input-foreground, #e6edf3);
      font-size: 13px; font-family: inherit; outline: none; transition: border-color 0.15s;
    }
    input:focus { border-color: #1e90d0; box-shadow: 0 0 0 2px rgba(30,144,208,0.2); }
    .eye-btn {
      position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
      background: none; border: none; color: #8b949e; cursor: pointer; font-size: 14px;
    }
    .eye-btn:hover { color: var(--vscode-foreground); }
    .hint { font-size: 11px; color: #8b949e; margin-top: 5px; }
    .hint a { color: #58a6ff; text-decoration: none; cursor: pointer; }
    .hint a:hover { text-decoration: underline; }
    .btn-row { display: flex; gap: 10px; margin-top: 8px; }
    .btn {
      padding: 10px 18px; border-radius: 6px; border: none;
      font-size: 13px; font-weight: 600; cursor: pointer;
      font-family: inherit; transition: all 0.15s;
      display: flex; align-items: center; gap: 6px;
    }
    .btn-primary { background: linear-gradient(135deg, #1e90d0, #0e639c); color: white; flex: 1; justify-content: center; }
    .btn-primary:hover { background: linear-gradient(135deg, #2ea8e8, #1177bb); transform: translateY(-1px); }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn-ghost { background: var(--vscode-button-secondaryBackground, #21262d); color: var(--vscode-button-secondaryForeground, #c9d1d9); border: 1px solid #30363d; }
    .btn-ghost:hover { background: #30363d; }
    .btn-clear { width: 100%; justify-content: center; background: transparent; color: #f85149; border: 1px solid rgba(248,81,73,0.4); margin-top: 10px; }
    .btn-clear:hover { background: rgba(248,81,73,0.08); border-color: #f85149; }
    .banner {
      display: none; padding: 12px 16px; border-radius: 8px;
      font-size: 13px; font-weight: 500; margin-top: 16px;
      animation: fadeIn 0.2s ease;
    }
    @keyframes fadeIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
    .banner.ok  { background: rgba(35,134,54,0.15); border: 1px solid #238636; color: #3fb950; }
    .banner.err { background: rgba(248,81,73,0.12); border: 1px solid #f85149; color: #f85149; }
    .banner.inf { background: rgba(30,144,208,0.12); border: 1px solid #1e90d0; color: #58a6ff; }
    .hidden { display: none !important; }
    .info-box { background: rgba(30,144,208,0.08); border: 1px solid rgba(30,144,208,0.25); border-radius: 8px; padding: 14px 16px; font-size: 12px; color: #8b949e; line-height: 1.7; }
    .info-box strong { color: #58a6ff; }
    .spin { display:inline-block; width:14px; height:14px; border:2px solid rgba(255,255,255,0.25); border-top-color:#fff; border-radius:50%; animation:spin 0.6s linear infinite; }
    @keyframes spin { to { transform:rotate(360deg); } }
  </style>
</head>
<body>
  <div class="hero">
    <div class="hero-icon">&#128273;</div>
    <div class="hero-text">
      <h1>API Key Configuration</h1>
      <p>Connect Tocky Code to your AI provider for intelligent security fixes</p>
    </div>
  </div>

  <div class="container">

    <div class="status-bar" id="statusBar">
      <span id="sIcon">&#9888;&#65039;</span>
      <span id="sText">No API key configured &mdash; using built-in model as fallback</span>
    </div>

    <!-- Step 1 -->
    <div class="card">
      <div class="card-title"><div class="step">1</div> Select AI Provider</div>
      <div class="provider-grid">
        <button class="prov-btn active" id="prov-gemini" onclick="selectProv('gemini')">
          <div class="pname">&#128311; Google Gemini <span class="badge">Default</span></div>
          <div class="pdesc">gemini-2.5-flash &middot; Free tier available</div>
        </button>
        <button class="prov-btn" id="prov-openai" onclick="selectProv('openai')">
          <div class="pname">&#129302; OpenAI</div>
          <div class="pdesc">gpt-4o-mini &middot; GPT-4o</div>
        </button>
        <button class="prov-btn" id="prov-custom" onclick="selectProv('custom')">
          <div class="pname">&#128421;&#65039; Custom / Local</div>
          <div class="pdesc">Ollama &middot; vLLM &middot; Private server</div>
        </button>
        <button class="prov-btn" id="prov-codeguard-model" onclick="selectProv('codeguard-model')">
          <div class="pname">&#9889; Built-in Engine</div>
          <div class="pdesc">No key needed &middot; Ultra-fast AST</div>
        </button>
      </div>
    </div>

    <!-- Step 2: cloud key -->
    <div class="card" id="cloudCard">
      <div class="card-title"><div class="step">2</div> Enter API Key</div>
      <div class="form-group">
        <label for="keyIn">API Key <span class="req">*</span></label>
        <div class="iw">
          <input type="password" id="keyIn" placeholder="Paste your API key here&hellip;" autocomplete="off" spellcheck="false">
          <button class="eye-btn" onclick="toggleVis()" title="Show/Hide">&#128065;</button>
        </div>
        <div class="hint" id="keyHint">Stored in VS Code settings &amp; your workspace <code>.env</code> file.</div>
      </div>
      <div class="form-group">
        <label for="modelIn">Model <span class="opt">(optional)</span></label>
        <input type="text" id="modelIn" placeholder="e.g. gemini-2.5-flash" value="gemini-2.5-flash">
        <div class="hint" id="modelHint">Options: gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash</div>
      </div>
      <div class="hint" style="margin-top:4px;">
        <a onclick="openKeyPage()" id="keyPageLink">&#128279; Get your Gemini API key at Google AI Studio &rarr;</a>
      </div>
    </div>

    <!-- Step 2: custom endpoint -->
    <div class="card hidden" id="customCard">
      <div class="card-title"><div class="step">2</div> Custom Endpoint</div>
      <div class="form-group">
        <label for="endpIn">Server URL <span class="req">*</span></label>
        <div class="iw"><input type="text" id="endpIn" value="http://localhost:11434/api/generate"></div>
        <div class="hint">Point to your Ollama, vLLM, or OpenAI-compatible local server.</div>
      </div>
      <div class="form-group">
        <label for="localModelIn">Model Name <span class="opt">(optional)</span></label>
        <input type="text" id="localModelIn" placeholder="e.g. llama3, mistral, codellama">
      </div>
    </div>

    <!-- Step 2: built-in -->
    <div class="card hidden" id="builtinCard">
      <div class="card-title"><div class="step">2</div> Built-in Engine</div>
      <div class="info-box">
        <strong>No API key required!</strong><br>
        The built-in Tocky Code engine uses AST pattern synthesis and a local FixCache
        for instant, zero-token remediation. Ideal for offline or privacy-sensitive use.
      </div>
    </div>

    <!-- Actions -->
    <div class="btn-row">
      <button class="btn btn-ghost" onclick="testKey()">&#129514; Validate Key</button>
      <button class="btn btn-primary" id="saveBtn" onclick="saveKey()">&#128190; Save &amp; Apply</button>
    </div>
    <button class="btn btn-clear btn-ghost" onclick="clearKey()">&#128465;&#65039; Clear Saved Key</button>

    <div class="banner" id="banner"></div>
  </div>

  <script>
    const vsc = acquireVsCodeApi();
    let prov = 'gemini', keyVis = false;

    const models = { gemini:'gemini-2.5-flash', openai:'gpt-4o-mini', custom:'', 'codeguard-model':'' };
    const modelHints = {
      gemini:'Options: gemini-2.5-flash, gemini-1.5-flash, gemini-1.5-pro',
      openai:'Options: gpt-4o-mini, gpt-4o, gpt-3.5-turbo',
      custom:'Model name your local server supports',
      'codeguard-model':''
    };
    const keyLinks = {
      gemini:{ text:'&#128279; Get Gemini API key at Google AI Studio &#8594;', url:'https://aistudio.google.com/app/apikey' },
      openai:{ text:'&#128279; Get OpenAI API key at platform.openai.com &#8594;', url:'https://platform.openai.com/api-keys' }
    };
    const placeholders = {
      copilot:'No API key needed - uses your Copilot subscription',
      gemini:'AIzaSy... (Google Gemini API key)',
      openai:'sk-... (OpenAI API key)',
      custom:'No key needed for local models',
      'codeguard-model':''
    };

    function selectProv(p) {
      prov = p;
      document.querySelectorAll('.prov-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('prov-' + p).classList.add('active');
      const show = (id, vis) => document.getElementById(id).classList.toggle('hidden', !vis);
      show('cloudCard',   p !== 'custom' && p !== 'codeguard-model');
      show('customCard',  p === 'custom');
      show('builtinCard', p === 'codeguard-model');
      if (p !== 'custom' && p !== 'codeguard-model') {
        document.getElementById('keyIn').placeholder = placeholders[p] || '';
        document.getElementById('modelIn').value = models[p] || '';
        document.getElementById('modelHint').textContent = modelHints[p] || '';
        const lnk = keyLinks[p];
        const el = document.getElementById('keyPageLink');
        if (lnk) { el.innerHTML = lnk.text; el.style.display = ''; }
        else { el.style.display = 'none'; }
      }
      hideBanner();
    }

    function openKeyPage() {
      const lnk = keyLinks[prov];
      if (lnk) vsc.postMessage({ type:'openExternal', url: lnk.url });
    }

    function toggleVis() {
      keyVis = !keyVis;
      document.getElementById('keyIn').type = keyVis ? 'text' : 'password';
    }

    function saveKey() {
      const key   = document.getElementById('keyIn').value.trim();
      const model = document.getElementById('modelIn').value.trim();
      const endp  = document.getElementById('endpIn').value.trim();
      const lModel = document.getElementById('localModelIn').value.trim();

      if (prov !== 'codeguard-model' && prov !== 'custom' && !key) {
        showBanner('Please enter an API key before saving.', 'err');
        document.getElementById('keyIn').focus();
        return;
      }
      const btn = document.getElementById('saveBtn');
      btn.innerHTML = '<div class="spin"></div> Saving&hellip;';
      btn.disabled = true;
      vsc.postMessage({
        type:'saveKey', provider:prov,
        apiKey: key,
        model: prov === 'custom' ? lModel : model,
        customEndpoint: endp
      });
    }

    function testKey() {
      const key = document.getElementById('keyIn').value.trim();
      vsc.postMessage({ type:'testKey', provider:prov, apiKey:key });
      showBanner('Validating key format&hellip;', 'inf');
    }

    function clearKey() {
      if (confirm('Clear the saved API key?')) vsc.postMessage({ type:'clearKey' });
    }

    function showBanner(msg, cls) {
      const b = document.getElementById('banner');
      b.innerHTML = msg; b.className = 'banner ' + cls; b.style.display = 'block';
    }
    function hideBanner() { document.getElementById('banner').style.display = 'none'; }

    window.addEventListener('message', e => {
      const m = e.data;
      const btn = document.getElementById('saveBtn');
      if (m.type === 'currentConfig') {
        selectProv(m.provider || 'gemini');
        if (m.apiKey) document.getElementById('keyIn').placeholder = m.apiKey + ' (saved — paste to replace)';
        if (m.model)  document.getElementById('modelIn').value = m.model;
        if (m.customEndpoint) document.getElementById('endpIn').value = m.customEndpoint;
        const bar = document.getElementById('statusBar');
        if (m.provider === 'codeguard-model') {
          bar.className='status-bar ok';
          document.getElementById('sIcon').textContent = '\u26a1';
          document.getElementById('sText').textContent = 'Using built-in engine \u2014 no API key needed';
        } else if (m.hasKey) {
          bar.className='status-bar ok';
          document.getElementById('sIcon').textContent = '\u2705';
          document.getElementById('sText').textContent = (m.provider||'').toUpperCase() + ' API key is configured and active';
        } else {
          bar.className='status-bar';
          document.getElementById('sIcon').textContent = '\u26a0\ufe0f';
          document.getElementById('sText').textContent = 'No API key configured \u2014 using built-in model as fallback';
        }
      } else if (m.type === 'saveResult') {
        btn.innerHTML = '&#128190; Save &amp; Apply';
        btn.disabled = false;
        showBanner(m.message, m.success ? 'ok' : 'err');
        if (m.success) {
          document.getElementById('keyIn').value = '';
          document.getElementById('keyIn').placeholder = '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022 (key saved \u2014 paste to replace)';
          const bar = document.getElementById('statusBar');
          bar.className = 'status-bar ok';
          document.getElementById('sIcon').textContent = '\u2705';
          document.getElementById('sText').textContent = (prov||'').toUpperCase() + ' API key saved successfully';
        }
      } else if (m.type === 'testResult') {
        showBanner(m.message, m.success ? 'ok' : 'err');
      }
    });

    vsc.postMessage({ type:'loadCurrent' });
  </script>
</body>
</html>`;
  }
}
