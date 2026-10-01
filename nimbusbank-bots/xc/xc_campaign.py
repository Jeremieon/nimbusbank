"""
xc_campaign.py — run every xc/ attack in sequence to light up all XC detections.

Reproduces the full API security challenge set against NimbusBank in one
command, with clear "Challenge N:" phase banners and small default volumes so
a laptop copes. Point NIMBUS_URL at your XC-protected hostname to practise
detection against F5 Distributed Cloud.

Each phase shells out to the standalone xc/ script, so what runs here is exactly
what the individual scripts do.

Usage:
    python3 xc_campaign.py                 # small run of all 8 challenges
    python3 xc_campaign.py --scale 2       # roughly double the volumes
"""

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def banner(n, title):
    print("\n" + "=" * 72)
    print(f" Challenge {n}: {title}")
    print("=" * 72)


def run(script, *cli_args):
    path = os.path.join(HERE, script)
    print(f"$ python3 xc/{script} {' '.join(cli_args)}\n")
    try:
        subprocess.run([sys.executable, path, *cli_args], check=False, cwd=HERE)
    except Exception as exc:  # noqa: BLE001
        print(f"  (phase error: {exc})")


def main():
    ap = argparse.ArgumentParser(description="Full API security challenge campaign vs NimbusBank.")
    ap.add_argument("--scale", type=int, default=1, help="multiplier on the volumes")
    args = ap.parse_args()
    s = max(1, args.scale)

    sys.path.insert(0, os.path.dirname(HERE))
    from config import BASE_URL
    print(f"API security challenge campaign against {BASE_URL}")
    print("(lab-only — point NIMBUS_URL at your XC-protected hostname to test XC)")
    start = time.time()

    banner(1, "SQL injection — basic (high-accuracy signatures)")
    run("sqli_signatures.py", "--set", "basic")

    banner(2, "SQL injection — advanced (UNION/@@version/error/boolean/time)")
    run("sqli_signatures.py", "--set", "advanced")

    banner(3, "Suspicious bot traffic (HTTP-library UA crawling many endpoints)")
    run("suspicious_bot.py", "--cycles", str(2 * s), "--max-id", "5")

    banner(4, "Zero-day via custom request header (+ re-engineered rename)")
    run("custom_header_attack.py", "--count", str(15 * s))
    run("custom_header_attack.py", "--count", str(15 * s), "--rename")

    banner(5, "Malicious users (sustained XSS from one fixed identity)")
    run("malicious_user_xss.py", "--rounds", str(3 * s))

    banner(6, "API misuse / schema validation (extra/wrong-type/missing)")
    run("api_schema_abuse.py")

    banner(7, "Sensitive-data exposure (SSN / full PAN+CVV in responses)")
    run("sensitive_data_probe.py", "--max-id", "4")

    banner(8, "API discovery (shadow / undocumented endpoints)")
    run("shadow_api.py", "--count", str(5 * s))

    print("\n" + "=" * 72)
    print(f" campaign complete in {time.time() - start:.1f}s")
    print(" XC hint: open the F5 Distributed Cloud console for the protected app's")
    print("   Load Balancer -> Security Monitoring / API Discovery / Malicious Users")
    print("   to watch WAF SQLi signatures, Bot Defense, Service Policy header")
    print("   matches, schema-validation events, sensitive-data findings and the")
    print("   newly-discovered shadow endpoints populate.")
    print(f" Local Ops console (pre-XC): curl -s {BASE_URL}/api/admin/admin/traffic")
    print("=" * 72)


if __name__ == "__main__":
    main()
