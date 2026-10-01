# BIG-IP API Security — Advanced WAF + APM, OWASP API Top 10 (hands-on)

A **beginner, start-to-finish** journey. We take the **OWASP API Security Top 10
(2023)** one category at a time (Chapter N = APIN), and for each one you'll
*attack* NimbusBank, *see* it in BIG-IP, then *mitigate* it — watching how
**Advanced WAF (AWAF)** and **APM** divide the work.

> Companion to [`DEPLOY-BIGIP.md`](DEPLOY-BIGIP.md), which already put NimbusBank
> behind a BIG-IP Virtual Server with one pool per service. This guide assumes
> that VS exists and the app is reachable through it.

## How to use this guide

Do **one chapter, fully**, before moving on. Each chapter follows the same loop:

1. **Attack** — run a NimbusBank attack (a `curl` or a `nimbusbank-bots` script) at the VS.
2. **See** — find it in BIG-IP's **Security ▸ Event Logs** (your "tail -f" for WAF).
3. **Mitigate** — turn on the specific AWAF and/or APM control for that category.
4. **Re-attack** — confirm it's now blocked.
5. **Checkpoint** — what you learned, and which layer did the work.

When you finish a chapter and it clicks, tell me and we'll write the next one.

## AWAF vs APM — who does what (read this once)

They sit on the **same Virtual Server** but protect different things:

- **Advanced WAF (AWAF / ASM)** inspects the **content** of requests and
  responses: attack signatures (SQLi, XSS…), OpenAPI schema validation, allowed
  methods, rate limiting, bot defense, and **Data Guard** (masking SSN/PAN/CVV in
  responses). Think: *"is this request/response malicious or malformed?"*
- **APM (Access Policy Manager)** controls **access**: who the caller is and what
  they're allowed to reach — authentication (OAuth/OIDC/JWT), per-request
  authorization, and per-URL/method access rules. Think: *"is this caller allowed
  to do this?"*

Rule of thumb for the Top 10: **authorization/authentication gaps (BOLA, Broken
Auth, BFLA) lean on APM**; **payload, schema, data-exposure, and
resource-consumption gaps lean on AWAF**. Several categories use **both** — that's
the point of this journey.

## The roadmap

| Stage | OWASP API (2023) | NimbusBank gap you'll attack | Main BIG-IP control | Attack to fire |
|---|---|---|---|---|
| **0** | *Foundations* | — | Provision AWAF+APM, baseline WAF policy, Event Logs | any bot script |
| **1** | API1 BOLA | IDOR on `/accounts/{id}`, cards, transfers | APM per-request authz (+ AWAF session tracking) | `xc/sensitive_data_probe.py` |
| **2** | API2 Broken Authentication | weak OTP, enumeration, expired-token, reset flaws | APM auth (OAuth/OIDC/JWT) + AWAF **Brute Force** / **Login Enforcement** | `attacks/credential_stuffing.py`, `otp_bruteforce.py` |
| **3** | API3 BOPLA (mass-assign + data exposure) | `PATCH /me`→admin; SSN/PAN/CVV in responses | AWAF **OAS request/response validation** + **Data Guard** | `attacks/privilege_escalation.py`, `xc/sensitive_data_probe.py` |
| **4** | API4 Unrestricted Resource Consumption | no rate limits, no upload cap, app-DoS | AWAF **rate limiting** + **DoS profiles** | `attacks/app_dos.py` |
| **5** | API5 BFLA | admin-override, `/kyc/pending`, `/admin/overview` | APM per-URL/method authz + AWAF **Allowed Methods** / **URL flow** | README BFLA curls |
| **6** | API6 Sensitive Business Flows | fake accounts, transfer/credit abuse | AWAF **Bot Defense** + rate limiting | `attacks/fake_account_farming.py` |
| **7** | API7 SSRF | `/accounts/link-external` | AWAF **SSRF attack signatures** + host restrictions | SSRF curl |
| **8** | API8 Security Misconfiguration | verbose errors, any method, undocumented paths | AWAF signatures (Info-Leak, Vuln-Scanner), Allowed Methods, OAS; APM error-schema | `xc/custom_header_attack.py`, `api_schema_abuse.py` |
| **9** | API9 Improper Inventory | shadow `/legacy/export`, `/legacy/orders` | AWAF **OAS enforcement** (reject undocumented) + API discovery | `xc/shadow_api.py` |
| **10** | API10 Unsafe Consumption of APIs | services consuming auth JWKS | AWAF OAS validation of consumed APIs | — |

