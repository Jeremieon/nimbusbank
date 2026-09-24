# NimbusBank bots & traffic toolkit

Scripts that generate **legitimate** and **attack** traffic against the local
NimbusBank lab, so you can watch it land on the Ops console
(`/api/admin/admin/traffic`) and — once you put a WAF / Bot Defense in front —
compare before/after.

> ⚠️ **Lab-only.** Every script targets `http://localhost:80` (the NimbusBank
> gateway) by default. Point it at nothing you don't own. There are no
> real leaked-credential lists here, no evasion, no persistence — the bots
> announce themselves (`User-Agent: nimbusbank-bots/1.0`) precisely so you can
> see them.

## What's here

```
config.py                  shared BASE_URL, seeded creds, the 2-step OTP login helper
legit/normal_users.py      gentle well-formed customer traffic (a baseline)
attacks/
  credential_stuffing.py   hammer /login with emails × common passwords; shows enumeration (404 vs 401)
  otp_bruteforce.py        brute the 4-digit OTP (0000-9999), unthrottled, until it lands
  fake_account_farming.py  mass-register instantly-verified accounts; reports accounts/sec
  account_scraping.py      walk BOLA GET /accounts/{id} → CSV of account #, full SSN, DOB, balance
  card_harvesting.py       walk BOLA GET /cards/{id} → CSV of full PAN + CVV
  kyc_pii_scrape.py        hit BFLA /kyc/pending as a customer → every user's KYC docs
  sqli_dump.py             one SQLi tautology on /accounts/search dumps all accounts
  privilege_escalation.py  register a customer, PATCH /me {role:admin}, use an admin endpoint
  app_dos.py               bounded burst of expensive /search requests to spike the console
run_all.py                 a scripted campaign: a little legit traffic + the attacks in sequence
```

Each attack script has a header docstring naming the vulnerability and the F5 XC
category it maps to, `argparse` flags with laptop-safe defaults, and a concise
report. Scraping scripts write a CSV (git-ignored) and print a truncated sample.

## Running it

### In a container (no host Python needed) — recommended

An opt-in `bots` service is defined in the root `docker-compose.yml` behind the
`bots` profile, so it never starts on a normal `docker compose up`. It joins the
compose network and reaches the gateway as `http://gateway:80`.

```bash
# from the repo root, with the stack already up (docker compose up -d)

# the full campaign (lights up the Ops console):
docker compose run --rm bots

# a single script (entrypoint is python3, so pass the script path):
docker compose run --rm bots attacks/account_scraping.py
docker compose run --rm bots attacks/otp_bruteforce.py --concurrency 20
docker compose run --rm bots legit/normal_users.py --cycles 3 --users alice bob
```

### On the host (if you have Python)

```bash
cd nimbusbank-bots
pip install -r requirements.txt
python3 run_all.py                      # or any individual script
NIMBUS_URL=http://localhost:80 python3 attacks/sqli_dump.py
```

## Watching the traffic

After a run, the Ops console reflects the surge:

```bash
curl -s http://localhost/api/admin/admin/traffic | python3 -m json.tool
```

or open `http://localhost/ops` in the browser (auto-refreshes every 4s).

## Env knobs (config.py)

| Var | Default | Meaning |
|---|---|---|
| `NIMBUS_URL` | `http://localhost:80` | gateway base URL (`http://gateway:80` in-container) |
| `NIMBUS_TIMEOUT` | `8.0` | per-request timeout (seconds) |
| `NIMBUS_CONCURRENCY` | `8` | default connection-pool size |
| `NIMBUS_UA` | `nimbusbank-bots/1.0 (+lab-only)` | User-Agent |

## Resetting the lab

The attacks create throwaway users/accounts and mutate balances (that's the
point). To get a pristine seed back:

```bash
docker compose down -v && docker compose up -d --build
```
