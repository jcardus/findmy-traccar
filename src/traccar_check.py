import argparse
import logging
import time
from typing import Optional

import requests
from findmy import KeyPair

from _login import get_account_sync
from traccar_client import (latest_position_by_device, fetch)

STORE_PATH = "account.json"
ANISETTE_SERVER: Optional[str] = None
ANISETTE_LIBS_PATH = "ani_libs.bin"

def run(
    base_url: str,
    token: str,
) -> int:
    devices = fetch(base_url.rstrip("/") + "/api/devices", token, False)
    positions = fetch(base_url.rstrip("/") + "/api/positions", token, False)
    latest_by_dev = latest_position_by_device(positions)

    acc = get_account_sync(STORE_PATH, ANISETTE_SERVER, ANISETTE_LIBS_PATH)
    print(f"Logged in as: {acc.account_name} ({acc.first_name} {acc.last_name})")
    for d in devices:
        latest_pos = latest_by_dev.get(d.get("id"))
        key = KeyPair.from_b64(d.get("uniqueId"))
        reports = acc.fetch_location_history(key)

        print(f"{d.get("uniqueId")} latest: {latest_pos}")
        reports_sorted = sorted(reports, key=lambda r: r.timestamp) if reports else []

        for rep in reports_sorted:
            status = "UNKNOWN"
            if rep.timestamp and latest_pos:
                status = "NEW" if rep.timestamp > latest_pos else "STALE"
            elif rep.timestamp and not latest_pos:
                status = "NEW"
            elif not rep.timestamp:
                status = "NO_REPORT"

            #print(f" * findmy: {rep.timestamp}  status={status}")
            if status == "NEW" and rep.timestamp is not None:
                params = {
                    "id": d.get("uniqueId"),
                    "lat": getattr(rep, "latitude", None),
                    "lon": getattr(rep, "longitude", None),
                    "timestamp": int(rep.timestamp.timestamp()),
                    "accuracy": getattr(rep, "accuracy", None),
                    "confidence": getattr(rep, "confidence", None),
                    "horizontal_accuracy": getattr(rep, "horizontal_accuracy", None),
                    "status": getattr(rep, "status", None),
                    "ignoreMaxSpeedFilter": True
                }
                try:
                    resp = requests.get(f"{base_url}:5055", params=params, timeout=5, verify=False)
                    if 200 <= resp.status_code < 300:
                        print(f"{params} -> OsmAnd push OK")
                    else:
                        print(f"    -> OsmAnd push failed ({resp.status_code}): {resp.text[:200]}")
                except Exception as e:
                    print(f"    -> OsmAnd push error: {e}")

    acc.to_json(STORE_PATH)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Traccar devices for newer Find My positions")
    ap.add_argument("--url", default="http://localhost", help="Traccar base URL, e.g., https://traccar.example.com (default: http://localhost)")
    ap.add_argument("--url2", default="http://localhost", help="Traccar base URL, e.g., https://traccar.example.com (default: http://localhost)")
    ap.add_argument("--token", required=True, help="Traccar access token (Bearer)")
    ap.add_argument("--period", help="Fetch every period seconds (default: 3600)", default=3600, type=int)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    
    while True:
        print(f"Running traccar_check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        run(args.url, args.token)
        print(f"Waiting {args.period} seconds before next check...")
        time.sleep(args.period)


if __name__ == "__main__":
    raise SystemExit(main())
