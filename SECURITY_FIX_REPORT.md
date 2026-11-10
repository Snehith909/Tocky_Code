# Security Fix and Scanner Evaluation

**Evaluation date:** 2026-10-12

## Changes made

- Removed the credential-shaped value from `.env.example`; `GEMINI_API_KEY` is blank in the example. The value's validity was not tested. Revoke and rotate it if it was a real key.
- Changed the Gemini backend adapter to send API keys in the `x-goog-api-key` header rather than the URL, where they could be copied into request logs.
- Updated the Gemini backend default model from `gemini-1.5-flash` to `gemini-2.5-flash`, which is listed in Google's [Gemini API model documentation](https://ai.google.dev/gemini-api/docs/models).
- Extended the VS Code and Python backend scanners to detect the credential, SQL f-string, and `os.popen` patterns present in the supplied VulnShop fixture. Added regression tests, including a check that an interpolated SQL password is not misreported as a hardcoded credential.
- Left `requirements.zip`'s intentionally vulnerable app unchanged. It is a test fixture, not a remediated application.

## Fixture accuracy

The fixture README documents 19 planted vulnerabilities. The VS Code scanner was run against the extracted `app.py` through the extension's scanner and test harness:

| Fixture issue | Result | Location |
|---|---|---:|
| Hardcoded weak secret key | Detected | 12 |
| SQL injection in login | Detected | 85 |
| SQL injection in search | Detected | 112 |
| Command injection via `os.popen` | Detected | 150 |
| Other documented issues | Not detected | — |

| Measure | Result |
|---|---:|
| True positives | 4 |
| False positives | 0 |
| False negatives | 15 |
| Precision | 100% (4/4) |
| Recall | 21.1% (4/19) |
| F1 score | 34.8% |

These are fixture-specific results, based on matching the scanner's four findings to the fixture's documented ground truth. The rule-based scanner does not cover many issue classes in the sample, including XSS, CSRF, IDOR/access control, rate limiting, path traversal, file upload controls, open redirects, and security headers. A clean scan is not evidence that an application is secure.

The Python backend CLI also found the same four patterns using its built-in scanner. Semgrep, Bandit, and Gitleaks were unavailable in this environment, so their coverage was not measured.

## Gemini and token usage

No live Gemini request was made: the example key is blank, and the test used a mocked API response. The integration test verified that provider-reported usage is preserved as **31 prompt tokens + 12 completion tokens = 43 total tokens**. This is test data, not billable or measured usage from a real Gemini call. Real usage is recorded from Gemini's `usageMetadata` when a request succeeds.

The Python backend supports Gemini patch proposals through `codeguard propose-fix --provider gemini`. The VS Code extension currently scans locally and supports an OpenAI-compatible endpoint for optional explanations; it is not wired to the Python backend or Gemini for patch generation.

## Validation

- Python backend tests: **10 passed**, including the end-to-end scan/fix/verify test and mocked Gemini authentication/token reporting.
- VS Code extension tests: **3 passed**, including a scan of the uploaded fixture and regression coverage for Python SQL, command execution, and hardcoded secrets.
- Extension TypeScript compilation, type-check, lint, and bundle: **passed**.
- No live API call or billable LLM usage was performed.