We write each chapter when you reach it, pulling F5's exact recommended controls
from their OWASP API Top 10 guide and turning them into GUI steps against your VS.

---

## Chapter 0 — Foundations

Goal: get AWAF (and APM) provisioned, put a **baseline WAF policy in monitoring
mode** on your NimbusBank VS, fire an attack, and **read the Event Log**. No
blocking yet — first you learn to *see*. (This is the WAF equivalent of the
`log` + `tail -f /var/log/ltm` loop you learned for iRules.)

> Menu names vary slightly across TMOS versions; the flow is the same. If a path
> differs, search the GUI for the bold feature name.

### 0.1 — Provision the modules

**System ▸ Resource Provisioning.**
- Set **Application Security (ASM)** — this is Advanced WAF — to **Nominal**.
- Set **Access Policy (APM)** to **Nominal** (we'll use it from Chapter 1).
- Submit. The box re-provisions (can take a few minutes; it may restart services).
- Confirm afterwards under **Statistics ▸ Dashboard** or that both modules now
  appear in the top-nav (Security ▸ Application Security; Access ▸ Profiles/Policies).

> On a BIG-IP VE, make sure it has enough RAM/CPU for ASM+APM (a small lab guest
> may need resizing). If provisioning fails, that's almost always the cause.

### 0.2 — Pick the target VS

Use the Virtual Server from `DEPLOY-BIGIP.md` that fronts the NimbusBank gateway
(the one on `VS_IP:80` with the path-routing iRule). All `/api/*` traffic flows
through it, so one WAF policy here covers every service.

### 0.3 — Create a baseline WAF policy (monitoring)

**Security ▸ Application Security ▸ Security Policies ▸ Create (or Policies List ▸ Create).**
- **Name:** `nimbus-waf`
- **Policy Template:** start with **Rapid Deployment Policy** (a sane generic
  baseline with attack signatures). *(We'll switch to an OpenAPI/API-protection
  template in the API-specific chapters 3/8/9.)*
- **Enforcement Mode:** **Transparent** (a.k.a. monitoring) — it **detects and
  logs** but does **not block** yet. This is deliberate: Chapter 0 is about
  seeing.
- **Signature Staging:** leave default (new signatures start in staging).
- Create / Save, then **Apply Policy**.

### 0.4 — Attach the policy to the VS

Open your VS ▸ **Security ▸ Policies** tab.
- **Application Security Policy:** **Enabled**
- **Policy:** `nimbus-waf`
- Update.

Now every request through the VS is inspected by AWAF (in monitor mode).

### 0.5 — Generate attack traffic

Point an attack at the **VS** (not the origin). From the repo:

```bash
# aim the bots at the BIG-IP VS instead of localhost
NIMBUS_URL=http://<VS_IP> docker compose run --rm bots xc/sqli_signatures.py --set all
```

or a quick manual one:

```bash
curl "http://<VS_IP>/api/accounts/accounts/search?q=' OR '1'='1"
```

### 0.6 — Read the Event Log (your WAF "tail -f")

**Security ▸ Event Logs ▸ Application ▸ Requests.**
- You should see your requests flagged with violations (e.g. **"SQL-Injection"**
  attack signatures), each showing the matched signature, the attack type, the
  **Enforcement action = Alarmed** (not Blocked — we're in Transparent mode), and
  the raw request.
- Click a request to see the full detail: which signature matched, the
  parameter/offset, accuracy, and the response.

This is your core feedback loop for every chapter from here on: **attack → read
the Event Log → see what AWAF caught (or missed)**.

### 0.7 — Checkpoint

You now have:
- AWAF **and** APM provisioned.
- A WAF policy attached to the NimbusBank VS, in **monitoring** mode.
- The ability to fire attacks at the VS and **see** them in the Event Log.

You've also seen the division of labor in miniature: AWAF matched a **payload**
signature (SQLi). In the next chapters you'll (a) flip specific protections to
**blocking**, and (b) bring **APM** in for the access-control categories, so you
feel how the two cooperate.

**When you're comfortable here, tell me and we'll do Chapter 1 — API1 BOLA**,
where APM does the heavy lifting (per-request authorization) and you'll stop
`xc/sensitive_data_probe.py` from walking account IDs.

---

## Chapters 1–10

*Written one at a time as you progress. Next up: Chapter 1 — API1 BOLA.*
