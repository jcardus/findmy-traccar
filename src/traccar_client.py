import datetime as _dt
from typing import Any, Dict, List

import requests

def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def fetch(url: str, token: str, verify_tls: bool = True, timeout: int = 20) -> List[Dict[str, Any]]:
    resp = requests.get(url, headers=_auth_headers(token), timeout=timeout, verify=verify_tls)
    resp.raise_for_status()
    return resp.json()

def latest_position_by_device(positions: List[Dict[str, Any]]) -> Dict[int, _dt.datetime]:
    latest: Dict[int, _dt.datetime] = {}
    for p in positions:
        fix_time = p.get("fixTime")
        if isinstance(fix_time, str):
            latest[p.get("deviceId")] = _dt.datetime.fromisoformat(fix_time)
        else:
            latest[p.get("deviceId")] = _dt.datetime.fromtimestamp(fix_time / 1000, tz=_dt.timezone.utc)
    return latest
