import csv
import threading
from pathlib import Path

_lock = threading.Lock()
# Default to MQTT output since this repository focuses on MQTT now
_output = Path("all_devices_recorded_data.csv")


def initialize_output(path: str | None = None):
    """Create/overwrite the output CSV with the standard header.

    If path is provided, switch the global output to it.
    This is intended to be called at application startup to start a fresh log.
    """
    global _output
    if path:
        _output = Path(path)
    header = [
        "device_id",
        "time",
        "date",
        "protocol",
        "sensor_type",
        "value",
        "send_ts",
        "receive_ts",
        "latency_ms",
    ]
    with _lock:
        with _output.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)


def log_sent(record: dict, sent_log_path: str | None = None):
    """Log that a device attempted to send a message (used for PDR calculation).

    record should contain at least device_id and send_ts.
    """
    target = Path(sent_log_path) if sent_log_path else Path("sent_messages.csv")
    header = ["device_id", "send_ts", "protocol"]
    with _lock:
        exists = target.exists()
        with target.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if not exists:
                writer.writerow(header)
            writer.writerow([record.get("device_id"), record.get("send_ts"), record.get("protocol")])


def initialize_sent_log(path: str | None = None):
    """Create/overwrite the sent_messages.csv log with header."""
    target = Path(path) if path else Path("sent_messages.csv")
    header = ["device_id", "send_ts", "protocol"]
    with _lock:
        with target.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)


def set_output_file(path: str):
    """Set the global output CSV file path used by save_to_csv.

    Use this at startup to reset the recorded CSV (default: 'all_devices_recorded_data.csv').
    """
    global _output
    _output = Path(path)


def save_to_csv(record: dict, output_path: str | None = None):
    # Supported keys: device_id, time, date, protocol, sensor_type, value, send_ts, receive_ts, latency_ms
    header = ["device_id", "time", "date", "protocol", "sensor_type", "value", "send_ts", "receive_ts", "latency_ms"]
    target = Path(output_path) if output_path else _output
    with _lock:
        exists = target.exists()
        with target.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if not exists:
                writer.writerow(header)
            row = [
                record.get("device_id"),
                record.get("time"),
                record.get("date"),
                record.get("protocol"),
                record.get("sensor_type"),
                record.get("value"),
                record.get("send_ts", ""),
                record.get("receive_ts", ""),
                record.get("latency_ms", ""),
            ]
            writer.writerow(row)

def read_all():
    if not _output.exists():
        return []
    with _output.open("r", encoding="utf-8") as fh:
        return list(csv.reader(fh))
