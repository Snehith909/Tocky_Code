/**
 * GitHub Copilot / VS Code Language Model Provider for Tocky Code.
 * Uses the built-in VS Code Language Model API to generate fixes without external API keys.
 */

import * as vscode from 'vscode';
import { Finding, PatchProposal } from './types';

export class CopilotProvider {
  private static readonly MODEL_SELECTOR: vscode.LanguageModelChatSelector = {
    vendor: 'copilot',
    family: 'gpt-4o'
  };

  /**
   * Check if Copilot or any language model is available
   */
  public static async isAvailable(): Promise<boolean> {
    try {
      const models = await vscode.lm.selectChatModels(CopilotProvider.MODEL_SELECTOR);
      return models.length > 0;
    } catch {
      return false;
    }
  }

  /**
   * Get available model info for display
   */
  public static async getModelInfo(): Promise<string> {
    try {
      const models = await vscode.lm.selectChatModels(CopilotProvider.MODEL_SELECTOR);
      if (models.length > 0) {
        const model = models[0];
        return `${model.vendor}/${model.family} (${model.name})`;
      }
      return 'No model available';
    } catch {
      return 'Language Model API not available';
    }
  }

  /**
   * Generate a security fix using Copilot/VS Code Language Model
   */
  public static async generateFix(
    finding: Finding,
    fileContent: string,
    workspaceRoot: string
  ): Promise<PatchProposal> {
    const startTime = Date.now();

    try {
      // Select the best available model
      const models = await vscode.lm.selectChatModels(CopilotProvider.MODEL_SELECTOR);
      if (models.length === 0) {
        throw new Error('No language model available. Please ensure GitHub Copilot is installed and activated.');
      }

      const model = models[0];

      // Build context-aware prompt
      const prompt = CopilotProvider.buildSecurityPrompt(finding, fileContent);

      // Create chat messages
      const messages = [
        vscode.LanguageModelChatMessage.User(prompt)
      ];

      // Send request to language model
      const response = await model.sendRequest(messages, {}, new vscode.CancellationTokenSource().token);

      // Collect the response
      let fullResponse = '';
      for await (const fragment of response.text) {
        fullResponse += fragment;
      }

      // Parse the response
      const parsed = CopilotProvider.parseResponse(fullResponse, finding, fileContent);

      const latency = Date.now() - startTime;

      return {
        id: `PATCH-${finding.id}`,
        finding_id: finding.id,
        target_file: finding.file,
        diff: parsed.diff,
        explanation: parsed.explanation,
        provider: 'copilot',
        model: `${model.vendor}/${model.family}`,
        status: 'AWAITING_REVIEW',
        approved_by_user: false,
        verification_status: 'NOT_RUN',
        original_snippet: parsed.original,
        replacement_snippet: parsed.replacement,
        start_line: finding.start_line,
        end_line: finding.end_line,
        tokens_used: {
          prompt_tokens: 0, // VS Code API doesn't expose token counts
          completion_tokens: 0,
          total_tokens: 0
        },
        latency_ms: latency
      };

    } catch (error: any) {
      throw new Error(`Copilot fix generation failed: ${error.message}`);
    }
  }

  /**
   * Build a security-focused prompt for the language model
   */
  private static buildSecurityPrompt(finding: Finding, fileContent: string): string {
    const lines = fileContent.split('\n');
    const startIdx = Math.max(0, finding.start_line - 6);
    const endIdx = Math.min(lines.length, finding.end_line + 5);
    const contextLines = lines.slice(startIdx, endIdx);
    const context = contextLines.join('\n');

    return `You are a security code fix assistant. A vulnerability has been detected:

**Vulnerability Details:**
- Rule: ${finding.rule_id}
- Severity: ${finding.severity}
- Tool: ${finding.tool}
- File: ${finding.file}
- Lines: ${finding.start_line}-${finding.end_line}
- Message: ${finding.message}
${finding.cwe ? `- CWE: ${finding.cwe}` : ''}

**Vulnerable Code (lines ${startIdx + 1}-${endIdx}):**
\`\`\`
${context}
\`\`\`

**Instructions:**
1. Provide a MINIMAL, secure fix for ONLY the vulnerable code
2. Preserve exact indentation and code style
3. Do NOT rewrite unrelated code
4. Explain the security improvement briefly

**Response Format (JSON):**
\`\`\`json
{
  "original_code": "the exact vulnerable code snippet to replace",
  "fixed_code": "the secure replacement code",
  "explanation": "brief explanation of what was fixed and why it's secure"
}
\`\`\`

Respond ONLY with the JSON object, no additional text.`;
  }

