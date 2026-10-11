# Product Requirements Document --- CodeGuard AI

**Product:** CodeGuard AI (working title)\
**Product type:** Multi-language VS Code security extension\
**Status:** MVP requirements and architecture confirmed; implementation is in progress

## 1. Summary

CodeGuard AI is a VS Code plugin designed to scan source code across
multiple programming languages, identify selected security
vulnerabilities, use an LLM to propose minimal fixes, and independently
verify patches with scanners and tests. The product aims to reduce
unnecessary LLM calls and token use, while reducing hallucination-driven
changes through evidence-based prompts and independent checks.

## 2. Problem statement

AI coding agents can generate code in many languages quickly, but
generated code may contain vulnerabilities, unsafe patterns, exposed
secrets, or regressions. Developers need to inspect code, understand
scanner output, fix issues, and verify the changes. Whole-repository LLM
prompts can waste tokens and may lead to unsupported or incorrect fixes.

## 3. Target users

-   Developers using AI coding assistants.
-   Students learning secure software engineering.
-   Small teams seeking an additional security check in VS Code.
-   Evaluators researching token-efficient AI-assisted remediation.

## 4. Goals

1.  Provide a multi-language architecture using scanner adapters.
2.  Start implementation with JavaScript, TypeScript, and Python.
3.  Detect selected vulnerabilities and show evidence with file/line
    locations.
4.  Generate minimal fix proposals using a code-capable LLM.
5.  Verify fixes with independent scans and relevant tests in an
    isolated environment.
6.  Reduce LLM token consumption through local scanning, context
    minimization, caching, and bounded retries.
7.  Reduce incorrect fixes through evidence-grounded prompts and
    verification.
8.  Measure detection, remediation, token use, latency, and regressions.

## 5. Non-goals

-   Detecting every vulnerability in every language.
-   Claiming a repository is completely secure.
-   Supporting every language in the first release.
-   Automatically merging, pushing, or deploying changes.
-   Running untrusted code directly on the host.
-   Training a foundation model.
-   Requiring Jev before its API and measurable value are established.

## 6. Language rollout

### Initial implementation targets

-   JavaScript
-   TypeScript
-   Python

### Later candidates

Java, C, C++, C#, Go, PHP, Ruby, Kotlin, Rust, and other languages based
on scanner availability, team capacity, and test coverage.

Language support is profile-based. A language is not considered
supported merely because a file extension is recognized; the product
must have an appropriate scanner configuration and documented
limitations for that language.

## 7. MVP scope

### In scope

-   VS Code extension written in TypeScript.
-   Scan current file and workspace.
-   Language and project-profile detection.
-   Scanner adapter interface.
-   Semgrep integration as the cross-language starting point.
-   Bandit for Python; ESLint security rules for JavaScript/TypeScript
    where appropriate.
-   Gitleaks for secret detection, if installed/configured.
-   Normalized findings and severity/file/line display.
-   One configurable code-capable LLM for patch proposals.
-   Diff review and explicit user approval.
-   Verification using security rescans and relevant tests.
-   Docker-based restricted execution where configured.
-   `VERIFIED`, `REJECTED`, and `NEEDS_REVIEW` outcomes.
-   Token/latency metrics where available.
-   Jev as optional, pending verification of API and capabilities.

### Later scope

-   More language profiles.
-   Deeper IDE diagnostics and code actions.
-   Direct coding-agent integrations where supported by public APIs.
-   Rich scan history and team reporting.

## 8. User stories

1.  As a developer, I want to scan the current file or workspace for
    supported vulnerabilities.
2.  As a developer, I want findings to show the tool, rule, severity,
    location, and evidence.
3.  As a developer, I want unsupported languages or unavailable scanners
    to be clearly reported.
4.  As a developer, I want a concise fix proposal based on the finding
    and relevant code.
5.  As a developer, I want to review a diff before it changes my files.
6.  As a developer, I want fixes checked with independent scanners and
    relevant tests.
7.  As a developer, I want inconclusive verification to be labelled
    honestly.
8.  As a developer, I want to see token usage and elapsed time.
9.  As a developer, I want source code and secrets handled with care.
10. As an evaluator, I want repeatable tests to compare the optimized
    system with a baseline.

