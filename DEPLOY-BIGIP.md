# Deploying NimbusBank behind BIG-IP (LTM) — GUI guide

This puts BIG-IP in front of NimbusBank as the **reverse proxy / load balancer**,
with **one pool per microservice**. BIG-IP takes over the path-based routing that
the Nginx gateway does today: `/api/auth/*` → the auth pool, `/api/accounts/*` →
the accounts pool, and everything else → the frontend. This is the setup for
learning LTM (pools, monitors, virtual servers, iRules, SNAT) and, on top of it,
API security (WAF/ASM, API protection) later.

We start on **HTTP :80**. Moving to :443 is a small follow-up at the end.

---

## 1. Target architecture

```
                          ┌───────────────────────────────────────────┐
   browser  ── :80 ──►    │  BIG-IP   Virtual Server  VS_IP:80         │
                          │           HTTP profile (+ X-Forwarded-For) │
                          │           SNAT: Auto Map                    │
                          │           iRule: path → pool + strip prefix │
                          └───────────────┬───────────────────────────┘
                                          │  (BIG-IP internal VLAN, same subnet
                                          │   as the Docker host)
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ▼            ▼            ▼         ▼          ▼          ▼           ▼
   pool_frontend pool_auth  pool_accounts pool_transfers pool_kyc pool_support ...
   HOST:80      HOST:8001   HOST:8002     HOST:8003      HOST:8004 HOST:8005   ...
   (React SPA   (auth svc)  (accounts)    (transfers)    (kyc)     (support)
    via gateway)
```

Every pool has **one member** for now: the **Docker host IP** at that service's
already-published port. (Later you can turn each pool into a real multi-member
pool — see §8.)

### Pool member table

Substitute `HOST` with the Docker host's IP **on the BIG-IP internal VLAN**.
On this host the candidate NICs are:

| NIC | IP | Note |
|---|---|---|
| ens18 | 192.168.0.45 | default route / LAN — probably **not** the BIG-IP VLAN |
| ens19 | **10.10.10.30** | example used below — use this if it's your BIG-IP internal VLAN |
| ens20 | 10.20.20.30 | |
| ens21 | 10.30.40.30 | |
| ens22 | 10.40.10.30 | |

Pick the one on the same subnet as BIG-IP's internal self IP. This guide uses
`HOST = 10.10.10.30`.

| Pool | Member (HOST:port) | Service | Health monitor path |
|---|---|---|---|
| `pool_frontend`  | `10.10.10.30:80`   | Nginx (serves the React SPA) | `GET /`        |
| `pool_auth`      | `10.10.10.30:8001` | auth-service       | `GET /health` |
| `pool_accounts`  | `10.10.10.30:8002` | accounts-service   | `GET /health` |
| `pool_transfers` | `10.10.10.30:8003` | transfers-service  | `GET /health` |
| `pool_kyc`       | `10.10.10.30:8004` | kyc-service        | `GET /health` |
| `pool_support`   | `10.10.10.30:8005` | support-service    | `GET /health` |
| `pool_cards`     | `10.10.10.30:8006` | cards-service      | `GET /health` |
| `pool_admin`     | `10.10.10.30:8007` | admin-service      | `GET /health` |

> **Why the frontend stays as a pool too:** the Nginx gateway keeps serving the
> built SPA and its static assets (JS/CSS), and its `try_files … /index.html`
> rule makes SPA deep-links (e.g. `/dashboard`, `/cards`) work on refresh. Behind
> BIG-IP, the gateway's *own* `/api/*` proxy rules are simply never used —
> BIG-IP routes `/api/*` straight to the service pools instead. Nothing in the
> app changes.

---

## 2. Prerequisites & reachability check

1. NimbusBank is up on the Docker host: `docker compose up -d` (all 9 healthy).
   The ports `80, 8001–8007` are published on `0.0.0.0`, so they're reachable on
   every NIC including the BIG-IP VLAN.
2. BIG-IP VE is deployed with an **internal self IP on the same subnet** as
   `HOST` (e.g. self IP `10.10.10.10/24`, VLAN `internal`), and an external/VS
   address the browser can reach.
3. **Prove the members are reachable before touching BIG-IP.** From the Docker
   host itself:
   ```bash
   for p in 8001 8002 8003 8004 8005 8006 8007; do
     echo -n "$p: "; curl -s http://10.10.10.30:$p/health; echo
   done
   curl -s -o /dev/null -w "frontend: %{http_code}\n" http://10.10.10.30:80/
   ```
   You should get `{"status":"ok"}` seven times and `frontend: 200`.
   If BIG-IP has a bash shell, run the same `curl` from BIG-IP to confirm the
   VLAN path works end-to-end.

