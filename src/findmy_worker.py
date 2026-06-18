import argparse
import datetime as _dt
import logging
import os
import time
from typing import Optional

from findmy import KeyPair
from supabase import Client, create_client

from _login import get_account_sync

logger = logging.getLogger(__name__)

STORE_PATH = os.environ.get("FINDMY_STORE_PATH", "account.json")
ANISETTE_SERVER: Optional[str] = os.environ.get("ANISETTE_URL") or None
ANISETTE_LIBS_PATH = os.environ.get("FINDMY_LIBS_PATH", "ani_libs.bin")


def _parse_ts(value: Optional[str]) -> Optional[_dt.datetime]:
    if not value:
        return None
    return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def run(sb: Client) -> None:
    acc = get_account_sync(STORE_PATH, ANISETTE_SERVER, ANISETTE_LIBS_PATH)
    logger.info(f"Logged in as: {acc.account_name} ({acc.first_name} {acc.last_name})")

    tags_resp = sb.table("hybrid_tags") \
        .select("tag_id, user_id, apple_priv_key, last_apple_timestamp") \
        .filter("apple_priv_key", "not.is", "null") \
        .filter("user_id", "not.is", "null") \
        .execute()
    tags = tags_resp.data or []
    logger.info(f"Processing {len(tags)} tags with Apple keys")

    for t in tags:
        tag_id = t["tag_id"]
        user_id = t["user_id"]
        apple_priv = t["apple_priv_key"]
        latest_ts = _parse_ts(t.get("last_apple_timestamp"))

        try:
            key = KeyPair.from_b64(apple_priv)
            reports = acc.fetch_location_history(key) or []
            reports_sorted = sorted(
                (r for r in reports if r.timestamp),
                key=lambda r: r.timestamp,
            )
            logger.info(f"{tag_id} latest={latest_ts} reports={len(reports_sorted)}")

            for rep in reports_sorted:
                if latest_ts and rep.timestamp <= latest_ts:
                    continue

                power: Optional[float] = None
                battery_level: Optional[int] = None
                if rep.status and rep.status > 0:
                    voltage = (rep.status + 200) / 100
                    power = voltage
                    battery_level = int(max(0, min(100, (voltage - 2.4) * 100)))

                row = {
                    "tag_id": tag_id,
                    "user_id": user_id,
                    "lat": rep.latitude,
                    "lon": rep.longitude,
                    "power": power,
                    "battery_level": battery_level,
                    "source": "apple",
                    "timestamp": rep.timestamp.isoformat(),
                }
                ins = sb.table("positions") \
                    .upsert(row, on_conflict="tag_id,source,timestamp", ignore_duplicates=True) \
                    .execute()
                position = (ins.data or [None])[0]
                if not position:
                    continue

                logger.info(f"{tag_id} inserted position at {position['timestamp']}")
        except Exception as e:
            logger.error(f"{tag_id} ❌ {e}")

    acc.to_json(STORE_PATH)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Apple Find My reports for all tags and insert into positions")
    ap.add_argument("--period", type=int, default=120, help="Polling period in seconds (default: 120)")
    ap.add_argument("--once", action="store_true", help="Run a single pass and exit")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE must be set")
    sb = create_client(url, key)

    if args.once:
        run(sb)
        return 0

    while True:
        logger.info("Running findmy worker pass")
        try:
            run(sb)
        except Exception as e:
            logger.error(f"Worker error: {e}")
        logger.info(f"Sleeping {args.period}s before next pass")
        time.sleep(args.period)


if __name__ == "__main__":
    raise SystemExit(main())
