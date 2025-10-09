import argparse
import asyncio
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.logging import RichHandler

from tgdigest.ai import AnthropicProvider
from tgdigest.cases_extractor import CasesExtractor
from tgdigest.facts_extractor import FactsExtractor
from tgdigest.faq_normalizer import FAQNormalizer
from tgdigest.fetcher import Fetcher
from tgdigest.helpers import WorkLimiter
from tgdigest.models import Config
from tgdigest.questions_categorizer import QuestionsCategorizer
from tgdigest.questions_extractor import QuestionsExtractor
from tgdigest.yaml2md import Yaml2Md


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


def extract_facts(cfg: Config, *, max_months: int):
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    extractor = FactsExtractor(config=cfg, provider=provider)
    limiter = WorkLimiter(max_months)

    for chat in cfg.chats:
        if not limiter.can_process():
            break
        extractor.process_chat(chat, limiter)


def extract_questions(cfg: Config, *, max_months: int):
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    extractor = QuestionsExtractor(config=cfg, provider=provider)
    limiter = WorkLimiter(max_months)

    for chat in cfg.chats:
        if not limiter.can_process():
            break
        extractor.process_chat(chat, limiter)


def extract_cases(cfg: Config, *, max_months: int):
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    extractor = CasesExtractor(config=cfg, provider=provider)
    limiter = WorkLimiter(max_months)

    for chat in cfg.chats:
        if not limiter.can_process():
            break
        extractor.process_chat(chat, limiter)


def yaml_to_markdown(cfg: Config):
    builder = Yaml2Md(config=cfg, output_dir='site/content')
    for chat in cfg.chats:
        builder.process_chat(chat)


def categorize_questions(cfg: Config, *, max_months: int):
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    categorizer = QuestionsCategorizer(config=cfg, provider=provider)
    limiter = WorkLimiter(max_months)

    for chat in cfg.chats:
        if not limiter.can_process():
            break
        categorizer.process_chat(chat, limiter)


def normalize_questions(cfg: Config, *, max_categories: int):
    provider = AnthropicProvider(api_key=os.getenv('ANTHROPIC_API_KEY'), model=cfg.anthropic_model)
    normalizer = FAQNormalizer(config=cfg, provider=provider)
    limiter = WorkLimiter(max_categories)

    for chat in cfg.chats:
        normalizer.process_chat(chat, limiter)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Telegram digest')
    parser.add_argument('--config', '-c', default='config.yaml', help='Path to config file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    subparsers = parser.add_subparsers(dest='command', required=True)

    fetch_parser = subparsers.add_parser('fetch', help='Fetch messages from Telegram')
    fetch_parser.add_argument('--force-login', action='store_true', help='Force re-login even if session exists')

    # gen_parser = subparsers.add_parser('generate', help='Generate markdown from cache')
    # gen_parser.add_argument('--output', '-o', default='docs', help='Output directory')

    extract_facts_parser = subparsers.add_parser('extract-facts', help='Extract facts from messages')
    extract_facts_parser.add_argument('--max-months', type=int, default=1, help='Max months to process per run')

    extract_questions_parser = subparsers.add_parser('extract-questions', help='Extract questions from messages')
    extract_questions_parser.add_argument('--max-months', type=int, default=1, help='Max months to process per run')

    extract_cases_parser = subparsers.add_parser('extract-cases', help='Extract cases from messages')
    extract_cases_parser.add_argument('--max-months', type=int, default=1, help='Max months to process per run')

    yaml2md_parser = subparsers.add_parser('yaml2md', help='Build markdown from YAML')

    categorize_parser = subparsers.add_parser('categorize-questions', help='Categorize FAQ questions')
    categorize_parser.add_argument('--max-months', type=int, default=1, help='Max months to process per run')

    normalize_parser = subparsers.add_parser('normalize-questions', help='Normalize FAQ questions')
    normalize_parser.add_argument('--max-categories', type=int, default=1, help='Max categories to process per run')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(message)s',
        datefmt='[%X]',
        handlers=[RichHandler(markup=False, rich_tracebacks=True, enable_link_path=False)],
    )

    # Enable OpenAI logging
    logging.getLogger('openai').setLevel(logging.DEBUG)
    logging.getLogger('httpx').setLevel(logging.INFO)

    # Enable Anthropic logging
    logging.getLogger('anthropic').setLevel(logging.DEBUG)
    logging.getLogger('anthropic._base_client').setLevel(logging.DEBUG)

    load_dotenv()

    config_path = Path(args.config)
    with config_path.open(encoding='utf-8') as f:
        config = Config(**yaml.safe_load(f))

    if args.command == 'fetch':
        asyncio.run(fetch_messages(config, force_login=args.force_login))
    elif args.command == 'extract-facts':
        extract_facts(config, max_months=args.max_months)
    elif args.command == 'extract-questions':
        extract_questions(config, max_months=args.max_months)
    elif args.command == 'extract-cases':
        extract_cases(config, max_months=args.max_months)
    elif args.command == 'yaml2md':
        yaml_to_markdown(config)
    elif args.command == 'categorize-questions':
        categorize_questions(config, max_months=args.max_months)
    elif args.command == 'normalize-questions':
        normalize_questions(config, max_categories=args.max_categories)
