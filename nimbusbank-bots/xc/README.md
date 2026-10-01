# xc/ — API security challenge attack pack

An attack-traffic pack that reproduces eight common API attack types (an OWASP
API Security Top 10-style challenge set) against the NimbusBank lab, so you can
fire them at the app once it sits behind **F5 Distributed Cloud (XC)** and
practise detection, scoring and mitigation.

> ⚠️ **Lab-only.** These scripts generate attack traffic. Point them at nothing
> you don't own. They don't try to evade anything — the point is to *trigger*
> XC detections so you can see them, not to get past them. Each script shares
> the parent [`config.py`](../config.py) (same `NIMBUS_URL`, seeded creds and
> the 2-step OTP login helper).

## Challenge → script → XC signal

| # | Challenge / attack type | Script | XC feature / signal exercised |
|---|---|---|---|
| 1 | SQL injection — basic (high-accuracy signatures) | `sqli_signatures.py --set basic` | WAF SQLi signatures — **high** confidence |
| 2 | SQL injection — advanced (UNION / `@@version` / error / boolean / time-based) | `sqli_signatures.py --set advanced` | WAF SQLi signatures — **medium** confidence |
| 3 | Suspicious bot traffic | `suspicious_bot.py` | Bot Defense / suspicious-bot (HTTP-library UA, broad crawl) |
| 4 | Zero-day via a custom request header (+ re-engineered rename) | `custom_header_attack.py` (`--rename`) | Service Policy custom-header (name+value) match |
| 5 | Malicious users (sustained XSS from one identity) | `malicious_user_xss.py` | Malicious User detection / client risk scoring |
| 6 | API misuse / schema validation | `api_schema_abuse.py` | API request / OpenAPI schema validation |
| 7 | Sensitive-data exposure | `sensitive_data_probe.py` | Sensitive Data Discovery / masking (response inspection) |
| 8 | API discovery (shadow endpoint) | `shadow_api.py` | API Discovery — shadow / undocumented endpoint |
| — | run all of the above in sequence | `xc_campaign.py` | one command lights up every detection above |

The shadow endpoints challenge #7/#8 lean on live in the app
(`accounts-service`, added with `include_in_schema=False` so they are served but
absent from `/openapi.json`):

- `GET  /api/accounts/legacy/export` — dumps every account incl. full SSN.
- `POST /api/accounts/legacy/orders` — echoes a body whose `amount` is a string.

## Running it

The stack must be up (`docker compose up -d`, all services healthy). The root
`bots` compose service bind-mounts `nimbusbank-bots/`, so `xc/` is available
immediately (entrypoint is `python3` — pass the script path only):

```bash
# from the repo root
docker compose run --rm bots xc/xc_campaign.py            # the full campaign
docker compose run --rm bots xc/sqli_signatures.py --set all
docker compose run --rm bots xc/custom_header_attack.py --rename
docker compose run --rm bots xc/shadow_api.py
```

Or on the host with Python:

```bash
cd nimbusbank-bots
pip install -r requirements.txt
python3 xc/xc_campaign.py
NIMBUS_URL=http://localhost:80 python3 xc/sensitive_data_probe.py
```

## Pointing at XC

When practising against F5 Distributed Cloud, point the pack at the
**XC-protected hostname** instead of the local gateway:

```bash
NIMBUS_URL=https://nimbusbank.your-xc-namespace.example python3 xc/xc_campaign.py
```

Then watch the app's Load Balancer in the XC console — **Security Monitoring**
(WAF SQLi signatures, Service Policy hits), **Bot Defense**, **API Discovery**
(the `/legacy/*` shadow endpoints), **Malicious Users**, and the API
**schema-validation** and **sensitive-data** findings — populate as the
campaign runs. Pre-XC, the local Ops console still reflects the surge:
`curl -s http://localhost/api/admin/admin/traffic`.

Nothing here writes stolen data to disk; the scraping CSVs live with the
`attacks/` pack and are git-ignored (`*.csv`).
