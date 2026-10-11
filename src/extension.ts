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

export function activate(context: vscode.ExtensionContext) {
  const backend = new BackendBridge(context);
  const treeProvider = new FindingsTreeProvider();
  const statusProvider = new StatusWebviewProvider(context.extensionUri);
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

  // 1. Scan Workspace Command
  const scanWorkspaceCmd = vscode.commands.registerCommand('codeguard.scanWorkspace', async () => {
    const root = getWorkspaceRoot();
    if (!root) {
      vscode.window.showWarningMessage('CodeGuard AI: Please open a workspace folder to scan.');
      return;
    }

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'CodeGuard AI: Scanning workspace for security vulnerabilities...',
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
              'CodeGuard AI: No findings detected in configured checks. (Note: Not a guarantee of total security).'
            );
          } else {
            vscode.window.showWarningMessage(
              `CodeGuard AI: Detected ${summary.total_findings} security finding(s) across ${summary.languages_detected.join(', ')}.`
            );
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`CodeGuard AI scan failed: ${err.message}`);
        }
      }
    );
  });

  // 2. Scan Current File Command
  const scanFileCmd = vscode.commands.registerCommand('codeguard.scanFile', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('CodeGuard AI: No active file to scan.');
      return;
    }

    const filePath = editor.document.uri.fsPath;
    const root = getWorkspaceRoot() || path.dirname(filePath);

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `CodeGuard AI: Scanning ${path.basename(filePath)}...`,
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
            `CodeGuard AI: Found ${summary.total_findings} finding(s) in ${path.basename(filePath)}.`
          );
        } catch (err: any) {
          vscode.window.showErrorMessage(`CodeGuard AI file scan failed: ${err.message}`);
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
          title: `CodeGuard AI: Generating minimal fix proposal for ${finding.rule_id}...`,
          cancellable: false,
        },
        async () => {
          try {
            const patch = await backend.proposeFix(root, finding);
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
          title: `CodeGuard AI: Verifying patch in isolated environment...`,
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
          `### CodeGuard AI: ${explanation.rule_id} (${explanation.severity})\n\n` +
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
      `CodeGuard AI Metrics: ${metrics.tokens.total_tokens} tokens consumed, ` +
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
      `# CodeGuard AI Security Scan Report\n\n` +
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

  context.subscriptions.push(
    scanWorkspaceCmd,
    scanFileCmd,
    proposeFixCmd,
    verifyPatchCmd,
    explainFindingCmd,
    showMetricsCmd,
    openReportCmd
  );
}

export function deactivate() {}