---

## 3. Create the health monitors

**Local Traffic ▸ Monitors ▸ Create.**

**Monitor A — `mon_nimbus_health`** (for all seven API pools):
- Name: `mon_nimbus_health`
- Type: **HTTP**
- Interval `5`, Timeout `16` (defaults are fine)
- **Send String:**
  ```
  GET /health HTTP/1.1\r\nHost: nimbus\r\nConnection: close\r\n\r\n
  ```
- **Receive String:** `ok`
  (each service's `/health` returns `{"status":"ok"}`)
- Finished ▸ **Create.**

**Monitor B — for the frontend:** just use the built-in **`http`** monitor
(it does `GET /` and marks the member up on a normal response). No custom
monitor needed. *(Don't use `mon_nimbus_health` here — the gateway answers
`/health` with `index.html`, not `ok`, so it would flap.)*

---

## 4. Create the pools

**Local Traffic ▸ Pools ▸ Create.** Repeat for each row of the table in §1.

For each API pool (example: `pool_auth`):
- Name: `pool_auth`
- Health Monitors: **`mon_nimbus_health`**
- Load Balancing Method: **Round Robin** (only one member for now)
- New Members ▸ **New Node**: Address `10.10.10.30`, Service Port `8001` ▸ **Add**
- Finished ▸ **Create.**

For `pool_frontend`:
- Health Monitors: **`http`**
- New Member: Address `10.10.10.30`, Service Port `80` ▸ **Add**

Do this for all eight pools (ports per the §1 table). After creating them,
each pool should show a **green** status once the monitor passes.

---

## 5. Create the routing iRule

This one rule does two jobs for every service: **pick the pool** by the
`/api/<svc>/…` prefix, and **strip that prefix** so the service sees its own
route (e.g. `/api/auth/login` → the auth service receives `/login`). Anything
that isn't `/api/*` goes to the frontend.

**Local Traffic ▸ iRules ▸ Create.**
- Name: `irule_nimbus_routing`
- Definition:

```tcl
when HTTP_REQUEST {
    # Route /api/<svc>/... to that service's pool, stripping the /api/<svc>
    # prefix so the microservice sees its own bare path. Everything else
    # (the SPA, its static assets, SPA deep-links) goes to the frontend.
    if { [HTTP::path] starts_with "/api/" } {
        # /api/<svc>/rest  ->  fields split on "/": 1="" 2="api" 3="<svc>"
        set svc [getfield [HTTP::path] "/" 3]
        switch $svc {
            "auth"      { pool pool_auth }
            "accounts"  { pool pool_accounts }
            "transfers" { pool pool_transfers }
            "kyc"       { pool pool_kyc }
            "support"   { pool pool_support }
            "cards"     { pool pool_cards }
            "admin"     { pool pool_admin }
            default     { pool pool_frontend ; return }
        }
        # strip the "/api/<svc>" prefix (anchored at the start, once)
        HTTP::path [regsub "^/api/$svc" [HTTP::path] ""]
    } else {
        pool pool_frontend
    }
}
```
- Finished ▸ **Create.**

> **Teaching note — why strip the prefix:** the Nginx gateway used
> `proxy_pass http://auth:8000/;` (trailing slash) which strips `/api/auth/`.
> Hit directly, each service serves *bare* routes (`/login`, `/health`,
> `/accounts/3`, `/tickets/2`, …). If BIG-IP forwarded `/api/auth/login`
> unchanged, the auth service would 404. The `regsub` reproduces Nginx's strip.

---

## 6. Create the HTTP profile (to log the real client IP)

Because we'll use **SNAT** (next step), the services would otherwise see BIG-IP's
self IP as the client. NimbusBank's request logger reads `X-Forwarded-For`, so
insert it and the Ops console will show real client IPs.

**Local Traffic ▸ Profiles ▸ Services ▸ HTTP ▸ Create.**
- Name: `http_nimbus`
- Parent Profile: `http`
- **Insert X-Forwarded-For: Enabled**
- Finished ▸ **Create.**

---

## 7. Create the Virtual Server

**Local Traffic ▸ Virtual Servers ▸ Create.**
- Name: `vs_nimbus_http`
- Type: **Standard**
- Destination Address/Mask: your **VS IP** (the address the browser hits), e.g.
  `10.10.10.100`
- Service Port: `80` (HTTP)
- **HTTP Profile (Client):** `http_nimbus`
- **Source Address Translation:** **Auto Map**  ← important, see below
- Resources ▸ **iRules:** add `irule_nimbus_routing`
- Resources ▸ **Default Pool:** `pool_frontend`
- Finished ▸ **Create.**

> **Teaching note — why SNAT Auto Map is required here:** the Docker host's
> default route is `192.168.0.1` (its LAN NIC), **not** BIG-IP. Without SNAT,
> BIG-IP preserves the browser's real source IP; the Docker host would then try
> to reply *directly* to the browser via its default gateway, bypassing BIG-IP →
> asymmetric routing → the connection hangs/fails. **Auto Map** makes BIG-IP
> replace the source IP with its own internal self IP (same subnet as the
> member), so the host replies to BIG-IP, which relays back to the browser. If
> you ever set the Docker host's default gateway *to* the BIG-IP self IP, you
> could drop SNAT and keep the real client IP natively — a good exercise later.

---

## 8. Test it

From a browser on a machine that can reach the VS IP:

1. Open `http://10.10.10.100/` → the NimbusBank hero/login page loads (served by
   `pool_frontend`).
2. Sign in as `alice@nimbusbank.io` / `password123`, enter the on-screen OTP →
   dashboard loads (that's `/api/auth/*` → `pool_auth`, then `/api/accounts/*` →
   `pool_accounts`, all through BIG-IP).
3. Make a transfer, open **Cards**, open **Ops** — the Ops console should now
   show request rows whose **client IP is your browser's real IP** (thanks to
   the X-Forwarded-For insertion).

