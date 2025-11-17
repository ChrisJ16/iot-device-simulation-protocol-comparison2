import threading
import json
import time
from typing import Callable
import paho.mqtt.client as mqtt
from storage import save_to_csv
from gateway import process_message
from datetime import datetime


class MqttCollector:
    def __init__(self, broker_host="localhost", broker_port=1883, topic="iot"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self._client = mqtt.Client()
        self._thread = None
        self._stop_event = threading.Event()

        # Bind callbacks
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.topic)
        else:
            print(f"[MQTT COLLECTOR] Connection failed with rc={rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            data = json.loads(payload)
        except Exception as e:
            print(f"[MQTT COLLECTOR] Failed to decode message: {e}")
            return
        # attach receive timestamp and compute latency if send_ts present
        try:
            recv_ts = datetime.utcnow().isoformat()
            data["receive_ts"] = recv_ts
            if "send_ts" in data and data.get("send_ts"):
                try:
                    send_dt = datetime.fromisoformat(data.get("send_ts"))
                    recv_dt = datetime.fromisoformat(recv_ts)
                    latency_ms = int((recv_dt - send_dt).total_seconds() * 1000)
                    data["latency_ms"] = latency_ms
                except Exception:
                    data["latency_ms"] = ""
        except Exception:
            pass
        # forward normalized data to gateway for persistence
        try:
            process_message(data)
        except Exception as e:
            # fallback
            save_to_csv(data)

    def start(self):
        if self._thread and self._thread.is_alive():
            return

        def _run():
            try:
                self._client.connect(self.broker_host, self.broker_port)
                # Blocking network loop; exits when stop_event is set via disconnect
                while not self._stop_event.is_set():
                    self._client.loop(timeout=1.0)
            except Exception as e:
                print(f"[MQTT COLLECTOR] Error in MQTT loop: {e}")

        self._stop_event.clear()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        try:
            self._client.disconnect()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2)
