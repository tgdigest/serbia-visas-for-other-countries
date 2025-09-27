import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

class TgDigestClient:
    def __init__(self):
        self.api_id = int(os.getenv('API_ID'))
        self.api_hash = os.getenv('API_HASH')
        self.session_name = 'tgdigest_session'
        self.client = None
    
    async def start(self):
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        phone = os.getenv('PHONE_NUMBER')
        await self.client.start(phone=phone)
        return self.client
    
    async def get_messages(self, chat, limit=10):
        if not self.client:
            await self.start()
        
        messages = []
        async for message in self.client.iter_messages(chat, limit=limit):
            messages.append(message)
        return messages
    
    async def disconnect(self):
        if self.client:
            await self.client.disconnect()