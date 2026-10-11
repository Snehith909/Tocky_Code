# CodeGuard AI --- Technical and UX Design

## 1. Product experience

CodeGuard AI is a TypeScript-based VS Code extension. It provides a
sidebar for findings and reports, editor diagnostics for supported
findings, and a review flow for proposed patches.

The current product direction is locked for a TypeScript extension with a
Python-backed orchestration layer or local process boundary, with the
initial language targets set to JavaScript, TypeScript, and Python.

### Design principles

-   Show scanner evidence and preserve original tool findings.
-   Do not rely on color alone; include severity labels and icons.
-   Review code changes before applying them.
-   Distinguish `VERIFIED`, `REJECTED`, and `NEEDS_REVIEW`.
-   Show which scanners and tests ran.
-   Never imply that the entire repository is secure because selected
    checks passed.

## 2. Main user flow

1.  Developer opens a workspace.
2.  Extension identifies file languages and project profiles.
3.  Developer selects **Scan Workspace** or **Scan Current File**.
4.  Scanner adapters run configured tools.
5.  Findings appear in the CodeGuard sidebar and VS Code diagnostics.
6.  Developer selects a finding and chooses **Explain** or **Propose
    Fix**.
7.  Backend builds a minimal, redacted context and calls the configured
    LLM.
8.  Proposed patch opens in a diff view.
9.  Developer approves or rejects the patch.
10. Verification runs in a temporary restricted environment.
11. Results are displayed and metrics recorded.

## 3. Sidebar layout (concept)

``` text
CODEGUARD AI
--------------------------------
Workspace: my-project
Languages: TypeScript, Python

[ Scan Workspace ] [ Scan File ]

FINDINGS (7)
  HIGH (2)
    SQL injection
      src/db.ts:42
    Exposed secret
      .env.example:12

  MEDIUM (3)
    Unsafe subprocess
      tools/run.py:18

  LOW (2)
    ...

SELECTED FINDING
  Tool: Semgrep
  Rule: <original-rule-id>
  Location: src/db.ts:42
  Evidence: <redacted excerpt>

  [Explain] [Propose Fix] [Open Source]
--------------------------------
LAST VERIFICATION
  State: NEEDS REVIEW
  Security rescan: Passed
  Tests: Not Run
  [View Report]
```

This is a conceptual layout; counts and findings above are sample data.

## 4. Proposed commands

-   `CodeGuard: Scan Workspace`
-   `CodeGuard: Scan Current File`
-   `CodeGuard: Explain Finding`
-   `CodeGuard: Propose Fix`
-   `CodeGuard: Verify Patch`
-   `CodeGuard: Open Latest Report`
-   `CodeGuard: Show Metrics`

## 5. Extension and backend boundary

The TypeScript extension handles: - VS Code commands, sidebar,
diagnostics, progress, cancellation, and diff view. - Workspace
selection and user approval. - Displaying findings and verification
status.

The backend/scanner layer handles: - Scanner execution and parsing. -
Finding normalization and triage. - Context building and secret
redaction. - LLM provider calls. - Patch validation. - Test
orchestration and verification. - Metrics and local persistence.

For the earliest prototype, a local process or CLI can be simpler than a
long-running API service. Add FastAPI only if a stable service boundary
is beneficial.

## 6. Common finding schema

``` json
{
  "id": "FINDING-001",
  "tool": "semgrep",
  "rule_id": "example-rule",
  "language": "typescript",
  "file": "src/db.ts",
  "start_line": 42,
  "end_line": 43,
  "severity": "HIGH",
  "message": "Potential unsafe query construction",
  "evidence": "Redacted code excerpt",
  "status": "OPEN"
}
```

Example only; real scanner rule IDs and severity mappings must be
preserved.

## 7. Patch proposal schema

``` json
{
  "id": "PATCH-001",
  "finding_id": "FINDING-001",
  "provider": "configured-llm",
  "diff": "unified diff",
  "explanation": "Use a parameterized query.",
  "status": "AWAITING_REVIEW",
  "approved_by_user": false,
  "verification_status": "NOT_RUN"
}
```

## 8. Verification state machine

``` text
OPEN
  |
  v
PATCH_PROPOSED
  |
  v
AWAITING_REVIEW
  |             \
  v              v
APPROVED       REJECTED_BY_USER
  |
  v
VERIFICATION_RUNNING
  |          |            |
  v          v            v
VERIFIED   REJECTED    NEEDS_REVIEW
```

-   `VERIFIED`: all configured required checks passed for the stated
    scope.
-   `REJECTED`: a required check failed or a blocking condition
    occurred.
-   `NEEDS_REVIEW`: checks are missing, inconclusive, or contradictory.
-   `NOT_RUN`: verification has not started.

## 9. Multi-language routing

Use VS Code's language IDs for editor documents and inspect project
manifests for workspace-level routing. Use adapters for scanners and
test runners.

Initial profiles: - JavaScript / TypeScript: Semgrep and configured
ESLint security rules; run project tests/build only when safely and
correctly configured. - Python: Semgrep and Bandit; use project test
command when known. - Secrets: Gitleaks across repository files where
configured.

Later profiles can add Java, C/C++, C#, Go, PHP, Ruby, Kotlin, Rust, and
other languages. A profile must document its tools and known coverage
limits.

## 10. Token optimization UX

Show token usage when available from the provider. Include: - Calls
made. - Input/output tokens. - Retry count. - Approximate or reported
cost, clearly labelled. - Files/findings included in context. - Cache
hit/miss where applicable.

Optimization methods: - Scanner-first processing. - Changed-file
prioritization. - Minimal relevant context. - Secret redaction. -
Structured patch outputs. - Safe cache invalidation. - Bounded retries.

## 11. Error and empty states

  -----------------------------------------------------------------------
  Condition                           Message
  ----------------------------------- -----------------------------------
  No supported files                  "No files matched configured
                                      language profiles."

  Scanner missing                     "Scan incomplete: required scanner
                                      is unavailable."

  No findings                         "No findings from the configured
                                      checks; this is not a guarantee of
                                      security."

  LLM unavailable                     "Findings are available, but fix
                                      generation could not run."

  Patch scope violation               "Patch rejected because it changes
                                      files outside the approved scope."

  Sandbox timeout                     "Verification inconclusive; review
                                      required."

  Tests not configured                "Tests not run; verification is
                                      incomplete."

  Jev unavailable                     "Optional Jev analysis skipped;
                                      deterministic triage continued."
  -----------------------------------------------------------------------

## 12. Privacy and safety UX

-   Clearly disclose when source code will be sent to an external model.
-   Redact secrets before context construction.
-   Show a diff and require explicit approval before applying patches.
-   Execute untrusted code only in a restricted sandbox.
-   Disable network access by default in test containers.
-   Never claim comprehensive security from a partial scan.
