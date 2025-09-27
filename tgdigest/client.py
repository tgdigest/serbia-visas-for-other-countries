from telethon import TelegramClient


class TgDigest:
    def __init__(
        self,
        *,
        api_id,
        api_hash,
        phone,
        session_name='tgdigest',
    ):
        self._client = TelegramClient(session_name, api_id, api_hash)
        self._client.start(phone=phone)

    async def get_me(self):
        return await self._client.get_me()

    def iter_messages(self, *args, **kwargs):
        if not self._client:
            raise RuntimeError("Client not started. Call start() first.")
        return self._client.iter_messages(*args, **kwargs)

    def disconnect(self):
        self._client.disconnect()
