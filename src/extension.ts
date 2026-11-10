/**
 * Main extension entry point for CodeGuard AI.
 * Wires commands, sidebar views, diagnostics, and patch verification.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { BackendBridge } from './backendBridge';
import { FindingsTreeProvider, FindingTreeItem } from './findingsTreeProvider';
import { StatusWebviewProvider } from './statusWebviewProvider';
import { DiagnosticsManager } from './diagnosticsManager';
import { DiffManager, PatchContentProvider } from './diffManager';
import { Finding, PatchProposal, VerificationResult, ScanSummary } from './types';
import { ApiKeyWebviewPanel } from './apiKeyWebviewPanel';
import { CopilotProvider } from './copilotProvider';

export function activate(context: vscode.ExtensionContext) {
  const backend = new BackendBridge(context);
  const treeProvider = new FindingsTreeProvider();
  let autoWorkflowStarted = false;
  const statusProvider = new StatusWebviewProvider(context.extensionUri, () => {
    if (!autoWorkflowStarted) {
      autoWorkflowStarted = true;
      void vscode.commands.executeCommand('codeguard.autoFixWorkspace');
    }
  });
  const diagnostics = new DiagnosticsManager();

  const patchContentProvider = new PatchContentProvider();
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(
      PatchContentProvider.scheme,
      patchContentProvider
    )
  );

  const diffManager = new DiffManager(patchContentProvider);

  // Register sidebar views
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('codeguard.findingsView', treeProvider)
  );

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      StatusWebviewProvider.viewType,
      statusProvider
    )
  );

  // Register Diagnostics and Code Actions
  context.subscriptions.push(diagnostics.getCollection());
  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      [
        { language: 'python' },
        { language: 'javascript' },
        { language: 'typescript' },
        { language: 'json' },
      ],
      diagnostics,
      {
        providedCodeActionKinds: [
          vscode.CodeActionKind.QuickFix,
          vscode.CodeActionKind.Empty,
        ],
      }
    )
  );

  let currentSummary: ScanSummary | undefined;
  let currentVerification: VerificationResult | undefined;

  const getWorkspaceRoot = (): string | undefined => {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  };

  /**
   * Checks whether an API key is configured; if not, shows a one-time
   * info message with an action button that opens the API Key panel.
   */
  const checkAndPromptApiKey = async (silent = false): Promise<void> => {
    const config = vscode.workspace.getConfiguration('codeguard');
    const provider = config.get<string>('llmProvider', 'copilot');
    const apiKey = config.get<string>('apiKey', '').trim();
    
    // Check if user has Copilot provider selected
    if (provider === 'copilot') {
      const copilotAvailable = await CopilotProvider.isAvailable();
      if (!copilotAvailable && !silent) {
        const action = await vscode.window.showWarningMessage(
          '🤖 GitHub Copilot is not available. Please install and activate Copilot, or configure an API key.',
          'Install Copilot',
          'Use API Key Instead',
          'Use Built-in Model'
        );
        
        if (action === 'Install Copilot') {
          vscode.env.openExternal(vscode.Uri.parse('https://marketplace.visualstudio.com/items?itemName=GitHub.copilot'));
        } else if (action === 'Use API Key Instead') {
          const root = getWorkspaceRoot();
          ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
        } else if (action === 'Use Built-in Model') {
          await config.update('llmProvider', 'codeguard-model', vscode.ConfigurationTarget.Global);
          vscode.window.showInformationMessage('Switched to built-in CodeGuard model.');
        }
      }
      return;
    }
    
    const hasKey =
      apiKey.length > 0 ||
      provider === 'codeguard-model' ||
      (provider === 'gemini' && !!process.env.GEMINI_API_KEY) ||
      (provider === 'openai' && !!process.env.OPENAI_API_KEY);
      
    if (!hasKey && !silent) {
      const copilotAvailable = await CopilotProvider.isAvailable();
      const actions = copilotAvailable 
        ? ['Use Copilot (No Key Needed)', 'Add API Key', 'Later']
        : ['Add API Key', 'Later'];
        
      const action = await vscode.window.showInformationMessage(
        '🔑 Tocky Code: No API key configured. Choose how to enable AI-powered fix proposals.',
        ...actions
      );
      
      if (action === 'Use Copilot (No Key Needed)') {
        await config.update('llmProvider', 'copilot', vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage('✓ Switched to GitHub Copilot. No API key needed!');
      } else if (action === 'Add API Key') {
        const root = getWorkspaceRoot();
        ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
      }
    }
  };

  // 1. Scan Workspace Command
  const scanWorkspaceCmd = vscode.commands.registerCommand('codeguard.scanWorkspace', async () => {
    const root = getWorkspaceRoot();
    if (!root) {
      vscode.window.showWarningMessage('Tocky Code: Please open a workspace folder to scan.');
      return;
    }

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Tocky Code: Scanning workspace for security vulnerabilities...',
        cancellable: false,
      },
      async (progress) => {
        try {
          progress.report({ increment: 20 });
          const summary = await backend.scan(root);
          currentSummary = summary;

          treeProvider.setFindings(summary.findings);
          diagnostics.updateDiagnostics(summary.findings, root);

          const metrics = await backend.getMetrics(root);
          statusProvider.updateData(summary, currentVerification, metrics);

          progress.report({ increment: 80 });

          if (summary.total_findings === 0) {
            vscode.window.showInformationMessage(
              'Tocky Code: No findings detected in configured checks. (Note: Not a guarantee of total security).'
            );
          } else {
            vscode.window.showWarningMessage(
              `Tocky Code: Detected ${summary.total_findings} security finding(s) across ${summary.languages_detected.join(', ')}.`
            );
            // Nudge user to add an API key so fix proposals work
            await checkAndPromptApiKey(false);
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`Tocky Code scan failed: ${err.message}`);
        }
      }
    );
  });

  // 2. Scan Current File Command
  const scanFileCmd = vscode.commands.registerCommand('codeguard.scanFile', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('Tocky Code: No active file to scan.');
      return;
    }

    const filePath = editor.document.uri.fsPath;
    const root = getWorkspaceRoot() || path.dirname(filePath);

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Tocky Code: Scanning ${path.basename(filePath)}...`,
        cancellable: false,
      },
      async () => {
        try {
          const summary = await backend.scan(filePath);
          treeProvider.setFindings(summary.findings);
          diagnostics.updateDiagnostics(summary.findings, root);

          const metrics = await backend.getMetrics(root);
          statusProvider.updateData(summary, currentVerification, metrics);

          vscode.window.showInformationMessage(
            `Tocky Code: Found ${summary.total_findings} finding(s) in ${path.basename(filePath)}.`
          );
        } catch (err: any) {
          vscode.window.showErrorMessage(`Tocky Code file scan failed: ${err.message}`);
        }
      }
    );
  });

  // 3. Propose Fix Command
  const proposeFixCmd = vscode.commands.registerCommand(
    'codeguard.proposeFix',
    async (item?: Finding | FindingTreeItem) => {
      let finding: Finding | undefined;
      if (item instanceof FindingTreeItem) {
        finding = item.finding;
      } else if (item && 'rule_id' in item) {
        finding = item;
      } else {
        const findings = treeProvider.getFindings();
        if (findings.length === 0) {
          vscode.window.showInformationMessage('No active findings to propose fix for.');
          return;
        }
        finding = findings[0];
      }

      if (!finding) {
        vscode.window.showWarningMessage('Please select a finding to propose a fix for.');
        return;
      }

      const root = getWorkspaceRoot();
      if (!root) {
        vscode.window.showWarningMessage('Workspace root required for fix generation.');
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `Tocky Code: Generating minimal fix proposal for ${finding.rule_id}...`,
          cancellable: false,
        },
        async () => {
          try {
            const config = vscode.workspace.getConfiguration('codeguard');
            const provider = config.get<string>('llmProvider', 'copilot');
            
            let patch: PatchProposal;
            
            // Check if using Copilot provider
            if (provider === 'copilot') {
              const copilotAvailable = await CopilotProvider.isAvailable();
              if (!copilotAvailable) {
                const action = await vscode.window.showWarningMessage(
                  '🤖 GitHub Copilot is not available. Use another provider?',
                  'Use Built-in Model',
                  'Configure API Key',
                  'Cancel'
                );
                
                if (action === 'Use Built-in Model') {
                  await config.update('llmProvider', 'codeguard-model', vscode.ConfigurationTarget.Global);
                  patch = await backend.proposeFix(root, finding);
                } else if (action === 'Configure API Key') {
                  ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
                  return;
                } else {
                  return;
                }
              } else {
                // Use Copilot to generate fix
                const targetFile = vscode.Uri.file(root + '/' + finding.file);
                let fileContent = '';
                try {
                  const doc = await vscode.workspace.openTextDocument(targetFile);
                  fileContent = doc.getText();
                } catch {
                  fileContent = finding.evidence;
                }
                
                patch = await CopilotProvider.generateFix(finding, fileContent, root);
              }
            } else {
              // Use backend (Gemini, OpenAI, or built-in)
              patch = await backend.proposeFix(root, finding);
            }

            const proposalTokens = patch.tokens_used?.total_tokens ?? 0;
            const proposalMetrics = await backend.getMetrics(root);
            statusProvider.updateData(currentSummary, currentVerification, proposalMetrics);
            
            // Check if the fix used fallback due to API key issues
            const expectedProvider = config.get<string>('llmProvider', 'copilot');
            const isFallback = patch.explanation && (
              patch.explanation.includes('Fallback to CodeGuard') || 
              patch.explanation.includes('Invalid Gemini API key') ||
              patch.explanation.includes('GEMINI_API_KEY not configured')
            );
            
            if (isFallback && expectedProvider !== 'codeguard-model') {
              // Extract the reason from explanation
              const reasonMatch = patch.explanation.match(/\(Fallback[^:]*: ([^)]+)\)/);
              const reason = reasonMatch ? reasonMatch[1] : 'API key issue';
              
              const copilotAvail = await CopilotProvider.isAvailable();
              const actions = copilotAvail 
                ? ['Use Copilot Instead', 'Configure API Key', 'View Fix Anyway']
                : ['Configure API Key', 'View Fix Anyway'];
              
              const action = await vscode.window.showWarningMessage(
                `⚠️ Fix generated using fallback model. ${reason}`,
                ...actions
              );
              
              if (action === 'Use Copilot Instead') {
                await config.update('llmProvider', 'copilot', vscode.ConfigurationTarget.Global);
                vscode.commands.executeCommand('codeguard.proposeFix', finding);
                return;
              } else if (action === 'Configure API Key') {
                ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
                return;
              }
            } else {
              const providerDisplay = patch.provider === 'copilot' ? '🤖 GitHub Copilot' : patch.provider.toUpperCase();
              const tokenMsg = proposalTokens > 0 ? ` using ${proposalTokens} tokens` : '';
              vscode.window.showInformationMessage(
                `Tocky Code: ${providerDisplay} generated fix${tokenMsg}. Total tokens: ${proposalMetrics.tokens.total_tokens}.`
              );
            }

            await diffManager.openDiffReview(finding, patch, root);

            const metrics = await backend.getMetrics(root);
            statusProvider.updateData(currentSummary, currentVerification, metrics);
          } catch (err: any) {
            vscode.window.showErrorMessage(`Fix proposal failed: ${err.message}`);
          }
        }
      );
    }
  );

  // 4. Verify Patch Command
  const verifyPatchCmd = vscode.commands.registerCommand(
    'codeguard.verifyPatch',
    async (finding?: Finding, patch?: PatchProposal) => {
      const root = getWorkspaceRoot();
      if (!root || !finding || !patch) {
        vscode.window.showWarningMessage('Finding and patch proposal required for verification.');
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `Tocky Code: Verifying patch in isolated environment...`,
          cancellable: false,
        },
        async () => {
          try {
            const result = await backend.verifyPatch(root, finding, patch);
            currentVerification = result;

            const metrics = await backend.getMetrics(root);
            statusProvider.updateData(currentSummary, result, metrics);

            if (result.status === 'VERIFIED') {
              const applyNow = await vscode.window.showInformationMessage(
                `✓ Verification Succeeded: All checks passed. Would you like to apply the patch now?`,
                'Approve & Apply',
                'Cancel'
              );
              if (applyNow === 'Approve & Apply') {
                await diffManager.applyPatch(patch, root);
              }
            } else if (result.status === 'REJECTED') {
              vscode.window.showErrorMessage(
                `✗ Verification Rejected: ${result.details}`
              );
            } else {
              vscode.window.showWarningMessage(
                `⚠ Verification Needs Review: ${result.details}`
              );
            }
          } catch (err: any) {
            vscode.window.showErrorMessage(`Verification failed: ${err.message}`);
          }
        }
      );
    }
  );

  // 5. Explain Finding Command
  const explainFindingCmd = vscode.commands.registerCommand(
    'codeguard.explainFinding',
    async (item?: Finding | FindingTreeItem) => {
      let finding: Finding | undefined;
      if (item instanceof FindingTreeItem) {
        finding = item.finding;
      } else if (item && 'rule_id' in item) {
        finding = item;
      }

      if (!finding) {
        return;
      }

      try {
        const explanation = await backend.explain(finding);
        const md = new vscode.MarkdownString(
          `### Tocky Code: ${explanation.rule_id} (${explanation.severity})\n\n` +
          `**File:** \`${explanation.file}:${explanation.line}\`\n\n` +
          `**CWE:** ${explanation.cwe}\n\n` +
          `**Description:** ${explanation.description}\n\n` +
          `**Remediation:** ${explanation.remediation_guidance}`
        );
        vscode.window.showInformationMessage(md.value);
      } catch (err: any) {
        vscode.window.showErrorMessage(`Could not explain finding: ${err.message}`);
      }
    }
  );

  // 6. Metrics & Report Commands
  const showMetricsCmd = vscode.commands.registerCommand('codeguard.showMetrics', async () => {
    const root = getWorkspaceRoot();
    if (!root) {
      return;
    }
    const metrics = await backend.getMetrics(root);
    statusProvider.updateData(currentSummary, currentVerification, metrics);
    vscode.window.showInformationMessage(
      `Tocky Code Metrics: ${metrics.tokens.total_tokens} tokens consumed, ` +
      `${metrics.tokens.tokens_saved} tokens saved (${metrics.tokens.token_reduction_pct}% reduction vs baseline). ` +
      `Verified Fixes: ${metrics.verified_fixes}.`
    );
  });

  const openReportCmd = vscode.commands.registerCommand('codeguard.openReport', async () => {
    if (!currentSummary) {
      vscode.window.showInformationMessage('No scan report generated yet. Run Scan Workspace first.');
      return;
    }

    const reportContent =
      `# Tocky Code Security Scan Report\n\n` +
      `- **Target:** ${currentSummary.workspace_path}\n` +
      `- **Languages:** ${currentSummary.languages_detected.join(', ')}\n` +
      `- **Scanners:** ${currentSummary.scanners_run.join(', ')}\n` +
      `- **Scan Time:** ${currentSummary.duration_ms} ms\n` +
      `- **Total Findings:** ${currentSummary.total_findings}\n\n` +
      `## Findings Breakdown\n` +
      Object.entries(currentSummary.by_severity)
        .map(([k, v]) => `- **${k}:** ${v}`)
        .join('\n') +
      `\n\n## Findings Detail\n` +
      currentSummary.findings
        .map((f, i) => `### ${i + 1}. [${f.severity}] ${f.rule_id}\n- File: \`${f.file}:${f.start_line}\`\n- Tool: ${f.tool}\n- Message: ${f.message}\n- Evidence:\n\`\`\`\n${f.evidence}\n\`\`\``)
        .join('\n\n');

    const doc = await vscode.workspace.openTextDocument({
      content: reportContent,
      language: 'markdown',
    });
    await vscode.window.showTextDocument(doc, { preview: true });
  });

  // 7. Approve & Apply Patch Command
  const applyApprovedPatchCmd = vscode.commands.registerCommand(
    'codeguard.applyApprovedPatch',
    async (patch?: PatchProposal) => {
      const root = getWorkspaceRoot();
      if (!root) {
        vscode.window.showWarningMessage('Tocky Code: Please open a workspace folder.');
        return;
      }

      const targetPatch = patch || diffManager.getLatestPatch();
      if (!targetPatch) {
        vscode.window.showInformationMessage('Tocky Code: No patch proposal is currently open to apply.');
        return;
      }

      await diffManager.applyPatch(targetPatch, root);
    }
  );

  // 8. Reject Proposed Patch Command
  const rejectPatchCmd = vscode.commands.registerCommand(
    'codeguard.rejectPatch',
    async (patch?: PatchProposal) => {
      const targetPatch = patch || diffManager.getLatestPatch();
      if (targetPatch) {
        diffManager.rejectPatch(targetPatch);
      }
      vscode.window.showInformationMessage('Tocky Code: Patch proposal rejected.');
    }
  );

  // 9. Set LLM API Key Command
  const setApiKeyCmd = vscode.commands.registerCommand('codeguard.setApiKey', async () => {
    const config = vscode.workspace.getConfiguration('codeguard');
    const currentKey = config.get<string>('apiKey', '');
    const currentProvider = config.get<string>('llmProvider', 'gemini');

    const providerChoice = await vscode.window.showQuickPick(
      [
        { label: 'gemini', description: 'Google Gemini API (Default: gemini-2.5-flash)' },
        { label: 'openai', description: 'OpenAI API (Default: gpt-4o-mini)' },
        { label: 'codeguard-model', description: 'Built-in Specialized Engine (No API key needed)' },
        { label: 'custom', description: 'Custom / Self-Hosted Endpoint (Ollama, vLLM)' },
      ],
      { placeHolder: `Select LLM Provider (Current: ${currentProvider})` }
    );

    if (!providerChoice) {
      return;
    }

    await config.update('llmProvider', providerChoice.label, vscode.ConfigurationTarget.Global);

    if (providerChoice.label === 'codeguard-model') {
      vscode.window.showInformationMessage('Tocky Code: Switched to built-in specialized model.');
      return;
    }

    if (providerChoice.label === 'custom') {
      const endpoint = await vscode.window.showInputBox({
        prompt: 'Enter your custom LLM endpoint URL',
        value: config.get<string>('customLlmEndpoint', 'http://localhost:11434/api/generate'),
      });
      if (endpoint) {
        await config.update('customLlmEndpoint', endpoint, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage(`Tocky Code: Custom endpoint set to ${endpoint}`);
      }
      return;
    }

    const key = await vscode.window.showInputBox({
      prompt: `Enter your ${providerChoice.label.toUpperCase()} API Key:`,
      password: true,
      value: currentKey,
      placeHolder: providerChoice.label === 'gemini' ? 'AIzaSy...' : 'sk-...',
    });

    if (key !== undefined) {
      await config.update('apiKey', key.trim(), vscode.ConfigurationTarget.Global);
      vscode.window.showInformationMessage(
        `Tocky Code: Successfully saved ${providerChoice.label.toUpperCase()} API key!`
      );
    }
    updateStatusBar();
    statusProvider.refresh();
  });

  // 9b. Configure API Key — opens the dedicated full panel
  const configureApiKeyCmd = vscode.commands.registerCommand('codeguard.configureApiKey', () => {
    const root = getWorkspaceRoot();
    ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
  });

  // 9c. Add API Key — friendly alias surfaced in command palette & sidebar
  const addApiKeyCmd = vscode.commands.registerCommand('codeguard.addApiKey', () => {
    const root = getWorkspaceRoot();
    ApiKeyWebviewPanel.createOrShow(context.extensionUri, root);
  });

  // 9d. Fix all open findings using the configured provider and apply them.
  const fixAllCmd = vscode.commands.registerCommand(
    'codeguard.fixAll',
    async () => {
      const root = getWorkspaceRoot();
      if (!root) {
        vscode.window.showWarningMessage('Tocky Code: Please open a workspace folder.');
        return;
      }

      let findings = treeProvider.getFindings();
      if (findings.length === 0) {
        await vscode.commands.executeCommand('codeguard.scanWorkspace');
        findings = treeProvider.getFindings();
      }

      const openFindings = findings.filter(f => f.status === 'OPEN' || f.status === 'PATCH_PROPOSED');
      if (openFindings.length === 0) {
        vscode.window.showInformationMessage('Tocky Code: No open vulnerabilities to fix.');
        return;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: `Tocky Code: Fixing ${openFindings.length} vulnerability(s)...`,
          cancellable: false,
        },
        async (progress) => {
          let applied = 0;
          let tokensUsed = 0;
          const failures: string[] = [];

          for (let index = 0; index < openFindings.length; index++) {
            const finding = openFindings[index];
            progress.report({
              increment: 100 / openFindings.length,
              message: `[${index + 1}/${openFindings.length}] ${finding.rule_id}`,
            });
            try {
              const config = vscode.workspace.getConfiguration('codeguard');
              const useCopilot = config.get<string>('llmProvider', 'copilot') === 'copilot' &&
                await CopilotProvider.isAvailable();
              let patch: PatchProposal;
              if (useCopilot) {
                const fileUri = vscode.Uri.file(path.join(root, finding.file));
                const document = await vscode.workspace.openTextDocument(fileUri);
                patch = await CopilotProvider.generateFix(finding, document.getText(), root);
              } else {
                patch = await backend.proposeFix(root, finding, 'codeguard-model');
              }
              tokensUsed += patch.tokens_used?.total_tokens ?? 0;
              const verification = await backend.verifyPatch(root, finding, patch, true);
              currentVerification = verification;
              if (verification.rescan_passed && await diffManager.applyPatch(patch, root)) {
                applied++;
              } else {
                failures.push(`${finding.file}:${finding.start_line} (verification failed)`);
              }
            } catch (err: any) {
              failures.push(`${finding.file}:${finding.start_line} (${err.message})`);
            }
          }

          const summary = await backend.scan(root);
          currentSummary = summary;
          treeProvider.setFindings(summary.findings);
          diagnostics.updateDiagnostics(summary.findings, root);
          const metrics = await backend.getMetrics(root);
          statusProvider.updateData(summary, currentVerification, metrics);

          const failureText = failures.length > 0
            ? ` Failed: ${failures.join(', ')}.`
            : '';
          vscode.window.showInformationMessage(
            `Tocky Code: Applied ${applied}/${openFindings.length} fix(es) using ${tokensUsed} tokens. ` +
            `Rescan found ${summary.total_findings} remaining finding(s).${failureText}`
          );

        }
      );
    }
  );

  const autoFixWorkspaceCmd = vscode.commands.registerCommand(
    'codeguard.autoFixWorkspace',
    async () => {
      try {
        await vscode.commands.executeCommand('workbench.action.chat.open', {
          query: 'Tocky Code is scanning this workspace, sending findings to the Copilot remediation workflow, and verifying each fix. Follow the progress here.',
        });
      } catch {
        await vscode.commands.executeCommand('workbench.action.chat.open');
      }
      await vscode.commands.executeCommand('codeguard.fixAll');
    }
  );

  const onApiKeyUpdatedCmd = vscode.commands.registerCommand(
    'codeguard.onApiKeyUpdated',
    async () => vscode.commands.executeCommand('codeguard.fixAll')
  );

  // 10. Status Bar Item for quick API Key and Provider management
  const statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = 'codeguard.configureApiKey';
  statusBarItem.tooltip = 'Tocky Code: Click to update LLM API Key & Provider';
  const updateStatusBar = () => {
    const config = vscode.workspace.getConfiguration('codeguard');
    const provider = config.get<string>('llmProvider', 'gemini');
    const apiKey = config.get<string>('apiKey', '').trim();
    const hasKey = apiKey.length > 0 || (provider === 'gemini' && !!process.env.GEMINI_API_KEY) || (provider === 'openai' && !!process.env.OPENAI_API_KEY);
    statusBarItem.text = `$(key) Tocky: ${provider} ${hasKey ? '✓' : '(!)'}`;
    statusBarItem.show();
  };
  updateStatusBar();

  const configChangeListener = vscode.workspace.onDidChangeConfiguration((e) => {
    if (e.affectsConfiguration('codeguard')) {
      updateStatusBar();
      statusProvider.refresh();

      if (e.affectsConfiguration('codeguard.apiKey')) {
        const key = vscode.workspace.getConfiguration('codeguard').get<string>('apiKey', '').trim();
        if (!key) {
          // Key was cleared — gently remind the user
          checkAndPromptApiKey(false);
        } else {
          // Key was just set/updated — offer to fix open findings immediately
          const provider = vscode.workspace.getConfiguration('codeguard').get<string>('llmProvider', 'gemini');
          vscode.commands.executeCommand('codeguard.onApiKeyUpdated', provider);
        }
      }
    }
  });

  context.subscriptions.push(
    scanWorkspaceCmd,
    scanFileCmd,
    proposeFixCmd,
    verifyPatchCmd,
    explainFindingCmd,
    showMetricsCmd,
    openReportCmd,
    applyApprovedPatchCmd,
    rejectPatchCmd,
    setApiKeyCmd,
    configureApiKeyCmd,
    addApiKeyCmd,
    fixAllCmd,
    autoFixWorkspaceCmd,
    onApiKeyUpdatedCmd,
    statusBarItem,
    configChangeListener
  );

  // Prompt on first activation if no key is set (delayed so UI settles)
  setTimeout(() => checkAndPromptApiKey(false), 2000);
}

export function deactivate() {}
