# CodeGuard AI

**A multi-language VS Code security extension for vulnerability
detection, AI-assisted remediation, and independent verification.**

> Status: Architecture and scope are now aligned for the initial MVP.
> The repository is in the documentation-and-implementation-planning
> phase: the product direction is defined, but runtime features remain to
> be built and validated.

## What it aims to do

CodeGuard AI is intended to: 1. Scan supported source code for selected
security vulnerabilities. 2. Display findings with evidence and source
locations. 3. Use an LLM to propose minimal fixes. 4. Let developers
review patches before applying them. 5. Verify changes with independent
scanners and tests in a restricted environment. 6. Reduce unnecessary
LLM calls and token use. 7. Reduce incorrect fixes by grounding AI
requests in scanner evidence and verifying results.

It cannot guarantee that every vulnerability will be found or that
passing checks proves an application is fully secure.

## Language strategy

**Initial targets:** JavaScript, TypeScript, and Python.

**Expansion candidates:** Java, C, C++, C#, Go, PHP, Ruby, Kotlin, Rust,
and other languages as suitable scanner profiles and tests are added.

Language support is delivered through scanner adapters and language
profiles. Recognizing a file extension alone does not mean that full
security analysis is supported.

## Architecture

``` text
VS Code Extension (TypeScript)
          |
          v
Workspace / Language Detection
          |
          v
Scanner Adapters
(Semgrep + language-specific tools + Gitleaks)
          |
          v
Normalized Findings
          |
          v
Minimal Context -> LLM Patch Proposal
          |
          v
User Diff Review
          |
          v
Restricted Verification + Rescan + Tests
          |
          v
Verified / Rejected / Needs Review
```

Jev is optional and must not be a core dependency until its current API,
capabilities, terms, and cost have been verified.

## Planned technology stack

-   TypeScript and VS Code Extension API
-   Node.js and npm
-   Semgrep
-   Bandit for Python
-   ESLint security rules for JavaScript/TypeScript where appropriate
-   Gitleaks for secrets
-   One code-capable LLM behind an adapter
-   Docker for restricted test execution
-   Git and optional SQLite scan history
-   Optional Jev integration after evaluation

## Planned repository layout

``` text
codeguard-ai/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── DESIGN.md
├── MEMORY.md
├── package.json
├── tsconfig.json
├── .env.example
├── src/extension.ts
├── backend/
│   ├── pyproject.toml
│   └── codeguard/
│       ├── orchestrator.py
│       ├── language_detection.py
│       ├── findings.py
│       ├── context_builder.py
│       ├── patching.py
│       ├── verification.py
│       └── scanners/
└── tests/
```

## Roadmap

-   [ ] Create and run the TypeScript VS Code extension scaffold.
-   [ ] Implement workspace/current-file scan commands.
-   [ ] Integrate Semgrep and normalize findings.
-   [ ] Add JavaScript/TypeScript and Python profiles.
-   [ ] Display findings in the sidebar and editor diagnostics.
-   [ ] Integrate one LLM for patch proposals.
-   [ ] Add diff review and explicit approval.
-   [ ] Add restricted verification, tests, and rescanning.
-   [ ] Measure token use, latency, and fix outcomes.
-   [ ] Evaluate optional Jev integration.
-   [ ] Add further languages incrementally.

## Development direction

1.  Install Node.js LTS and npm.
2.  Scaffold a TypeScript VS Code extension.
3.  Build the scanner adapter interface.
4.  Integrate one scanner and display results.
5.  Add language profiles after the first end-to-end scan works.
6.  Add LLM patch proposals and verification only after scanning is
    reliable.

## Safety and privacy

-   Never commit `.env`, API keys, or tokens.
-   Use `.env.example` only for placeholder values.
-   Do not send private source code to external services without
    explicit configuration and consent.
-   Treat source code and model output as untrusted.
-   Do not execute generated code directly on the host.
-   Use restricted containers with no network by default for untrusted
    tests.
-   Do not mount the host Docker socket or sensitive host paths.
-   Require review before applying patches.
-   Do not auto-commit, push, or deploy changes.

## Verification terminology

-   **Verified:** All configured required checks passed for the tested
    scope.
-   **Rejected:** A required check failed or a blocking condition was
    found.
-   **Needs Review:** Required checks were unavailable, inconclusive, or
    contradictory.

"Verified" is not a guarantee that the entire application is secure.

## Evaluation plan

Use documented test fixtures with known findings and expected outcomes.
Compare the optimized workflow with a baseline using the same models and
cases.

Measure: - Precision and recall. - Successful fix rate. - Regression
rate. - Verification pass rate. - Input/output tokens per verified
fix. - Latency and cost where measurable. - Coverage by language and
scanner profile.

Record tool, rule, and model versions so experiments can be reproduced.

## Documentation

-   [Product Requirements](PRD.md)
-   [Architecture](ARCHITECTURE.md)
-   [Technical and UX Design](DESIGN.md)
-   [Project Memory and Agent Instructions](MEMORY.md)

## License

No license has been selected yet. Choose a license before publishing or
accepting external contributions.