CLI smoke test through the VS:
```bash
curl -s http://10.10.10.100/api/auth/health           # {"status":"ok"}  (pool_auth)
curl -s http://10.10.10.100/api/accounts/health       # {"status":"ok"}  (pool_accounts)
curl -s -o /dev/null -w "%{http_code}\n" http://10.10.10.100/   # 200 (frontend)
```

In the GUI, **Local Traffic ▸ Pools** should show every pool **green**
(monitor passing), and **Statistics ▸ Module Statistics ▸ Local Traffic** shows
connections spread across the pools as you click around the app.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pool shows **red / offline** | Monitor can't reach `HOST:port`, or wrong Receive string | From BIG-IP/host `curl http://HOST:port/health`; confirm `HOST` is the BIG-IP-VLAN NIC; API pools use `mon_nimbus_health` (Receive `ok`), frontend uses `http` |
| Page loads but **API calls 404** | Prefix not stripped / wrong pool | Re-check the iRule `regsub`; confirm the service serves bare routes (`curl http://HOST:8001/login` style) |
| Browser **hangs / no response** | SNAT missing → asymmetric routing | Set Source Address Translation = **Auto Map** on the VS |
| Login works but **stays logged out** | refresh cookie blocked | On :80 keep `COOKIE_SECURE=false`; it's same-origin so this should just work — check the browser isn't forcing HTTPS |
| Ops console shows **BIG-IP's IP** as client | X-Forwarded-For not inserted | Use the `http_nimbus` profile with Insert XFF enabled on the VS |

---

## 10. Next steps

- **HTTPS on :443.** Create a Client SSL profile (import a cert/key or use a
  self-signed one), add a second Virtual Server `vs_nimbus_https` on port 443
  with that Client SSL profile + the same `http_nimbus` profile, iRule, SNAT and
  default pool. Optionally add a tiny redirect VS on :80. Then set
  `COOKIE_SECURE=true` in `.env` and `docker compose up -d` so the refresh
  cookie is marked Secure.
- **Real multi-member pools.** Give each service its own routable IP (Docker
  `macvlan`, or run replicas on additional hosts) and add them as extra members
  so you can demo true load balancing, priority groups, and member drain.
- **API security layer.** Once traffic flows through BIG-IP, attach ASM/Advanced
  WAF (declarative WAF policy) to `vs_nimbus_http`, import each service's
  `/openapi.json` for API protection/schema enforcement, and use the intentional
  gaps (SQLi, BOLA, path traversal, etc.) plus the `nimbusbank-bots/` scripts to
  demonstrate detection and blocking before/after.

Each service already exposes a clean `/openapi.json` (e.g.
`http://10.10.10.30:8001/openapi.json`) — that's the file you'll import into the
API-protection policy.