  /**
   * Parse the language model response and generate a diff
   */
  private static parseResponse(
    response: string,
    finding: Finding,
    fileContent: string
  ): { diff: string; explanation: string; original: string; replacement: string } {
    try {
      // Extract JSON from response (handle markdown code blocks)
      let jsonStr = response.trim();
      
      // Remove markdown code blocks if present
      const jsonMatch = jsonStr.match(/```(?:json)?\s*(\{[\s\S]*\})\s*```/);
      if (jsonMatch) {
        jsonStr = jsonMatch[1];
      }

      const parsed = JSON.parse(jsonStr);
      const original = parsed.original_code || finding.evidence;
      const replacement = parsed.fixed_code || original;
      const explanation = parsed.explanation || 'Security fix applied via Copilot';

      // Generate unified diff
      const modifiedContent = fileContent.replace(original, replacement);
      const diff = CopilotProvider.generateUnifiedDiff(fileContent, modifiedContent, finding.file);

      return {
        diff,
        explanation: `${explanation} (Generated via GitHub Copilot)`,
        original,
        replacement
      };

    } catch (error) {
      // Fallback: treat entire response as explanation
      return {
        diff: `--- a/${finding.file}\n+++ b/${finding.file}\n@@ -${finding.start_line},1 +${finding.start_line},1 @@\n-${finding.evidence}\n+// [Copilot] Manual review needed\n`,
        explanation: `Copilot response: ${response.substring(0, 200)}... (Please review manually)`,
        original: finding.evidence,
        replacement: '// [Copilot] Manual review needed'
      };
    }
  }

  /**
   * Generate a simple unified diff format
   */
  private static generateUnifiedDiff(original: string, modified: string, filename: string): string {
    if (original === modified) {
      return `No changes needed for ${filename}`;
    }

    const originalLines = original.split('\n');
    const modifiedLines = modified.split('\n');

    // Find first and last difference
    let firstDiff = 0;
    let lastDiff = Math.max(originalLines.length, modifiedLines.length);

    for (let i = 0; i < Math.min(originalLines.length, modifiedLines.length); i++) {
      if (originalLines[i] !== modifiedLines[i]) {
        firstDiff = i;
        break;
      }
    }

    let diff = `--- a/${filename}\n+++ b/${filename}\n`;
    diff += `@@ -${firstDiff + 1},${originalLines.length - firstDiff} +${firstDiff + 1},${modifiedLines.length - firstDiff} @@\n`;

    // Show context and changes
    const contextStart = Math.max(0, firstDiff - 2);
    const contextEnd = Math.min(originalLines.length, firstDiff + 10);

    for (let i = contextStart; i < contextEnd; i++) {
      if (i < originalLines.length && originalLines[i] !== modifiedLines[i]) {
        diff += `-${originalLines[i]}\n`;
        if (i < modifiedLines.length) {
          diff += `+${modifiedLines[i]}\n`;
        }
      } else if (i < originalLines.length) {
        diff += ` ${originalLines[i]}\n`;
      }
    }

    return diff;
  }

  /**
   * Ask user if they want to use Copilot when no API key is configured
   */
  public static async promptToUseCopilot(): Promise<boolean> {
    const isAvail = await CopilotProvider.isAvailable();
    
    if (!isAvail) {
      return false;
    }

    const choice = await vscode.window.showInformationMessage(
      '🤖 GitHub Copilot is available! Use it to generate security fixes without an API key?',
      'Yes, Use Copilot',
      'No, Configure API Key'
    );

    return choice === 'Yes, Use Copilot';
  }
}
