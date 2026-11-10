/**
 * Subprocess bridge to invoke CodeGuard AI Python backend CLI.
 */

import * as cp from 'child_process';
import * as path from 'path';
import * as vscode from 'vscode';
import {
  Finding,
  PatchProposal,
  VerificationResult,
  ScanSummary,
  CodeGuardMetrics,
} from './types';

export class BackendBridge {
  private extensionPath: string;

  constructor(context: vscode.ExtensionContext) {
    this.extensionPath = context.extensionPath;
  }

  private getPythonPath(): string {
    const config = vscode.workspace.getConfiguration('codeguard');
    return config.get<string>('pythonPath', 'python');
  }

  private getBackendDir(): string {
    return path.join(this.extensionPath, 'backend');
  }

  private async executeCli(args: string[]): Promise<string> {
    const pythonExe = this.getPythonPath();
    const backendDir = this.getBackendDir();
    const config = vscode.workspace.getConfiguration('codeguard');
    const apiKey = config.get<string>('apiKey', '').trim();
    const customEndpoint = config.get<string>('customLlmEndpoint', '').trim();
    const model = config.get<string>('model', '').trim();

    return new Promise((resolve, reject) => {
      const fullArgs = ['-m', 'codeguard.cli', ...args];
      const env: Record<string, string> = {
        ...process.env as Record<string, string>,
        PYTHONPATH: backendDir,
        PYTHONIOENCODING: 'utf-8',
      };

      if (apiKey) {
        env['GEMINI_API_KEY'] = apiKey;
        env['OPENAI_API_KEY'] = apiKey;
      }
      if (customEndpoint) {
        env['CODEGUARD_CUSTOM_ENDPOINT'] = customEndpoint;
      }
      if (model) {
        env['LLM_MODEL'] = model;
      }

      // Also load from workspace .env file (written by the API Key panel)
      try {
        const fs = require('fs') as typeof import('fs');
        const envFilePath = path.join(backendDir, '..', '.env');
        if (fs.existsSync(envFilePath)) {
          const envContent = fs.readFileSync(envFilePath, 'utf-8');
          for (const line of envContent.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) { continue; }
            const eqIdx = trimmed.indexOf('=');
            if (eqIdx > 0) {
              const k = trimmed.substring(0, eqIdx).trim();
              const v = trimmed.substring(eqIdx + 1).trim();
              // VS Code settings take priority over .env
              if (k && v && !env[k]) {
                env[k] = v;
              }
            }
          }
        }
      } catch (_) { /* ignore .env load errors */ }

      const proc = cp.spawn(pythonExe, fullArgs, {
        cwd: backendDir,
        env,
        shell: false,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => {
        stdout += data.toString('utf-8');
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString('utf-8');
      });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve(stdout.trim());
        } else {
          reject(new Error(`CodeGuard CLI error (exit code ${code}): ${stderr || stdout}`));
        }
      });

      proc.on('error', (err) => {
        reject(new Error(`Failed to start CodeGuard backend with "${pythonExe}": ${err.message}`));
      });
    });
  }

  public async scan(targetPath: string): Promise<ScanSummary> {
    const raw = await this.executeCli(['scan', '--target', targetPath, '--format', 'json']);
    return JSON.parse(raw) as ScanSummary;
  }

  public async proposeFix(
    workspacePath: string,
    finding: Finding,
    provider?: string
  ): Promise<PatchProposal> {
    const config = vscode.workspace.getConfiguration('codeguard');
    const selectedProvider = provider || config.get<string>('llmProvider', 'gemini');

    const raw = await this.executeCli([
      'propose-fix',
      '--workspace', workspacePath,
      '--finding-json', JSON.stringify(finding),
      '--provider', selectedProvider,
    ]);
    return JSON.parse(raw) as PatchProposal;
  }

  public async verifyPatch(
    workspacePath: string,
    finding: Finding,
    patch: PatchProposal,
    noTests: boolean = false
  ): Promise<VerificationResult> {
    const args = [
      'verify',
      '--workspace', workspacePath,
      '--finding-json', JSON.stringify(finding),
      '--patch-json', JSON.stringify(patch),
    ];
    if (noTests) {
      args.push('--no-tests');
    }

    const raw = await this.executeCli(args);
    return JSON.parse(raw) as VerificationResult;
  }

  public async getMetrics(workspacePath: string): Promise<CodeGuardMetrics> {
    const raw = await this.executeCli(['metrics', '--workspace', workspacePath]);
    return JSON.parse(raw) as CodeGuardMetrics;
  }

  public async explain(finding: Finding): Promise<any> {
    const raw = await this.executeCli([
      'explain',
      '--finding-json', JSON.stringify(finding),
    ]);
    return JSON.parse(raw);
  }
}
