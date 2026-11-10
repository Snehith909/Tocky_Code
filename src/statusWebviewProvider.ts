/**
 * Webview View Provider for CodeGuard AI Status, Verification, and Token Metrics panel.
 */

import * as vscode from 'vscode';
import { ScanSummary, VerificationResult, CodeGuardMetrics } from './types';

export class StatusWebviewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'codeguard.statusView';
  private _view?: vscode.WebviewView;

  private latestSummary?: ScanSummary;
  private latestVerification?: VerificationResult;
  private latestMetrics?: CodeGuardMetrics;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _onFirstVisible?: () => void
  ) {}

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this._view = webviewView;
    if (webviewView.visible) {
      this._onFirstVisible?.();
    }
    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        this._onFirstVisible?.();
      }
    });

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.onDidReceiveMessage((data) => {
      switch (data.type) {
        case 'scanWorkspace':
          vscode.commands.executeCommand('codeguard.scanWorkspace');
          break;
        case 'scanFile':
          vscode.commands.executeCommand('codeguard.scanFile');
          break;
        case 'refreshMetrics':
          vscode.commands.executeCommand('codeguard.showMetrics');
          break;
        case 'proposeFix':
          vscode.commands.executeCommand('codeguard.proposeFix');
          break;
        case 'fixAllVulnerabilities':
          vscode.commands.executeCommand('codeguard.fixAll');
          break;
        case 'setApiKey':
          vscode.commands.executeCommand('codeguard.configureApiKey');
          break;
        case 'addApiKey':
          vscode.commands.executeCommand('codeguard.configureApiKey');
          break;
      }
    });

    this.updateHtml();
  }

  public refresh(): void {
    this.updateHtml();
  }

  public updateData(
    summary?: ScanSummary,
    verification?: VerificationResult,
    metrics?: CodeGuardMetrics
  ): void {
    if (summary) {this.latestSummary = summary;}
    if (verification) {this.latestVerification = verification;}
    if (metrics) {this.latestMetrics = metrics;}
    this.updateHtml();
  }

  private updateHtml(): void {
    if (!this._view) {
      return;
    }
    this._view.webview.html = this.getHtmlForWebview();
  }

  private getHtmlForWebview(): string {
    const summary = this.latestSummary;
    const ver = this.latestVerification;
    const metrics = this.latestMetrics;

    const langs = summary?.languages_detected?.join(', ') || 'Auto-detect';
    const totalFindings = summary?.total_findings ?? 0;
    const durationMs = summary?.duration_ms ?? 0;

    let verBadge = '<span class="badge gray">NOT RUN</span>';
    let verDetails = 'No recent patch verified';
    if (ver) {
      if (ver.status === 'VERIFIED') {
        verBadge = '<span class="badge green">VERIFIED</span>';
      } else if (ver.status === 'REJECTED') {
        verBadge = '<span class="badge red">REJECTED</span>';
      } else {
        verBadge = '<span class="badge orange">NEEDS REVIEW</span>';
      }
      verDetails = `Rescan: ${ver.rescan_passed ? 'Passed' : 'Failed'} | Tests: ${ver.tests_run ? (ver.tests_passed ? 'Passed' : 'Failed') : 'Not Run'} (${ver.elapsed_seconds}s)`;
    }

    const totalTokens = metrics?.tokens?.total_tokens ?? 0;
    const tokensSaved = metrics?.tokens?.tokens_saved ?? 0;
    const savedPct = metrics?.tokens?.token_reduction_pct ?? 0;

    const config = vscode.workspace.getConfiguration('codeguard');
    const provider = config.get<string>('llmProvider', 'gemini');
    const apiKey = config.get<string>('apiKey', '').trim();
    const model = config.get<string>('model', 'gemini-2.5-flash');
    const hasKey = apiKey.length > 0 || (provider === 'gemini' && !!process.env.GEMINI_API_KEY) || (provider === 'openai' && !!process.env.OPENAI_API_KEY);
    const keyBadge = (provider === 'codeguard-model')
      ? '<span class="badge green">BUILT-IN</span>'
      : (hasKey ? '<span class="badge green">CONFIGURED ✓</span>' : '<span class="badge orange">NOT SET ⚠️</span>');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tocky Code Status</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      padding: 10px;
      margin: 0;
    }
    .card {
      background: var(--vscode-sideBar-background);
      border: 1px solid var(--vscode-widget-border, #333);
      border-radius: 6px;
      padding: 10px;
      margin-bottom: 12px;
    }
    h3 {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 0 0 8px 0;
      color: var(--vscode-descriptionForeground);
    }
    .row {
      display: flex;
      justify-content: space-between;
      margin: 4px 0;
      font-size: 12px;
    }
    .btn-row {
      display: flex;
      gap: 6px;
      margin-bottom: 8px;
    }
    .btn-row-secondary {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
    }
    button {
      flex: 1;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      padding: 6px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      font-weight: 500;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .btn-api-key {
      background: linear-gradient(135deg, #0e639c, #1177bb);
      color: white;
      border: 1px solid #1e90d0;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.3px;
    }
    .btn-api-key:hover {
      background: linear-gradient(135deg, #1177bb, #1a9ed4);
    }
    .btn-api-key-inline {
      display: flex;
      align-items: center;
      gap: 5px;
      margin-top: 8px;
      width: 100%;
      background: linear-gradient(135deg, #0e639c, #1177bb);
      color: white;
      border: 1px solid #1e90d0;
      border-radius: 4px;
      padding: 5px 10px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      letter-spacing: 0.3px;
      justify-content: center;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-api-key-inline:hover {
      background: linear-gradient(135deg, #1177bb, #1a9ed4);
      transform: translateY(-1px);
    }
    .pulse-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #ffa500;
      display: inline-block;
      animation: pulse 1.4s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.7); }
    }
    .badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 3px;
    }
    .green { background: #238636; color: white; }
    .red { background: #da3633; color: white; }
    .orange { background: #d29922; color: black; }
    .gray { background: #555; color: white; }
    .metric-value {
      font-size: 16px;
      font-weight: 700;
      color: var(--vscode-textLink-foreground);
    }
    .savings-highlight {
      color: #3fb950;
      font-weight: 700;
    }
    .fix-now-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(210,153,34,0.12);
      border: 1px solid #d29922;
      border-radius: 6px;
      padding: 8px 10px;
      margin-bottom: 10px;
      font-size: 11px;
      color: #d29922;
      gap: 6px;
    }
    .btn-fix-now {
      flex-shrink: 0;
      background: linear-gradient(135deg, #238636, #2ea043);
      color: white;
      border: none;
      border-radius: 4px;
      padding: 5px 10px;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
    }
    .btn-fix-now:hover {
      background: linear-gradient(135deg, #2ea043, #3fb950);
      transform: translateY(-1px);
    }
  </style>
</head>
<body>
  <div class="btn-row">
    <button onclick="post('scanWorkspace')">Scan Workspace</button>
    <button onclick="post('scanFile')">Scan File</button>
    <button onclick="post('proposeFix')" style="background: #238636; color: white;">🔧 Fix Issues</button>
  </div>
  <div class="btn-row-secondary">
    <button class="btn-api-key" onclick="post('addApiKey')">🔑 Add / Update API Key</button>
  </div>
  ${totalFindings > 0 && hasKey ? `<div class="fix-now-banner">
    <span>⚠️ ${totalFindings} vulnerability(s) ready to fix</span>
    <button class="btn-fix-now" onclick="post('fixAllVulnerabilities')">⚡ Fix with ${provider.toUpperCase()} Key</button>
  </div>` : ''}

  <div class="card">
    <h3>Workspace Overview</h3>
    <div class="row"><span>Languages:</span><span><b>${langs}</b></span></div>
    <div class="row"><span>Active Scanners:</span><span><b>${summary?.scanners_run?.length || 5} tools</b></span></div>
    <div class="row"><span>Total Findings:</span><span><b>${totalFindings}</b></span></div>
    <div class="row"><span>Scan Latency:</span><span>${durationMs} ms</span></div>
  </div>

  <div class="card">
    <h3>Model Engine</h3>
    <div class="row"><span>Remediation Model:</span><span><b style="background:#238636;color:white;padding:2px 7px;border-radius:3px;font-size:10px;">Tocky-Model</b></span></div>
    <div class="row"><span>Strategy:</span><span style="font-size:11px;">AST + Ultra-Low Token</span></div>
    <div class="row" style="margin-top:6px;"><span>Active Provider:</span><span><b>${provider.toUpperCase()}</b></span></div>
    <div class="row"><span>Model:</span><span>${model}</span></div>
    <div class="row"><span>API Key Status:</span>${keyBadge}</div>
    <button class="btn-api-key-inline" onclick="post('addApiKey')">
      ${!hasKey ? '<span class="pulse-dot"></span>' : '🔑'} Add / Update API Key
    </button>
  </div>


  <div class="card">
    <h3>Last Verification</h3>
    <div class="row"><span>Outcome:</span>${verBadge}</div>
    <div style="font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 6px;">
      ${verDetails}
    </div>
  </div>

  <div class="card">
    <h3>Token Optimization</h3>
    <div class="row"><span>Tokens Consumed:</span><span class="metric-value">${totalTokens}</span></div>
    <div class="row"><span>Baseline Saved:</span><span class="savings-highlight">${tokensSaved} tok</span></div>
    <div class="row"><span>Token Reduction:</span><span class="savings-highlight">${savedPct}%</span></div>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    function post(type) {
      vscode.postMessage({ type });
    }
  </script>
</body>
</html>`;
  }
}
