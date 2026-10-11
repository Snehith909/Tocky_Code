# CodeGuard AI --- System Architecture

**Purpose:** A multi-language VS Code security plugin that detects
vulnerabilities, helps generate fixes, independently verifies changes,
reduces unnecessary LLM calls, and measures token usage.

**Status:** Architecture is finalized for the initial MVP implementation
phase. Features remain unimplemented until they are built and validated
with tests.

## 1. Architecture principles

-   Multi-language by design; add language support through scanner
    adapters.
-   Start implementation with JavaScript, TypeScript, and Python; expand
    incrementally.
-   Run deterministic scanners before using an LLM.
-   Use minimal, redacted context for AI requests.
-   Treat repository content and model output as untrusted.
-   Require patch review and approval by default.
-   Never mark a fix verified when required checks did not run or
    results are inconclusive.
-   Keep Jev optional until its actual API, supported capabilities,
    terms, and cost are confirmed.

## 2. High-level architecture

``` text
                       VS Code Extension
                    (TypeScript / Extension API)
                              |
                 Commands, Sidebar, Diagnostics,
                   Diff Review, Status, Metrics
                              |
                         Extension Host
                              |
                    Backend / Scanner Adapters
                              |
                 Workspace + Language Detection
                              |
                    Scan Orchestration Layer
            +-----------------+------------------+
            |                 |                  |
      Semgrep adapter   Language-specific    Secret scanner
                         scanners/builders      (Gitleaks)
            |                 |                  |
            +-----------------+------------------+
                              |
                    Finding Normalization
                              |
                    Triage / Deduplication
                 (rules first; Jev optional)
                              |
                     Context Minimization
                              |
                        LLM Provider
                       Patch Proposal
                              |
                     Patch Scope Validator
                              |
                     User Review / Approval
                              |
                 Isolated Verification Runner
                  +-----------+------------+
                  |                        |
             Security rescan          Build / tests
                  |                        |
                  +-----------+------------+
                              |
                    Verification Evaluator
                              |
              Verified / Rejected / Needs Review
                              |
                 Findings, Reports, Metrics
```

## 3. Technology choices

  -----------------------------------------------------------------------
  Layer                               Initial choice
  ----------------------------------- -----------------------------------
  VS Code extension                   TypeScript, VS Code Extension API

  Extension packaging                 `npm`, `vsce`

  Backend                             Python service or local process,
                                      chosen after MVP spike

  Multi-language scanner              Semgrep

  Python-specific scanner             Bandit

  JavaScript/TypeScript               Semgrep plus appropriate ESLint
                                      security rules

  Java                                Semgrep; add SpotBugs where
                                      suitable

  C/C++                               Semgrep and Cppcheck

  Go                                  Semgrep and Gosec

  PHP                                 Semgrep and
                                      PHPStan/security-specific tooling

  Ruby                                Semgrep and Brakeman

  .NET / C#                           Semgrep and .NET analyzers

  Secrets                             Gitleaks

  Dependencies                        Ecosystem-specific lockfile
                                      scanners, added by ecosystem

  Patch generation                    One code-capable LLM behind a
                                      provider adapter

  Optional decision layer             Jev, if validated and useful

  Verification isolation              Docker with restrictive
                                      configuration

  Local persistence                   SQLite, only if scan history is
                                      needed

  Version/diff support                Git
  -----------------------------------------------------------------------

Tool capabilities vary by language and rule. The list is a candidate
stack, not a promise that every tool detects every vulnerability.

## 4. Multi-language support strategy

### 4.1 Language detection

Use VS Code document language IDs, file extensions, and project
manifests. For workspace scans, inspect known manifests and source
files. Do not infer that a whole repository is one language; monorepos
may contain several.

### 4.2 Scanner adapter interface

Every scanner adapter should expose a common contract such as: -
`name` - `supported_languages` - `is_available()` -
`scan(target, config) -> ScanResult` -
`parse_output(raw_output) -> list[Finding]`

Adapters must preserve the original tool name, rule ID, severity, file,
line range, and evidence where available.

### 4.3 Language profiles

A language profile maps languages and project types to scanners, tests,
and build commands. The first profiles are: 1. JavaScript / TypeScript
2. Python 3. Other languages added after tests exist for that profile.

Do not run a language-specific command if the relevant tool or runtime
is absent. Report `Not Run` or `Scan Incomplete`.

## 5. Main components

### VS Code extension

-   Commands: Scan Workspace, Scan File, Explain Finding, Generate Fix
    Proposal, Verify Patch, Show Report.
-   Sidebar: findings grouped by severity and file.
-   Diagnostics: optional editor squiggles and code-lens actions.
-   Diff view: review proposed patches before application.
-   Status panel: checks run, token usage when available, elapsed time,
    and verification state.
-   Do not silently overwrite files.

### Scan orchestrator

-   Selects scanners based on language profiles and installed tools.
-   Runs tools with timeouts and resource limits.
-   Captures versions, exit codes, stdout/stderr, and scan completeness.
-   Supports workspace and changed-file scans.

### Finding normalizer

Common fields: - `id`, `tool`, `rule_id`, `file`, `start_line`,
`end_line` - `severity`, `message`, `evidence`, `fingerprint`,
`status` - optional `cwe`, `help_uri`, and confidence only when supplied
or transparently derived.

