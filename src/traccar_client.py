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
        latest[p.get("deviceId")] = _dt.datetime.fromtimestamp(p.get("fixTime") / 1000, tz=_dt.timezone.utc)
    return latest
