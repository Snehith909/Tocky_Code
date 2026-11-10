# VulnShop - Intentionally Vulnerable Test App

For testing your security plugin/scanner. **Run locally only. Never deploy publicly.**

## Run

```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

Test logins: `admin/admin123`, `alice/alice123`, `bob/bob123`

## Planted vulnerabilities

| # | Vulnerability | Where | Sample test |
|---|---|---|---|
| 1 | Hardcoded weak secret key | `app.py` top | Scanner should flag it |
| 2 | Plaintext passwords | users table | Check DB / `/profile/1` |
| 3 | XSS via username | `/` | Register/login with script name |
| 4 | SQL injection (login bypass) | `/login` | user: `admin' --` , any password |
| 5 | Verbose error messages | `/login`, `/search` | user: `'` |
| 6 | No brute-force protection | `/login` | Repeated attempts |
| 7 | SQL injection (UNION) | `/search?q=` | `' UNION SELECT username, password FROM users --` |
| 8 | Reflected XSS | `/search?q=` | `<script>alert(1)</script>` |
| 9 | Stored XSS | `/comments` | Post `<img src=x onerror=alert(1)>` |
| 10 | No CSRF protection | all POST forms | Forge a cross-site POST |
| 11 | IDOR | `/profile/<id>` | Change id 1, 2, 3 without login |
| 12 | Command injection | `/ping` | host: `127.0.0.1; id` |
| 13 | Path traversal | `/download?file=` | `../app.py` |
| 14 | Unrestricted file upload | `/upload` | Upload `.html` / `.py` file |
| 15 | Open redirect | `/redirect?url=` | `/redirect?url=https://evil.com` |
| 16 | Broken access control | `/admin` | Visit without login |
| 17 | Sensitive info exposure | `/debug/config` | Leaks secret key + env vars |
| 18 | Missing security headers, insecure cookies | all responses | No CSP, X-Frame-Options, HttpOnly/Secure |
| 19 | Debug mode enabled | `app.run(debug=True)` | Werkzeug debugger |

## How to use with your plugin

1. Run your plugin/scanner against this folder (or the running site).
2. Compare its findings with the table above.
3. Score it: detected / 19 and how many it fixed correctly.
4. Re-run the app after the plugin's fixes and retry the sample tests.

Tip: keep a clean copy of `app.py` so you can compare before/after.
