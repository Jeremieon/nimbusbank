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

We write each chapter when you reach it, mapping each OWASP API Security Top 10
category to the BIG-IP control that addresses it, as concrete GUI steps against
your VS.

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

## Chapter 1 — API1: Broken Object Level Authorization (BOLA)

**The gap in NimbusBank:** `GET /api/accounts/accounts/{id}` (and the same on
cards and transfers) has *no ownership check* and uses *small sequential integer
ids*. Logged in as alice you can read carol's account id 7 — full SSN and all —
just by changing the number. Walk `1..10` and you've exfiltrated every customer.

**Why this chapter is different from Chapter 0:** a BOLA request is **perfectly
well-formed**. `GET /api/accounts/accounts/7` with a valid token is a legal
request — there's no SQL, no script, no bad character. **So no attack signature
fires.** This is the #1 thing to internalise about API security:

> Access-control flaws need access-control controls, not signatures. A
> signature WAF alone cannot tell "alice reads her own account" from "alice
> reads carol's account" — both look identical on the wire.

That's exactly why BIG-IP solves BOLA with **three layers working together**,
not with the signature engine:

1. **APM / JWT validation** establishes *who* the caller is (a trustworthy
   identity), so there's something to authorize against.
2. **An authorization check** (an iRule, or the app itself) decides whether that
   identity may touch *this object*.
3. **AWAF behavioural / rate controls** catch the *enumeration pattern* (one
   session walking many object ids fast) as a backstop.

### 1.1 — Attack first, and watch a signature NOT fire

Fire BOLA-focused traffic at your VS and look at the Event Log:

```bash
# just the object-walking attacks, pointed at the BIG-IP VS
NIMBUS_URL=http://<VS_IP> docker compose run --rm -e NIMBUS_URL bots \
  attack_engine.py --only bola_read,card_theft --duration 60
```