### Triage and Jev

-   Use transparent deterministic prioritization first.
-   Jev may be tested for bounded classification/triage only after its
    current capabilities and API are confirmed.
-   Never allow model triage to silently erase raw scanner findings.

### Context minimizer

-   Include finding evidence, affected code, relevant surrounding
    context, and necessary tests/call sites.
-   Avoid sending the entire repository by default.
-   Redact secrets.
-   Ask for explicit configuration/consent before sending proprietary
    source to an external provider.
-   Record prompt/completion token usage when the provider exposes it.

### LLM and patch handling

-   Use a provider adapter so the model provider can be changed.
-   Request a unified diff or validated structured patch.
-   Validate paths and ensure the patch only affects approved workspace
    files.
-   Run syntax/format checks appropriate to the language.
-   Require user approval by default and support rollback.

### Verification runner

-   Use a temporary working copy or worktree.
-   Execute generated code and tests only in an isolated environment.
-   Use non-root containers, limited capabilities, CPU/memory/PID
    limits, timeouts, restricted mounts, and network disabled by
    default.
-   Never mount the host Docker socket or sensitive host directories.
-   Docker is a useful isolation layer, not an absolute security
    guarantee.

### Verification evaluator

A patch may be `VERIFIED` only when all configured required checks for
the scope passed. The evaluator should check: 1. Patch applies only to
approved paths. 2. Relevant scanner no longer reports the original
issue, or a documented human review resolves ambiguity. 3. No new
blocking findings appear in the scanned scope. 4. Relevant build/tests
pass. 5. Required checks actually ran.

Use `NEEDS_REVIEW` if a required tool/test is unavailable, results
conflict, or evidence is insufficient. A pass does not prove the whole
application is secure.

## 6. Suggested repository layout

``` text
codeguard-ai/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── DESIGN.md
├── MEMORY.md
├── .env.example
├── package.json
├── tsconfig.json
├── src/
│   └── extension.ts
├── media/
├── backend/
│   ├── pyproject.toml
│   └── codeguard/
│       ├── cli.py
│       ├── models.py
│       ├── language_detection.py
│       ├── orchestrator.py
│       ├── findings.py
│       ├── triage.py
│       ├── context_builder.py
│       ├── patching.py
│       ├── verification.py
│       ├── sandbox.py
│       ├── storage.py
│       └── scanners/
│           ├── base.py
│           ├── semgrep.py
│           ├── bandit.py
│           ├── eslint.py
│           └── gitleaks.py
└── tests/
    ├── fixtures/
    ├── extension/
    ├── scanners/
    ├── patching/
    └── verification/
```

The backend may later be split into a service if extension-host
constraints or integration tests justify it. Keep the first prototype as
simple as possible.

## 7. End-to-end data flow

1.  User selects a file or workspace.
2.  Extension detects relevant languages and project profiles.
3.  Orchestrator selects available scanners.
4.  Scanners run and emit machine-readable findings.
5.  Normalizer creates common finding objects.
6.  Triage ranks findings without deleting original results.
7.  Context builder prepares minimal redacted context.
8.  LLM proposes a patch.
9.  Patch validator checks paths, format, and scope.
10. User reviews and approves.
11. Verification runner applies the patch to a temporary copy.
12. Appropriate scanners and tests run in isolation.
13. Evaluator returns `VERIFIED`, `REJECTED`, or `NEEDS_REVIEW`.
14. Extension displays the report and records metrics.

## 8. Token and reliability optimization

-   Scan locally before calling an LLM.
-   Prefer changed-file scans where safe; use dependency and
    configuration changes to invalidate affected results.
-   Cache scanner results keyed by content, tool/rule versions, and
    relevant configuration.
-   Cache only when the cache key captures all inputs that affect the
    result.
-   Use small code contexts and structured prompts.
-   Limit retries and stop repeated failed patches.
-   Record actual token usage and compare against a documented baseline.
-   Do not claim savings without measured comparisons.

## 9. Failure handling

-   Scanner missing: `SCAN INCOMPLETE`.
-   Unsupported language: explain that no suitable profile is
    configured.
-   LLM unavailable: preserve findings; do not propose a fix.
-   Invalid patch or out-of-scope file: reject patch.
-   Sandbox failure/timeout: `NEEDS_REVIEW`.
-   Test failure or new critical finding: reject or request human
    review.
-   Jev unavailable: continue using deterministic triage and record the
    fallback.

## 10. Security and privacy

-   Never commit secrets or `.env` files.
-   Treat repository content, comments, documentation, fixtures, and
    model output as untrusted.
-   Protect against prompt injection embedded in source code.
-   Do not execute generated code on the host.
-   Disable sandbox networking by default.
-   Ask before sending source code to a hosted model.
-   Do not auto-commit, push, or deploy patches.
-   Keep an audit trail of changes and checks.

## 11. Non-goals for initial release

-   Guaranteeing zero vulnerabilities.
-   Supporting all languages at launch.
-   Autonomous merging/deployment.
-   Replacing a professional security audit.
-   Training a foundation model.
-   Making Jev mandatory before its value is demonstrated.
