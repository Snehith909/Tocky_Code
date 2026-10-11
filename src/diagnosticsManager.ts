/**
 * Diagnostics and Code Actions manager for CodeGuard AI.
 * Surfaces editor squiggles and Quick Fix actions directly on vulnerable code.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { Finding, SeverityLevel } from './types';

export class DiagnosticsManager implements vscode.CodeActionProvider {
  private diagnosticCollection: vscode.DiagnosticCollection;
  private currentFindings: Finding[] = [];

  constructor() {
    this.diagnosticCollection = vscode.languages.createDiagnosticCollection('codeguard');
  }

  public getCollection(): vscode.DiagnosticCollection {
    return this.diagnosticCollection;
  }

  public updateDiagnostics(findings: Finding[], workspaceRoot?: string): void {
    this.currentFindings = findings;
    this.diagnosticCollection.clear();

    const diagnosticsByFile = new Map<string, vscode.Diagnostic[]>();

    for (const f of findings) {
      const targetPath = workspaceRoot ? path.join(workspaceRoot, f.file) : f.file;
      const fileUri = vscode.Uri.file(targetPath).toString();

      const startLine = Math.max(0, f.start_line - 1);
      const endLine = Math.max(0, f.end_line - 1);
      const startCol = f.start_col ? Math.max(0, f.start_col - 1) : 0;
      const endCol = f.end_col ?? 100;

      const range = new vscode.Range(startLine, startCol, endLine, endCol);
      const severity = this.mapSeverity(f.severity);

      const diag = new vscode.Diagnostic(
        range,
        `[CodeGuard AI: ${f.rule_id}] ${f.message}`,
        severity
      );
      diag.source = f.tool;
      diag.code = f.rule_id;

      const existing = diagnosticsByFile.get(fileUri) || [];
      existing.push(diag);
      diagnosticsByFile.set(fileUri, existing);
    }

    for (const [fileUriStr, diags] of diagnosticsByFile.entries()) {
      this.diagnosticCollection.set(vscode.Uri.parse(fileUriStr), diags);
    }
  }

  private mapSeverity(severity: SeverityLevel): vscode.DiagnosticSeverity {
    switch (severity) {
      case 'CRITICAL':
      case 'HIGH':
        return vscode.DiagnosticSeverity.Error;
      case 'MEDIUM':
        return vscode.DiagnosticSeverity.Warning;
      case 'LOW':
      case 'INFO':
      default:
        return vscode.DiagnosticSeverity.Information;
    }
  }

  public provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
    _token: vscode.CancellationToken
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];

    for (const diagnostic of context.diagnostics) {
      if (diagnostic.source === 'builtin' || diagnostic.source === 'semgrep' || diagnostic.source === 'bandit' || diagnostic.source === 'eslint') {
        const finding = this.currentFindings.find(
          (f) =>
            document.uri.fsPath.endsWith(path.normalize(f.file)) &&
            f.start_line - 1 === diagnostic.range.start.line
        );

        if (finding) {
          // Action 1: Propose Fix
          const fixAction = new vscode.CodeAction(
            `CodeGuard: Propose Minimal Fix for ${finding.rule_id}`,
            vscode.CodeActionKind.QuickFix
          );
          fixAction.command = {
            command: 'codeguard.proposeFix',
            title: 'Propose Fix',
            arguments: [finding],
          };
          fixAction.diagnostics = [diagnostic];
          fixAction.isPreferred = true;
          actions.push(fixAction);

          // Action 2: Explain Finding
          const explainAction = new vscode.CodeAction(
            `CodeGuard: Explain Finding Details`,
            vscode.CodeActionKind.Empty
          );
          explainAction.command = {
            command: 'codeguard.explainFinding',
            title: 'Explain Finding',
            arguments: [finding],
          };
          actions.push(explainAction);
        }
      }
    }

    return actions;
  }
}
