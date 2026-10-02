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
attack_engine.py           CONTINUOUS mixed attack+legit traffic with a live 2xx/403 table
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

## Continuous attack engine (for WAF tuning)

`attack_engine.py` is the one to use when you want to **leave an attack running
against your endpoint while you build/tune a WAF** (BIG-IP Advanced WAF or F5
XC), rather than firing a one-shot campaign. It keeps generating a steady blend
of legitimate and malicious traffic across every category and prints a live
table — the key column is **BLOCKED(403)**:

```
category          total     2xx  BLOCKED(403)    4xx   5xx   err
legit_list          120     120             0      0     0     0
sqli                 20       0            20      0     0     0   <- WAF now blocking
bola_read            18       0            18      0     0     0
...
TOTAL               ...                            blocked=XX.X%
```

Against the raw origin everything is `2xx` and `blocked=0.0%`. As you move the
WAF from monitor to blocking, the attack rows flip to **403** while `legit_list`
stays green — that's your mitigation working, live.

```bash
# point it at your endpoint and leave it running
NIMBUS_URL=https://nimbus.labtestdemo.com python3 attack_engine.py
NIMBUS_URL=https://nimbus.labtestdemo.com python3 attack_engine.py --rate 8 --concurrency 6 --duration 300
python3 attack_engine.py --read-only                 # skip state-mutating attacks
python3 attack_engine.py --only sqli,bola_read,xss_memo
python3 attack_engine.py --exclude priv_esc,mass_assign

# or containerised (bots compose profile):
NIMBUS_URL=https://nimbus.labtestdemo.com \
  docker compose run --rm -e NIMBUS_URL bots attack_engine.py --duration 120
```

Flags: `--rate` (approx req/s), `--concurrency` (threads), `--duration` (0 =
until Ctrl-C), `--report-interval`, `--read-only`, `--only`, `--exclude`.

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
