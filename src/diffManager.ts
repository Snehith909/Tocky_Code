/**
 * Diff review and patch application manager for CodeGuard AI.
 * Uses VS Code diff viewer with virtual document provider to let developers review
 * proposals before applying them to workspace files.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { PatchProposal, Finding } from './types';

export class PatchContentProvider implements vscode.TextDocumentContentProvider {
  static scheme = 'codeguard-patch';
  private patches = new Map<string, string>();

  private _onDidChange = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this._onDidChange.event;

  public setContent(uri: vscode.Uri, content: string): void {
    this.patches.set(uri.toString(), content);
    this._onDidChange.fire(uri);
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.patches.get(uri.toString()) || '';
  }
}

export class DiffManager {
  private activePatches = new Map<string, { finding: Finding; patch: PatchProposal }>();

  constructor(private contentProvider: PatchContentProvider) {}

  public async openDiffReview(
    finding: Finding,
    patch: PatchProposal,
    workspaceRoot: string
  ): Promise<void> {
    const originalFileUri = vscode.Uri.file(path.join(workspaceRoot, patch.target_file));

    // Read current file content
    let originalText = '';
    try {
      originalText = fs.readFileSync(originalFileUri.fsPath, 'utf-8');
    } catch {
      originalText = finding.evidence;
    }

    // Compute proposed file text by replacing original snippet with replacement snippet
    let patchedText = originalText;
    if (patch.original_snippet && patch.replacement_snippet) {
      patchedText = originalText.replace(patch.original_snippet, patch.replacement_snippet);
    }

    const virtualUri = vscode.Uri.parse(
      `${PatchContentProvider.scheme}://preview/${path.basename(patch.target_file)}?patchId=${patch.id}`
    );

    this.contentProvider.setContent(virtualUri, patchedText);
    this.activePatches.set(patch.id, { finding, patch });

    // Open side-by-side diff
    await vscode.commands.executeCommand(
      'vscode.diff',
      originalFileUri,
      virtualUri,
      `CodeGuard Fix Review: ${path.basename(patch.target_file)} (Original ↔ Proposed Fix)`,
      { preview: true }
    );

    // Show prompt with explicit Approve / Verify / Reject options
    const choice = await vscode.window.showInformationMessage(
      `CodeGuard AI proposed fix for ${finding.rule_id}. Explanation: ${patch.explanation}`,
      'Verify Fix in Sandbox',
      'Approve & Apply',
      'Reject'
    );

    if (choice === 'Verify Fix in Sandbox') {
      await vscode.commands.executeCommand('codeguard.verifyPatch', finding, patch);
    } else if (choice === 'Approve & Apply') {
      await this.applyPatch(patch, workspaceRoot);
    } else if (choice === 'Reject') {
      await vscode.commands.executeCommand('codeguard.rejectPatch', patch);
    }
  }

  public async applyPatch(patch: PatchProposal, workspaceRoot: string): Promise<boolean> {
    const targetPath = path.join(workspaceRoot, patch.target_file);

    try {
      const content = fs.readFileSync(targetPath, 'utf-8');
      if (!content.includes(patch.original_snippet)) {
        vscode.window.showErrorMessage(
          `Could not apply patch to ${patch.target_file}: original snippet has changed.`
        );
        return false;
      }

      const updated = content.replace(patch.original_snippet, patch.replacement_snippet);
      fs.writeFileSync(targetPath, updated, 'utf-8');

      patch.approved_by_user = true;
      patch.status = 'APPROVED';

      vscode.window.showInformationMessage(
        `[CodeGuard AI] Patch successfully applied to ${patch.target_file}.`
      );
      return true;
    } catch (err: any) {
      vscode.window.showErrorMessage(`Failed to write file ${patch.target_file}: ${err.message}`);
      return false;
    }
  }
}
