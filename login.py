import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv
import os

load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE_NUMBER')
session_name = 'tgdigest_session'

async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        
        code = input('Please enter the code you received: ')
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            print(f"Error: {e}")
            password = input('Enter 2FA password if required: ')
            await client.sign_in(password=password)
    
    me = await client.get_me()
    print(f"Successfully logged in as: {me.first_name} (ID: {me.id})")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())