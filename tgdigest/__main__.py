import argparse
import asyncio
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from tgdigest.client import TgDigest
from tgdigest.models import Config


async def main(config: Config):
    td = TgDigest(
        api_id=int(os.getenv('API_ID')),
        api_hash=os.getenv('API_HASH'),
        phone=os.getenv('PHONE_NUMBER'),
    )

    for chat in config.chats:
        await td.load_chat(chat)

    td.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram digest fetcher')
    parser.add_argument('--config', '-c', default='config.yaml', help='Path to config file (default: config.yaml)')
    parser.add_argument('--force-login', action='store_true', help='Force re-login even if session exists')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    load_dotenv()

    config_path = Path(args.config)
    with config_path.open(encoding='utf-8') as f:
        config = Config(**yaml.safe_load(f))

    if args.force_login:
        session_file = Path('tgdigest.session')
        if session_file.exists():
            session_file.unlink()
            logging.info('Removed existing session, forcing re-login')

    asyncio.run(main(config))
