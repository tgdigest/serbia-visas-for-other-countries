import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

class TgDigestClient:
    def __init__(self):
        self.api_id = int(os.getenv("API_ID"))
        self.api_hash = os.getenv("API_HASH")
        self.session_name = "tgdigest"
        self._client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        self._client.start(phone=os.getenv("PHONE_NUMBER"))

    async def get_me(self):
        return await self._client.get_me()

    def iter_messages(self, *args, **kwargs):
        if not self._client:
            raise RuntimeError("Client not started. Call start() first.")
        return self._client.iter_messages(*args, **kwargs)

    def disconnect(self):
        self._client.disconnect()
