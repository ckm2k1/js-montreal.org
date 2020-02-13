import aiohttp


async def placeholder(*args, **kwargs):
    pass


class WSClient:

    def __init__(self, on_connect=None, on_message=None, on_close=None, on_error=None):
        self.on_message = self._ensure_callback(on_message)
        self.on_close = self._ensure_callback(on_close)
        self.on_error = self._ensure_callback(on_error)
        self.on_connect = self._ensure_callback(on_connect)

    def _ensure_callback(self, fn):
        if fn is not None:
            return fn
        return placeholder

    async def connect(self, url):
        self.session = aiohttp.ClientSession()

        try:
            async with self.session.ws_connect(url) as ws:
                await self.on_connect(ws)

                async for msg in ws:
                    print(msg.type)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        exit = await self.on_message(msg.type, msg.data, ws)
                        if exit:
                            break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print('GOT ERROR', msg)
                        await self.on_error(msg, ws)
                        await ws.close()
                        break

                if not ws.closed:
                    await ws.close()
        except aiohttp.client_exceptions.ClientConnectionError as ex:
            await self.on_error(ex)
        finally:
            await self.on_close()
            await self.session.close()

    async def close(self):
        if not self.socket.closed:
            return await self.socket.close()


if __name__ == '__main__':
    import asyncio

    async def close():
        print('on_close handler')

    async def err(data: Exception, ws=None):
        print('OH NO', data)

    async def msg(ty, data, ws):
        print(ty, data)

    async def main():
        client = WSClient(on_message=msg, on_close=close, on_error=err)
        await client.connect('http://localhost:8666/ws')

    asyncio.run(main())
