"""
run_all.py — a scripted attack campaign that lights up the Ops console.

Runs, in sequence and with clear phase banners:
    1. A little legitimate baseline traffic (so the console isn't all-attack).
    2. Reconnaissance / enumeration + credential stuffing.
    3. OTP brute-force against a target we initiate.
    4. Fake-account farming.
    5. Mass data exfiltration: account scraping, card harvesting, KYC PII, SQLi dump.
    6. Privilege escalation (customer -> admin).
    7. A bounded load spike.

Everything is small by default so a normal laptop copes; pass --scale to turn it
up. Each phase invokes the standalone scripts as subprocesses with modest
arguments, so what you see here is exactly what the individual scripts do.

Usage:
    python3 run_all.py                 # small campaign
    python3 run_all.py --scale 2       # roughly double the counts
"""

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def banner(n: int, title: str) -> None:
    print("\n" + "=" * 70)
    print(f" PHASE {n}: {title}")
    print("=" * 70)


def run(script: str, *cli_args: str) -> None:
    path = os.path.join(HERE, script)
    print(f"$ python3 {script} {' '.join(cli_args)}\n")
    try:
        subprocess.run([sys.executable, path, *cli_args], check=False, cwd=HERE)
    except Exception as exc:  # noqa: BLE001
        print(f"  (phase error: {exc})")


def main():
    ap = argparse.ArgumentParser(description="Scripted NimbusBank attack campaign.")
    ap.add_argument("--scale", type=int, default=1, help="multiplier on the counts")
    args = ap.parse_args()
    s = max(1, args.scale)

    from config import BASE_URL
    print(f"NimbusBank attack campaign against {BASE_URL}")
    print("(lab-only — watch it land on the Ops console at "
          f"{BASE_URL}/api/admin/admin/traffic)")
    start = time.time()

    banner(1, "Legitimate baseline traffic")
    run("legit/normal_users.py", "--cycles", str(1 * s), "--users", "alice", "bob")

    banner(2, "Credential stuffing + account enumeration")
    run("attacks/credential_stuffing.py", "--concurrency", "8")

    banner(3, "OTP brute-force (target we initiate)")
    run("attacks/otp_bruteforce.py", "--concurrency", "20", "--max-attempts", "10000")

    banner(4, "Fake-account farming")
    run("attacks/fake_account_farming.py", "--count", str(10 * s), "--concurrency", "8")

    banner(5, "Mass data exfiltration (BOLA / BFLA / SQLi)")
    run("attacks/account_scraping.py", "--max-id", "10")
    run("attacks/card_harvesting.py", "--max-id", "10")
    run("attacks/kyc_pii_scrape.py")
    run("attacks/sqli_dump.py")

    banner(6, "Privilege escalation (mass assignment)")
    run("attacks/privilege_escalation.py")

    banner(7, "Bounded load spike")
    run("attacks/app_dos.py", "--requests", str(120 * s), "--concurrency", "16")

    print("\n" + "=" * 70)
    print(f" campaign complete in {time.time() - start:.1f}s")
    print(f" check the traffic jump: curl -s {BASE_URL}/api/admin/admin/traffic")
    print("=" * 70)


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