In **Security ▸ Event Logs ▸ Application ▸ Requests**, you'll see the requests
arrive — but with **no violation / no attack signature** (they're clean GETs).
That "nothing caught it" is the lesson. Leave the engine running for the rest of
the chapter; its live **BLOCKED(403)** column is your scoreboard.

### 1.2 — Establish identity (APM / JWT)

You need a verified caller identity before you can authorize. NimbusBank already
issues RS256 JWTs (signed by `auth-service`, public key at
`/.well-known/jwks.json`). Two ways to make BIG-IP trust and read it:

- **Advanced WAF API protection — JWT validation:** in the API protection
  workflow you point BIG-IP at the JWKS URL so it validates the token signature
  and expiry at the edge (we set this up properly in **Chapter 2 — API2 Broken
  Auth**). For now the key idea: after validation, the `sub` claim (the user id)
  is a *trusted* value.
- **APM access policy:** an access profile with an OAuth/JWT provider validates
  the token and exposes claims as session variables.

For this chapter we'll read the `sub` claim in an iRule. (In the lab we decode it
directly; in production you let APM/AWAF *validate* it first, then read the
validated claim — that's the APM+AWAF pairing, completed in Chapter 2.)

### 1.3 — Enforce object ownership (the real fix) — iRule + data-group

BIG-IP doesn't know your data model (which account belongs to whom), so give it
the mapping as a **data-group**, then an iRule compares the requested object's
owner to the caller's `sub` and blocks a mismatch.

**Step A — create the data-group.** Local Traffic ▸ iRules ▸ Data Group List ▸
Create:
- Name: `nimbus_account_owner`
- Type: **String**
- Records (NimbusBank's seeded ids → owner user-id):

  | String (account id) | Value (owner `sub`) |
  |---|---|
  | 1 | 11111111-1111-1111-1111-111111111111 |
  | 2 | 11111111-1111-1111-1111-111111111111 |
  | 3 | 22222222-2222-2222-2222-222222222222 |
  | 4 | 22222222-2222-2222-2222-222222222222 |
  | 5 | 33333333-3333-3333-3333-333333333333 |
  | 6 | 33333333-3333-3333-3333-333333333333 |
  | 7 | 44444444-4444-4444-4444-444444444444 |
  | 8 | 44444444-4444-4444-4444-444444444444 |
  | 9 | 55555555-5555-5555-5555-555555555555 |
  | 10 | 55555555-5555-5555-5555-555555555555 |

**Step B — create the iRule.** Local Traffic ▸ iRules ▸ Create, name
`irule_bola_accounts`:

```tcl
when HTTP_REQUEST {
    # Guard object reads on the accounts service: /api/accounts/accounts/<id>
    if { [HTTP::path] matches_regex {^/api/accounts/accounts/[0-9]+$} } {
        set objid [lindex [split [HTTP::path] "/"] end]

        # Pull the caller's user id (the "sub" claim) out of the bearer JWT.
        # LAB NOTE: we DECODE the JWT here; we don't verify its signature.
        # In production let APM / AWAF JWT-validation verify it first (Ch.2),
        # then read the trusted claim. Decoding unverified is fine to learn on.
        set authz [HTTP::header value Authorization]
        if { not [string match "Bearer *" $authz] } {
            HTTP::respond 401 content "missing token"; return
        }
        set jwt [string range $authz 7 end]
        set payload [lindex [split $jwt "."] 1]
        set payload [string map {- + _ /} $payload]
        while { [expr {[string length $payload] % 4}] != 0 } { append payload "=" }
        if { not [regexp {"sub"\s*:\s*"([^"]+)"} [b64decode $payload] -> sub] } {
            HTTP::respond 401 content "no sub"; return
        }

        # Who owns this object? Block if it isn't the caller.
        set owner [class match -value -- $objid equals nimbus_account_owner]
        if { $owner ne "" && $owner ne $sub } {
            log local0. "BOLA blocked: sub=$sub -> account $objid (owner $owner)"
            HTTP::respond 403 content "Forbidden: not your object"
        }
    }
}
```

**Step C — attach it** to your NimbusBank VS (Virtual Server ▸ Resources ▸
iRules ▸ Manage) *below* your routing iRule so routing still happens. Order:
routing iRule first, `irule_bola_accounts` after (both run on `HTTP_REQUEST`).

> Scope note: this guards `accounts`. The same pattern (another data-group +
> rule, or one generalised rule) covers `cards` and `transfers` — add them once
> the accounts one clicks.

### 1.4 — Backstop the enumeration (AWAF rate / anomaly)

Ownership enforcement stops the *single* cross-user read; you should also blunt
the *pattern* (a session rapidly trying many ids — scraping). On BIG-IP:

- **Session/IP request rate limiting** on `/api/accounts/accounts/*` (in the WAF
  policy or an LTM policy) caps how fast one client can walk ids.
- **Web Scraping / Behavioural anomaly** (Security ▸ Application Security ▸
  Anomaly Detection) flags a session making abnormally many object requests.

These don't *replace* 1.3 — they slow and surface mass-enumeration even against
ids you didn't map.

### 1.5 — Re-attack and verify

The attack engine is still running. Within a report cycle you should see the
`bola_read` row flip from `2xx` to **403 (BLOCKED)** while `legit_list` stays
`2xx` (alice reading *her own* accounts 3 and 4 is still allowed — the rule only
blocks mismatches). Confirm by hand:

```bash
# alice's own account (allowed)
curl -s -o /dev/null -w "own id 3:   %{http_code}\n"  http://<VS_IP>/api/accounts/accounts/3 -H "Authorization: Bearer $TOK"
# carol's account (now blocked by the iRule)
curl -s -o /dev/null -w "other id 7: %{http_code}\n"  http://<VS_IP>/api/accounts/accounts/7 -H "Authorization: Bearer $TOK"
```

Expect `own id 3: 200` and `other id 7: 403`. The `log local0.` line also lands
in `/var/log/ltm` for each block.

### 1.6 — Checkpoint

- You saw that **signatures don't catch BOLA** — a clean request needs an
  access-control answer, not a pattern match.
- You enforced **object-level ownership at the edge** by combining **identity
  from the JWT** (the APM/AWAF job) with an **authorization decision** (the
  iRule + data-group), and backstopped mass-enumeration with **AWAF rate /
  anomaly**.
- You felt the real division of labor for the first time: AWAF/APM supply *who*,
  your policy/iRule supplies *allowed to?*.

Two honest limitations to carry forward: the data-group is a static mapping
(BIG-IP can't see live app data), and here we decoded the JWT without verifying
it. **Chapter 2 — API2 Broken Authentication** fixes the second properly (APM /
AWAF JWT validation against the JWKS), which is what makes the `sub` you
authorized on actually trustworthy.

**When this clicks, tell me and we'll do Chapter 2 — API2 Broken
Authentication** (validate the JWT at the edge, kill the weak-OTP/enumeration/
expired-token gaps, and make the identity Chapter 1 leaned on real).

---

## Chapters 2–10

*Written one at a time as you progress. Next up: Chapter 2 — API2 Broken
Authentication.*
