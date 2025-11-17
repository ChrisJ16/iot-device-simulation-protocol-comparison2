import threading
import time
import random
import csv
import json
from datetime import datetime
from storage import log_sent
from faults import should_drop, get_network_delay, is_device_failed, maybe_fail
from pathlib import Path
import paho.mqtt.client as mqtt


class MqttDeviceThread(threading.Thread):
    def __init__(self, device_id: str, sensor_files: dict, broker_host: str, topic: str, fixed_interval: int | None = None, broker_port: int = 1883):
        super().__init__(daemon=True)
        self.device_id = device_id
        self.sensor_files = sensor_files
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.fixed_interval = fixed_interval
        self._stop_event = threading.Event()
        self._client = mqtt.Client()

    def stop(self):
        self._stop_event.set()

    def join(self, timeout=None):
        self._stop_event.set()
        super().join(timeout)

    def _pick_random_reading(self):
        sensor_type = random.choice(list(self.sensor_files.keys()))
        path = self.sensor_files[sensor_type]
        if not Path(path).exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            reader = list(csv.reader(fh))
            if len(reader) <= 1:
                return None
            row = random.choice(reader[1:])
            if len(row) < 3:
                return None
            return {"time": row[0], "date": row[1], "sensor_type": sensor_type, "value": row[2]}

    def run(self):
        try:
            self._client.connect(self.broker_host, self.broker_port)
        except Exception as e:
            print(f"[MQTT DEVICE {self.device_id}] Failed to connect to broker: {e}")
            return

        while not self._stop_event.is_set():
            reading = self._pick_random_reading()
            if reading:
                payload = {
                    "device_id": self.device_id,
                    "time": reading["time"],
                    "date": reading["date"],
                    "protocol": "MQTT",
                    "sensor_type": reading["sensor_type"],
                    "value": reading["value"],
                }
                try:
                    # simulate device failure
                    maybe_fail(self.device_id)
                    if is_device_failed(self.device_id):
                        # device is down for now; skip
                        continue
                    # simulate packet loss
                    if should_drop():
                        # log attempted send but drop the packet
                        send_ts = datetime.utcnow().isoformat()
                        try:
                            log_sent({"device_id": self.device_id, "send_ts": send_ts, "protocol": "MQTT"})
                        except Exception:
                            pass
                        continue
                    # attach send timestamp (ISO format) for latency measurement
                    send_ts = datetime.utcnow().isoformat()
                    payload["send_ts"] = send_ts
                    # log the attempted send for PDR calculation
                    try:
                        log_sent({"device_id": self.device_id, "send_ts": send_ts, "protocol": "MQTT"})
                    except Exception:
                        # non-fatal if logging fails
                        pass
                    # apply network delay
                    delay = get_network_delay()
                    if delay and delay > 0:
                        time.sleep(delay)
                    self._client.publish(self.topic, json.dumps(payload))
                except Exception as e:
                    print(f"[MQTT DEVICE {self.device_id}] Publish error: {e}")

            if self.fixed_interval and self.fixed_interval > 0:
                sleep_for = self.fixed_interval
            else:
                sleep_for = random.randint(4, 10)
            for _ in range(int(sleep_for * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)


def start_mqtt_device_thread(device_id: str, sensor_files: dict, broker_host: str, topic: str, fixed_interval: int | None = None, broker_port: int = 1883):
    t = MqttDeviceThread(device_id=device_id, sensor_files=sensor_files, broker_host=broker_host, topic=topic, fixed_interval=fixed_interval, broker_port=broker_port)
    t.start()
    return t
