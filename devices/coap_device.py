import asyncio
import json
import random
import threading
from datetime import datetime

import aiocoap
from storage import log_sent
from faults import should_drop, get_network_delay, is_device_failed, maybe_fail


async def _coap_send_once(protocol, uri: str, payload: dict):
    request = aiocoap.Message(code=aiocoap.POST, uri=uri, payload=json.dumps(payload).encode('utf-8'))
    try:
        await protocol.request(request).response
    except Exception:
        pass


def start_coap_device_loop(uri: str, device_id: str, sensor_files: dict, interval=5):
    async def _loop():
        protocol = await aiocoap.Context.create_client_context()
        try:
            while True:
                value = str(random.uniform(10.0, 30.0))
                maybe_fail(device_id)
                if is_device_failed(device_id):
                    await asyncio.sleep(interval)
                    continue
                if should_drop():
                    # log attempted send
                    try:
                        log_sent({'device_id': device_id, 'send_ts': datetime.utcnow().isoformat(), 'protocol': 'COAP'})
                    except Exception:
                        pass
                    await asyncio.sleep(interval)
                    continue
                from datetime import datetime as _dt
                now = _dt.utcnow()
                payload = {
                    'device_id': device_id,
                    'protocol': 'COAP',
                    'sensor_type': 'temperature',
                    'value': value,
                    'time': now.strftime('%H:%M:%S'),
                    'date': now.strftime('%Y-%m-%d')
                }
                send_ts = datetime.utcnow().isoformat()
                payload['send_ts'] = send_ts
                try:
                    log_sent({'device_id': device_id, 'send_ts': send_ts, 'protocol': 'COAP'})
                except Exception:
                    pass
                delay = get_network_delay()
                if delay and delay > 0:
                    await asyncio.sleep(delay)
                await _coap_send_once(protocol, uri, payload)
                await asyncio.sleep(interval)
        finally:
            try:
                await protocol.shutdown()
            except Exception:
                pass

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_loop())

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return t
