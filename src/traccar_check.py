import argparse
import logging
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
        reports = acc.fetch_last_reports(key)

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

            print(f" * findmy: {rep.timestamp}  status={status}")

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
                }
                resp = requests.get(f"{base_url}:5055", params=params, timeout=10, verify=False)
                if 200 <= resp.status_code < 300:
                    print("    -> OsmAnd push OK")
                else:
                    print(f"    -> OsmAnd push failed ({resp.status_code}): {resp.text[:200]}")

    acc.to_json(STORE_PATH)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Traccar devices for newer Find My positions")
    ap.add_argument("--url", required=True, help="Traccar base URL, e.g., https://traccar.example.com")
    ap.add_argument("--token", required=True, help="Traccar access token (Bearer)")
    ap.add_argument("--osmand-url", help="If set, push NEW positions to this OsmAnd endpoint, e.g., https://host:5055/")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)
    return run(args.url, args.token)


if __name__ == "__main__":
    raise SystemExit(main())
