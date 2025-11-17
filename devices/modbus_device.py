import threading
import time
import random
from pymodbus.server.sync import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer


class ModbusDeviceThread(threading.Thread):
    def __init__(self, host='127.0.0.1', port=1502, unit_id=1, update_interval=5):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.update_interval = update_interval
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        # create a datastore with holding registers
        store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0] * 100)
        )
        context = ModbusServerContext(slaves=store, single=True)

        identity = ModbusDeviceIdentification()
        identity.VendorName = 'Sim'
        identity.ProductCode = 'SD'
        identity.VendorUrl = 'http://example.com'

        # Start server in a background thread via StartTcpServer which blocks; we instead periodically update registers
        # Approach: run StartTcpServer in its own thread and in this thread update the store.

        def _server_thread():
            StartTcpServer(context, identity=identity, address=(self.host, self.port))

        t = threading.Thread(target=_server_thread, daemon=True)
        t.start()

        try:
            while not self._stop_event.is_set():
                # update register 0 with a random temperature-like value scaled as integer
                temp = int(random.uniform(2000, 3000))  # e.g. scaled by 100
                with context[0].store.lock:
                    context[0].setValues(3, 0, [temp])
                time.sleep(self.update_interval)
        except Exception:
            pass


def start_modbus_device_thread(host='127.0.0.1', port=1502, unit_id=1, update_interval=5):
    t = ModbusDeviceThread(host=host, port=port, unit_id=unit_id, update_interval=update_interval)
    t.start()
    return t
