import asyncio
import json
from gateway import process_message

import aiocoap.resource as resource
import aiocoap


class GatewayResource(resource.Resource):
    async def render_post(self, request):
        try:
            payload = request.payload.decode('utf-8')
            data = json.loads(payload)
            process_message(data)
        except Exception:
            pass
        return aiocoap.Message(code=aiocoap.CONTENT, payload=b'OK')


def start_coap_server(bind_host='127.0.0.1', bind_port=5683):
    async def _run():
        root = resource.Site()
        root.add_resource(['gateway'], GatewayResource())
        await aiocoap.Context.create_server_context(root, bind=(bind_host, bind_port))
        # run forever
        await asyncio.get_running_loop().create_future()

    loop = asyncio.new_event_loop()
    def _starter():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())

    import threading
    t = threading.Thread(target=_starter, daemon=True)
    t.start()
    return t
