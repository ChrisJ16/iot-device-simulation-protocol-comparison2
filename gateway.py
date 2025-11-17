from datetime import datetime
from typing import Dict
from storage import save_to_csv


def _normalize_common(data: Dict) -> Dict:
    # Ensure keys: device_id, time, date, protocol, sensor_type, value
    out = {
        "device_id": data.get("device_id") or data.get("id") or "",
        "time": data.get("time") or data.get("t") or "",
        "date": data.get("date") or data.get("d") or "",
        "protocol": data.get("protocol") or "",
        "sensor_type": data.get("sensor_type") or data.get("sensor") or "",
        "value": data.get("value") or data.get("val") or "",
    }
    # add receive timestamp if not present
    if "receive_ts" not in data:
        out["receive_ts"] = datetime.utcnow().isoformat()
    else:
        out["receive_ts"] = data.get("receive_ts")
    # preserve send_ts if present
    if "send_ts" in data:
        out["send_ts"] = data.get("send_ts")
    return out


def process_message(raw: Dict):
    """Process a raw message from any protocol, normalize and persist.

    Expects raw to be a dict with protocol-specific keys.
    """
    norm = _normalize_common(raw)
    # try to compute latency if send_ts present
    try:
        if "send_ts" in norm and norm.get("send_ts"):
            # let storage or collector compute latency; still write fields
            pass
    except Exception:
        pass
    # write to CSV via storage
    save_to_csv(norm)