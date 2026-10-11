/**
 * Type definitions for CodeGuard AI VS Code extension.
 * Aligned with backend data models.
 */

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingStatus =
  | 'OPEN'
  | 'PATCH_PROPOSED'
  | 'AWAITING_REVIEW'
  | 'APPROVED'
  | 'REJECTED_BY_USER'
  | 'VERIFICATION_RUNNING'
  | 'VERIFIED'
  | 'REJECTED'
  | 'NEEDS_REVIEW'
  | 'NOT_RUN';

export interface Finding {
  id: string;
  tool: string;
  rule_id: string;
  language: string;
  file: string;
  start_line: number;
  end_line: number;
  severity: SeverityLevel;
  message: string;
  evidence: string;
  fingerprint: string;
  status: FindingStatus;
  start_col?: number;
  end_col?: number;
  cwe?: string;
  help_uri?: string;
  confidence?: string;
}

export interface PatchProposal {
  id: string;
  finding_id: string;
  target_file: string;
  diff: string;
  explanation: string;
  provider: string;
  model: string;
  status: FindingStatus;
  approved_by_user: boolean;
  verification_status: FindingStatus;
  original_snippet: string;
  replacement_snippet: string;
  start_line: number;
  end_line: number;
  tokens_used: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  latency_ms: number;
}

export interface VerificationCheck {
  name: string;
  check_type: string;
  passed: boolean;
  details: string;
  duration_ms: number;
}

export interface VerificationResult {
  patch_id: string;
  finding_id: string;
  status: 'VERIFIED' | 'REJECTED' | 'NEEDS_REVIEW';
  rescan_passed: boolean;
  tests_passed: boolean;
  tests_run: boolean;
  details: string;
  checks_executed: VerificationCheck[];
  elapsed_seconds: number;
}

export interface ScanSummary {
  workspace_path: string;
  total_findings: number;
  by_severity: Record<string, number>;
  by_tool: Record<string, number>;
  scanners_run: string[];
  scanners_unavailable: string[];
  languages_detected: string[];
  duration_ms: number;
  findings: Finding[];
}

export interface CodeGuardMetrics {
  total_scans: number;
  total_findings: number;
  total_patches: number;
  verified_fixes: number;
  rejected_patches: number;
  needs_review: number;
  tokens: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_baseline_tokens: number;
    tokens_saved: number;
    token_reduction_pct: number;
  };
  average_latency_ms: number;
}
