import argparse
import asyncio
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from tgdigest.auto_collector import AutoCollector
from tgdigest.fetcher import Fetcher
from tgdigest.ai import AnthropicProvider, OpenAIProvider
from tgdigest.generator import Generator
from tgdigest.models import Config


async def fetch_messages(cfg: Config, *, force_login: bool = False):
    mf = Fetcher(
        api_id=int(os.getenv('API_ID')),
        api_hash=os.getenv('API_HASH'),
        phone=os.getenv('PHONE_NUMBER'),
        force_login=force_login,
    )
    for chat in cfg.chats:
        await mf.load_chat(chat)
    mf.disconnect()


async def generate_markdown(cfg: Config, *, max_months_per_run: int):
    # provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY'), model=cfg.openai_model)
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    generator = Generator(config=cfg, provider=provider)
    for chat in cfg.chats:
        if chat.title != 'Греция 🇬🇷':
            continue
        await generator.process_chat(chat, max_months_per_run)
    

async def reorganize_docs(cfg: Config):
    # provider = OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY'), model=cfg.openai_model)
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    generator = Generator(config=cfg, provider=provider)
    for chat in cfg.chats:
        await generator.reorganize_docs(chat)


def collect_auto(cfg: Config):
    collector = AutoCollector(config=cfg)
    for chat in cfg.chats:
        collector.process_chat(chat)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram digest')
    parser.add_argument('--config', '-c', default='config.yaml', help='Path to config file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    subparsers = parser.add_subparsers(dest='command', required=True)

    fetch_parser = subparsers.add_parser('fetch', help='Fetch messages from Telegram')
    fetch_parser.add_argument('--force-login', action='store_true', help='Force re-login even if session exists')

    gen_parser = subparsers.add_parser('generate', help='Generate markdown from cache')
    gen_parser.add_argument('--output', '-o', default='docs', help='Output directory')
    gen_parser.add_argument('--max-months', type=int, default=1, help='Max months to process per run')

    collect_parser = subparsers.add_parser('collect', help='Collect messages matching keywords')

    reorganize_parser = subparsers.add_parser('reorganize', help='Reorganize and improve documentation structure')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Enable OpenAI logging
    logging.getLogger('openai').setLevel(logging.DEBUG)
    logging.getLogger('httpx').setLevel(logging.INFO)

    load_dotenv()

    config_path = Path(args.config)
    with config_path.open(encoding='utf-8') as f:
        config = Config(**yaml.safe_load(f))

    if args.command == 'fetch':
        asyncio.run(fetch_messages(config, force_login=args.force_login))
    elif args.command == 'generate':
        asyncio.run(generate_markdown(config, max_months_per_run=args.max_months))
    elif args.command == 'collect':
        collect_auto(config)
    elif args.command == 'reorganize':
        asyncio.run(reorganize_docs(config))
