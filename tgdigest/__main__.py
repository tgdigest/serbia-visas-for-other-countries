import argparse
import asyncio
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from tgdigest.cache import MessagesCache
from tgdigest.client import TgDigest
from tgdigest.models import Config


async def main():
    load_dotenv()

    client = TgDigest(
        api_id=int(os.getenv('API_ID')),
        api_hash=os.getenv('API_HASH'),
        phone=os.getenv('PHONE_NUMBER'),
    )

    me = await client.get_me()
    print(f'Logged in as: {me.first_name} (ID: {me.id})')

    with open('config.yaml', encoding='utf-8') as f:
        config = Config(**yaml.safe_load(f))

    for chat in config.chats:
        print(f'\n=== {chat.title} ===')
        print(f'URL: {chat.url}')

        cache = MessagesCache(chat.url)

        # Check last cached message
        last_cached_id = cache.get_last_message_id()
        if last_cached_id:
            print(f'Last cached message ID: {last_cached_id}')
            min_id = last_cached_id
        else:
            print('No cached messages, fetching from beginning')
            min_id = 0

        # Get new messages
        current_month = None
        month_messages = []
        total_fetched = 0

        async for message in client.iter_messages(
            chat.get_chat_id(),
            reply_to=chat.get_topic_id(),
            min_id=min_id,
            reverse=True
        ):
            msg_month = message.date.strftime('%Y-%m')

            # If month changed, save previous month's messages
            if current_month and msg_month != current_month:
                cache.save_messages(month_messages)
                print(f'  Saved {len(month_messages)} messages for {current_month}')
                month_messages = []

            current_month = msg_month
            month_messages.append(message)
            total_fetched += 1

        # Save last month's messages
        if month_messages:
            cache.save_messages(month_messages)
            print(f'  Saved {len(month_messages)} messages for {current_month}')

        print(f'Total fetched: {total_fetched} new messages')

    client.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram digest fetcher')
    parser.add_argument('--force-login', action='store_true', help='Force re-login even if session exists')
    args = parser.parse_args()

    # Remove session file if force login
    if args.force_login:
        session_file = Path('tgdigest.session')
        if session_file.exists():
            session_file.unlink()
            print('Removed existing session, forcing re-login...')

    asyncio.run(main())
