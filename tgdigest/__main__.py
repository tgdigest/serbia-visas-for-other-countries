import asyncio
import argparse
from pathlib import Path
from tgdigest.client import TgDigestClient
from tgdigest.parser import load_config
from tgdigest.cache import MessagesCache

async def main():
    client = TgDigestClient()
    await client.start()
    
    me = await client.client.get_me()
    print(f"Logged in as: {me.first_name} (ID: {me.id})")
    
    # Load configuration
    config = load_config()
    
    for chat in config.chats:
        print(f"\n=== {chat.title} ===")
        print(f"URL: {chat.url}")
        
        cache = MessagesCache(chat.url)
        
        # Check last cached message
        last_cached_id = cache.get_last_message_id()
        if last_cached_id:
            print(f"Last cached message ID: {last_cached_id}")
            min_id = last_cached_id
        else:
            print("No cached messages, fetching from beginning")
            min_id = 0
        
        # Get new messages
        current_day = None
        day_messages = []
        total_fetched = 0
        
        async for message in client.client.iter_messages(
            chat.get_chat_id(), 
            reply_to=chat.get_topic_id(),
            min_id=min_id,
            reverse=True
        ):
            msg_day = message.date.strftime("%Y-%m-%d")
            
            # If day changed, save previous day's messages
            if current_day and msg_day != current_day:
                cache.save_messages(day_messages)
                print(f"  Saved {len(day_messages)} messages for {current_day}")
                day_messages = []
            
            current_day = msg_day
            day_messages.append(message)
            total_fetched += 1
        
        # Save last day's messages
        if day_messages:
            cache.save_messages(day_messages)
            print(f"  Saved {len(day_messages)} messages for {current_day}")
        
        print(f"Total fetched: {total_fetched} new messages")
    
    await client.disconnect()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram digest fetcher')
    parser.add_argument('--force-login', action='store_true', help='Force re-login even if session exists')
    args = parser.parse_args()
    
    # Remove session file if force login
    if args.force_login:
        session_file = Path('tgdigest_session.session')
        if session_file.exists():
            session_file.unlink()
            print("Removed existing session, forcing re-login...")
    
    asyncio.run(main())