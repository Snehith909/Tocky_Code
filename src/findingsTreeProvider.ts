/**
 * TreeDataProvider for CodeGuard AI findings view in sidebar.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { Finding, SeverityLevel } from './types';

export class FindingTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly finding?: Finding,
    public readonly isGroup: boolean = false,
    public readonly severityGroup?: SeverityLevel
  ) {
    super(label, collapsibleState);

    if (isGroup) {
      this.contextValue = 'severityGroup';
      this.iconPath = this.getGroupIcon(severityGroup);
    } else if (finding) {
      this.contextValue = 'finding';
      this.description = `${path.basename(finding.file)}:${finding.start_line}`;
      this.tooltip = new vscode.MarkdownString(
        `**[${finding.severity}] ${finding.rule_id}**\n\n` +
        `*Tool:* ${finding.tool}\n\n` +
        `*File:* ${finding.file}:${finding.start_line}\n\n` +
        `*Message:* ${finding.message}\n\n` +
        `*Evidence:* \`${finding.evidence}\``
      );

      this.iconPath = this.getFindingIcon(finding.severity);

      // Jump to file and line on click
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (workspaceFolder) {
        const fileUri = vscode.Uri.file(path.join(workspaceFolder.uri.fsPath, finding.file));
        const line = Math.max(0, finding.start_line - 1);
        this.command = {
          command: 'vscode.open',
          title: 'Open Finding Location',
          arguments: [
            fileUri,
            {
              selection: new vscode.Range(line, 0, line, 100),
            },
          ],
        };
      }
    }
  }

  private getGroupIcon(severity?: SeverityLevel): vscode.ThemeIcon {
    switch (severity) {
      case 'CRITICAL':
        return new vscode.ThemeIcon('flame', new vscode.ThemeColor('errorForeground'));
      case 'HIGH':
        return new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
      case 'MEDIUM':
        return new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
      case 'LOW':
        return new vscode.ThemeIcon('info', new vscode.ThemeColor('editorInfo.foreground'));
      default:
        return new vscode.ThemeIcon('shield');
    }
  }

  private getFindingIcon(severity: SeverityLevel): vscode.ThemeIcon {
    switch (severity) {
      case 'CRITICAL':
      case 'HIGH':
        return new vscode.ThemeIcon('bug', new vscode.ThemeColor('errorForeground'));
      case 'MEDIUM':
        return new vscode.ThemeIcon('alert', new vscode.ThemeColor('editorWarning.foreground'));
      default:
        return new vscode.ThemeIcon('circle-outline');
    }
  }
}

export class FindingsTreeProvider implements vscode.TreeDataProvider<FindingTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<FindingTreeItem | undefined | null | void> =
    new vscode.EventEmitter<FindingTreeItem | undefined | null | void>();
  readonly onDidChangeTreeData: vscode.Event<FindingTreeItem | undefined | null | void> =
    this._onDidChangeTreeData.event;

  private findings: Finding[] = [];

  public setFindings(findings: Finding[]): void {
    this.findings = findings;
    this._onDidChangeTreeData.fire();
  }

  public getFindings(): Finding[] {
    return this.findings;
  }

  getTreeItem(element: FindingTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: FindingTreeItem): Thenable<FindingTreeItem[]> {
    if (!element) {
      // Top level: Groups by Severity
      const severities: SeverityLevel[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
      const groups: FindingTreeItem[] = [];

      for (const sev of severities) {
        const count = this.findings.filter((f) => f.severity === sev).length;
        if (count > 0) {
          groups.push(
            new FindingTreeItem(
              `${sev} (${count})`,
              vscode.TreeItemCollapsibleState.Expanded,
              undefined,
              true,
              sev
            )
          );
        }
      }

      if (groups.length === 0 && this.findings.length === 0) {
        return Promise.resolve([
          new FindingTreeItem(
            'No findings detected (Run Scan)',
            vscode.TreeItemCollapsibleState.None
          ),
        ]);
      }

      return Promise.resolve(groups);
    } else if (element.isGroup && element.severityGroup) {
      // Children of severity group
      const matching = this.findings.filter((f) => f.severity === element.severityGroup);
      const items = matching.map(
        (f) =>
          new FindingTreeItem(
            `${f.message}`,
            vscode.TreeItemCollapsibleState.None,
            f
          )
      );
      return Promise.resolve(items);
    }

    return Promise.resolve([]);
  }
}
