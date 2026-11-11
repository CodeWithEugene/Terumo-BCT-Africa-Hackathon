# Security notes

A self-review done on 10 Nov 2026 for the hackathon prototype. It is not an independent security test,
and no outside audit tool was used. Each item marked "tested" has an automated test in `tests/`.

## What is in place

| Area | What we do | Tested |
| --- | --- | --- |
| Passwords | Stored as salted PBKDF2-SHA256 hashes (200,000 rounds). Compared in constant time. | yes |
| Sessions | A signed cookie (HMAC-SHA256), 12 hours, `HttpOnly`, `SameSite=Lax`. `Secure` when `SP_COOKIE_SECURE=1`. The signing key comes from `SP_SESSION_SECRET`, or a random key made when the database is created. | yes |
| Access | Every data request checks the signed-in role. A hospital officer sees one hospital; a regional officer sees the hospitals their centre supplies. Refused on the server, not hidden in the page. | yes |
| Wrong passwords | Five wrong tries for an account from one address locks it for 5 minutes. | yes |
| Cross-site requests | A request that changes something and names another site as its origin is refused. | yes |
| Injection | Every database query uses parameters. Dates are checked against a fixed list. | yes |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, a deny-all `Content-Security-Policy` and `Cache-Control: no-store` on API responses. | yes |
| Audit | Sign-ins, decisions, undo and the fallback switch are logged. The database refuses edits and deletes on the log. | yes |
| Secrets | None in the repo. `.env` and `wallet/` are ignored by git. The sync command never prints a setting. | by review |
| Browser | No third-party scripts, fonts or trackers. The page never inserts raw HTML. The browser cache holds the last brief and is cleared on sign-out. | by review |
| Dependencies | `npm audit` on the frontend's runtime packages: 0 known vulnerabilities on 10 Nov 2026. | by run |
| Data | No donor or patient identities are loaded. Unit labels are scrambled. The central copy holds aggregates and coded staff names only. | yes |

## Known gaps (do these before any real use)

- **Test log-ins are public.** The three demo accounts and their passwords are shown on the sign-in screen
  on purpose. Set `SP_DEMO_LOGINS=0`, remove them and create real accounts before real use.
- **HTTPS is not set up.** The prototype runs on `localhost`. Behind HTTPS, set `SP_COOKIE_SECURE=1` and add
  `Strict-Transport-Security` and a page-level `Content-Security-Policy` at the web server.
- **The password limit is kept in memory**, so it resets when the server restarts and is per server.
- **No multi-factor sign-in, no password reset, no account management screens.**
- **The local database file is not encrypted.** Use disk encryption on the device.
- **The FHIR and DHIS2 endpoints use the app's own sign-in**, not a system-to-system credential.
- **The API documentation page (`/api/docs`) is open.** Switch it off in production.
- **No independent penetration test, no dependency scan of the Python packages, no load test.**
