# NimbusBank integration test suite

Black-box integration tests that run against the **live** stack through the
Nginx gateway. They do two jobs:

1. **Happy paths** — confirm the normal app works (register/login/OTP + TOTP,
   list accounts, download a statement, move money, issue/list cards, upload
   and download a KYC doc, open and reply to a support ticket, every
   `/health`).
2. **Vulnerability lock-in** — assert that each *intentional* gap from the
   README's `INTENTIONALLY VULNERABLE` table is **still exploitable**, so a
   future refactor that accidentally "fixes" or breaks one fails the suite
   loudly. Each lock-in test's docstring names the README row it pins down.

These tests never change application code and never import a service in-process
— they exercise the real gateway path routing, real JWKS validation, and real
cross-service calls, which is the robust choice for this polyglot-shaped
microservices app.

## Layout

| File | What it covers |
|---|---|
| `conftest.py` | `BASE_URL`, seeded-data constants, and helpers/fixtures: `register_user`, `login` (the 2-step OTP dance), `auth_headers`, `jwt_claims`, session-scoped `alice`/`bob` tokens, and a fresh `throwaway` user per test |
| `test_health.py` | every service `/health` via the gateway returns 200 |
| `test_auth.py` | register, login+OTP, `/me`, token refresh, TOTP enroll/confirm/login |
| `test_accounts.py` | list own accounts (scoped), statement download |
| `test_cards.py` | list own cards (masked), issue a card on your own account |
| `test_kyc.py` | upload a benign file, list own docs, download it back |
| `test_support.py` | create a ticket, read own ticket, post a message |
| `test_transfers.py` | a same-user transfer actually moves both balances |
| `test_vulns_auth.py` | enumeration, echoed OTP, instant-verified account, PATCH /me privilege escalation, change-password without current, reset-token leak + reset |
| `test_vulns_bola_bfla.py` | BOLA/IDOR + BFLA across accounts, transfers, kyc, support, cards, admin |
| `test_vulns_injection.py` | SQLi, path traversal, SSRF, mass-assignment, stored XSS (transfers + support), and the JWT-validation contrast |

## Prerequisites

The stack must be **up and healthy** (all 9 containers):

```bash
docker compose up -d          # from the repo root; do NOT use -v
docker compose ps             # all healthy
```

## Running the tests

### Option A (preferred) — in a container, via the compose `test` profile

No host Python needed. The `tests` service is built from `tests/Dockerfile`,
joins the compose network, and reaches the gateway at `http://gateway:80`
(`BASE_URL` is set for you). It is guarded by the `test` profile, so it never
starts on a normal `docker compose up`.

```bash
# from the repo root
docker compose run --rm tests               # runs `pytest -q`
docker compose run --rm tests -q -x         # pass extra pytest args after the service name
docker compose run --rm tests test_vulns_injection.py
```

First run builds the image; later runs reuse it. Because `tests/` is
bind-mounted into the container, editing a test file does **not** require a
rebuild — only changing `requirements.txt` does (`docker compose build tests`).

### Option B — on the host, if you have Python 3.11+

```bash
cd tests
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
BASE_URL=http://localhost:80 pytest -q      # localhost:80 is the default too
```

`BASE_URL` defaults to `http://localhost:80` (the host-published gateway port),
so on the host you can usually just run `pytest -q`.

## Notes on data and re-runnability

- The suite is designed to **pass on repeated runs**. Mutating happy-path and
  auth vuln tests use a freshly-registered `throwaway` user each run; seeded
  mutations use fixed sentinel values or restore state (e.g. the foreign-card
  freeze test unfreezes afterward).
- The BOLA-drain and stored-XSS tests intentionally move money / append rows on
  each run; their assertions are delta- or membership-based, so they stay green
  across runs.
- One test is **skipped** on purpose:
  `test_support_accepts_expired_token_but_accounts_rejects`. Demonstrating
  support-service's `verify_exp=False` gap needs a validly-signed but *expired*
  RS256 token, which can't be produced black-box (login always mints a
  15-minute token, the private key is only inside auth-service, and tampering
  `exp` breaks the signature). The skip reason documents this, and the two
  `test_malformed_bearer_rejected_by_*` tests pin down that signature checking
  is the only thing the two services share — isolating the exp gap.
