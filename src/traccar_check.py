import argparse
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

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
    push_url: Optional[str] = None,
) -> int:
    push_url = push_url or f"{base_url}:5055"
    devices = fetch(base_url.rstrip("/") + "/api/devices", token, False)
    positions = fetch(base_url.rstrip("/") + "/api/positions", token, False)
    latest_by_dev = latest_position_by_device(positions)

    acc = get_account_sync(STORE_PATH, ANISETTE_SERVER, ANISETTE_LIBS_PATH)
    logger.info(f"Logged in as: {acc.account_name} ({acc.first_name} {acc.last_name})")
    for d in devices:
        try:
            latest_pos = latest_by_dev.get(d.get("id"))
            key = KeyPair.from_b64(d.get("uniqueId"))
            reports = acc.fetch_location_history(key)

            logger.info(f"{d.get("uniqueId")} latest: {latest_pos}, reports: {len(reports)}")
            reports_sorted = sorted(reports, key=lambda r: r.timestamp) if reports else []

            for rep in reports_sorted:
                status = "UNKNOWN"
                if rep.timestamp and latest_pos:
                    status = "NEW" if rep.timestamp > latest_pos else "STALE"
                elif rep.timestamp and not latest_pos:
                    status = "NEW"
                elif not rep.timestamp:
                    status = "NO_REPORT"

                if status == "NEW" and rep.timestamp is not None:
                    params = {
                        "id": d.get("uniqueId"),
                        "lat": rep.latitude,
                        "lon": rep.longitude,
                        "timestamp": int(rep.timestamp.timestamp()),
                        "confidence": rep.confidence,
                        "accuracy": rep.horizontal_accuracy,
                        **( {"power": (voltage := (rep.status + 200) / 100), "batteryLevel": max(0, min(100, (voltage - 2.8) * 100))} if rep.status > 0 else {} ),
                        "ignoreMaxSpeedFilter": "true",
                        "approximate": "true"
                    }
                    logger.info(f"{params.get('id')} {rep.timestamp} -> Pushing to {push_url}...")
                    resp = requests.get(push_url, params=params, timeout=5)
                    if 200 > resp.status_code or resp.status_code >= 300:
                        logger.error(f"{params.get('id')} {rep.timestamp} -> FAILED ({resp.status_code}): {resp.text[:200]}")
                        break
        except Exception as e:
            logger.error(f"{d.get("uniqueId")} ❌ {e}")

    acc.to_json(STORE_PATH)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Check Traccar devices for newer Find My positions")
    ap.add_argument("--url", default="http://localhost", help="Traccar base URL, e.g., https://traccar.example.com (default: http://localhost)")
    ap.add_argument("--token", required=True, help="Traccar access token (Bearer)")
    ap.add_argument("--push-url", default=None, help="URL for pushing positions (default: {url}:5055)")
    ap.add_argument("--period", help="Fetch every period seconds (default: 3600)", default=3600, type=int)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    while True:
        logger.info("Running traccar_check")
        try:
            run(args.url, args.token, args.push_url)
        except Exception as e:
            logger.error(f"Error running traccar_check: {e}")
        logger.info(f"Waiting {args.period} seconds before next check...")
        time.sleep(args.period)


if __name__ == "__main__":
    raise SystemExit(main())
