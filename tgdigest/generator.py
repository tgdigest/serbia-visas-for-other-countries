import datetime
import json
import logging
from pathlib import Path

from openai import OpenAI

from .cache import MessagesCache
from .diff_parser import DiffParser
from .models import Chat, Config, DocumentationUpdate, GeneratorState, MonthMessages
from .templates import get_jinja_env


class Generator:
    model = 'gpt-4.1-2025-04-14'

    def __init__(self, config: Config, openai_api_key: str, max_months_per_run: int, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        # Enable OpenAI logging
        logging.getLogger('openai').setLevel(logging.DEBUG)
        logging.getLogger('httpx').setLevel(logging.INFO)

        self.client = OpenAI(api_key=openai_api_key)
        self.config = config
        self.docs_dir = Path(config.docs_dir)
        self.max_months_per_run = max_months_per_run
        self.jinja_env = get_jinja_env()

    def _load_docs(self) -> dict[str, str]:
        auto_files = self.config.get_auto_files()
        
        docs = {}
        for md_file in self.docs_dir.rglob('*.md'):
            rel_path = md_file.relative_to(self.docs_dir)
            if str(rel_path) in auto_files:
                continue
            with md_file.open(encoding='utf-8') as f:
                docs[str(rel_path)] = f.read()
        
        for pages_file in self.docs_dir.rglob('.pages'):
            rel_path = pages_file.relative_to(self.docs_dir)
            with pages_file.open(encoding='utf-8') as f:
                docs[str(rel_path)] = f.read()
        return docs

    def _request_updates(self, docs: dict[str, str], month_messages: MonthMessages,
                         chat: Chat) -> DocumentationUpdate:
        self.logger.info('Requesting documentation updates for month %s with %d messages',
                        month_messages.month, len(month_messages.messages))

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[{
                'role': 'system',
                'content': self.jinja_env.get_template('update_docs.j2').render(
                    chat=chat,
                    current_date=datetime.date.today().strftime('%Y-%m-%d'),
                ),
            }, {
                'role': 'user',
                'content': self._json('Текущая документация', docs),
            }, {
                'role': 'user',
                'content': self._json('Новые сообщения', month_messages.model_dump())
            }],
            response_format=DocumentationUpdate,
        )

        parsed = response.choices[0].message.parsed
        self.logger.info('Received %d diffs from OpenAI', len(parsed.diffs))
        return parsed

    def _json(self, title, v):
        return f'{title}:\n```json\n{json.dumps(v, ensure_ascii=False)}\n```\n'

    def _apply_diff(self, file_path: Path, diff_content: str):
        self.logger.info('Applying diff to %s:\n%s', file_path, diff_content)

        with file_path.open(encoding='utf-8') as f:
            content = f.read()

        parser = DiffParser()
        patched_content = parser.apply(content, diff_content)

        with file_path.open('w', encoding='utf-8') as f:
            f.write(patched_content)

        self.logger.info('Successfully applied diff to %s', file_path)

    async def process_chat(self, chat: Chat):
        self.logger.info('Processing chat: %s (%s)', chat.title, chat.url)

        cache = MessagesCache(chat.url)
        unprocessed_months = cache.get_unprocessed_months()

        if not unprocessed_months:
            self.logger.info('No new months to process')
            return

        self.logger.info('Found %d unprocessed months: %s', len(unprocessed_months), unprocessed_months)

        months_to_process = unprocessed_months[:self.max_months_per_run]
        self.logger.info('Will process %d months: %s', len(months_to_process), months_to_process)

        docs = self._load_docs()

        for month in months_to_process:
            self.logger.info('Processing month: %s', month)

            messages = cache.get_messages_for_month(month)
            if not messages:
                self.logger.warning('No messages found for month %s, skipping', month)
                continue

            month_messages = MonthMessages(month=month, messages=messages)
            updates = self._request_updates(docs, month_messages, chat)

            for file_diff in updates.diffs:
                file_path = self.docs_dir / file_diff.path
                self._apply_diff(file_path, file_diff.diff)

            state = GeneratorState(last_processed_month=month)
            cache.save_generator_state(state)
            self.logger.info('Updated state to %s', month)
