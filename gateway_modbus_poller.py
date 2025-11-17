import threading
import time
from typing import List
from pymodbus.client.sync import ModbusTcpClient
from gateway import process_message
from storage import log_sent
from faults import should_drop, get_network_delay, is_device_failed, maybe_fail
from datetime import datetime


class ModbusPoller(threading.Thread):
    def __init__(self, targets: List[dict], poll_interval=5):
        super().__init__(daemon=True)
        self.targets = targets
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            for t in self.targets:
                host = t.get('host', '127.0.0.1')
                port = t.get('port', 1502)
                device_id = t.get('device_id', 'modbus1')
                try:
                    client = ModbusTcpClient(host, port=port)
                    if not client.connect():
                        continue
                    rr = client.read_holding_registers(0, 1, unit=1)
                    if rr and hasattr(rr, 'registers'):
                        # simulate device failure and fault injection
                        maybe_fail(device_id)
                        if is_device_failed(device_id):
                            continue
                        if should_drop():
                            # log attempted send but don't forward
                            try:
                                log_sent({'device_id': device_id, 'send_ts': datetime.utcnow().isoformat(), 'protocol': 'MODBUS'})
                            except Exception:
                                pass
                            continue
                        val = rr.registers[0]
                        send_ts = datetime.utcnow().isoformat()
                        try:
                            log_sent({'device_id': device_id, 'send_ts': send_ts, 'protocol': 'MODBUS'})
                        except Exception:
                            pass
                        delay = get_network_delay()
                        if delay and delay > 0:
                            time.sleep(delay)
                        # normalize to gateway format and include dummy date/time
                        from datetime import datetime as _dt
                        now = _dt.utcnow()
                        msg = {
                            'device_id': device_id,
                            'protocol': 'MODBUS',
                            'sensor_type': 'temperature',
                            'value': str(val / 100.0),
                            'time': now.strftime('%H:%M:%S'),
                            'date': now.strftime('%Y-%m-%d'),
                            'send_ts': send_ts
                        }
                        process_message(msg)
                except Exception:
                    pass
            time.sleep(self.poll_interval)