## 9. Functional requirements

### FR-1: Workspace and language detection

Detect file languages and relevant project manifests. Support
mixed-language workspaces.

### FR-2: Scanner adapters

Use a common interface to run scanners and parse machine-readable
output. Adapters must report availability and incomplete scans.

### FR-3: Finding normalization

Normalize tool, rule ID, file, line range, severity, message, evidence,
fingerprint, and status without losing source-tool details.

### FR-4: Triage

Prioritize findings with transparent rules. An optional AI/ Jev layer
may provide a recommendation but must not silently remove raw findings.

### FR-5: Context minimization

Send only the finding, necessary code, and required context to the LLM
by default. Redact secrets and require explicit configuration before
sending private code to an external service.

### FR-6: Patch generation

Generate a minimal patch in a structured format. Validate its syntax,
paths, and permitted scope.

### FR-7: User approval

Show a diff and require approval before modifying files by default.

### FR-8: Verification

Run configured rescans, builds, and tests in an isolated environment. If
required checks do not run or evidence is inconclusive, do not report
`VERIFIED`.

### FR-9: Reporting

Show findings, patch details, checks run, verification state,
limitations, elapsed time, and token usage where available.

### FR-10: Metrics and caching

Record usage and latency. Cache results only with keys that include
relevant content, tool/rule versions, and configuration.

### FR-11: Optional Jev integration

Integrate Jev only after validating current API access, supported tasks,
terms, privacy, and cost. Core scan/fix/verify workflows must not depend
on Jev.

## 10. Non-functional requirements

-   Safety: never execute untrusted code directly on the host.
-   Privacy: external source-code transfer must be explicit and
    configurable.
-   Reliability: incomplete checks are clearly identified.
-   Traceability: record findings, proposed patches, checks, and
    outcomes.
-   Performance: use local scanners before LLM calls and avoid
    unnecessary re-analysis.
-   Extensibility: add languages through profiles and scanner adapters.
-   Usability: provide actionable findings and reviewable diffs.
-   Portability: support the VS Code environments and runtimes declared
    by the extension manifest.

## 11. Metrics

-   Precision and recall on documented test fixtures.
-   Number of known vulnerabilities fixed successfully.
-   Patch verification pass rate.
-   Regression rate.
-   False-positive rate.
-   Token use per verified fix.
-   Token reduction against a baseline using the same cases and model.
-   Median/p95 latency.
-   Cost per verified fix where provider usage/pricing data is
    available.
-   Coverage by language and scanner profile.

## 12. Acceptance criteria

The first MVP is acceptable when: 1. The VS Code extension can scan a
workspace using at least one cross-language scanner. 2. JavaScript,
TypeScript, and Python are recognized and routed to configured profiles.
3. Findings appear in a consistent UI with file and line locations. 4.
The system can produce a patch proposal for at least one supported
finding. 5. The user can review and approve the diff. 6. The system can
run configured checks in a restricted environment. 7. It never reports
success if a required check did not run. 8. Token/latency metrics are
recorded where available. 9. Tests and docs state the limitations of
supported languages and rules.

## 13. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Different languages need different  Scanner adapters and language
  tools                               profiles

  Scanner coverage is incomplete      Document coverage; combine scanners
                                      and tests

  LLM introduces regressions          Minimal patches, approval, rescan,
                                      tests

  Token savings are unproven          Measure against a baseline

  Sandbox is weakly configured        Least privilege, resource limits,
                                      no network by default

  Private source leaks                Explicit provider configuration,
                                      redaction, consent

  Jev is unsuitable/unavailable       Keep optional and benchmark it

  Too much scope for a mini-project   Implement JS/TS/Python first and
                                      expand only after validation
  -----------------------------------------------------------------------

## 14. Milestones

1.  Extension scaffold and workspace scanning.
2.  Semgrep adapter and finding UI.
3.  Python and JavaScript/TypeScript scanner profiles.
4.  LLM patch proposals and diff review.
5.  Restricted verification, rescans, and tests.
6.  Token optimization and baseline evaluation.
7.  Optional Jev experiment.
8.  Additional languages and deeper VS Code integration.
