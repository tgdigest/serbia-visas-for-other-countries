import datetime
import logging
import re
from pathlib import Path

from .ai import AIProvider
from .diff_parser import DiffParser
from .helpers import format_json
from .models import Chat, Config, DocumentationUpdate
from .stores import ChatStore
from .templates import get_jinja_env


class Generator:
    def __init__(self, config: Config, provider: AIProvider, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.provider = provider
        self.config = config
        self.docs_dir = Path(config.docs_dir)
        self.jinja_env = get_jinja_env()

    async def process_chat(self, chat: Chat, max_months_per_run: int):
        self.logger.info('Processing chat: %s (%s)', chat.title, chat.url)

        store = ChatStore(chat.url)

        # Get unprocessed months based on state
        state = store.get_state()
        all_months = store.cache.get_all_months()

        if not all_months:
            self.logger.info('No months to process')
            return

        if state.last_processed_month:
            unprocessed_months = [m for m in all_months if m.to_string() > state.last_processed_month]
        else:
            unprocessed_months = all_months

        if not unprocessed_months:
            self.logger.info('No new months to process')
            return

        self.logger.info('Found %d unprocessed months: %s', len(unprocessed_months), unprocessed_months)

        months_to_process = unprocessed_months[:max_months_per_run]
        self.logger.info('Will process %d months: %s', len(months_to_process), months_to_process)

        docs = self._load_docs(chat)
        for month in months_to_process:
            self.logger.info('Processing month: %s', month)

            month_data = store.cache.get_month(month)
            if not month_data.messages:
                self.logger.warning('No messages found for month %s, skipping', month)
                continue

            updates = self.provider.request(DocumentationUpdate, [
                {
                    'role': 'system',
                    'content': 'Твоя задача: поддерживать базу знаний, основываясь новых сообщениях из чата.',
                },
                {
                    'role': 'user',
                    'content': format_json('База знаний', docs),
                },
                {
                    'role': 'user',
                    'content': format_json('Новые сообщения', {
                        'month': month_data.month,
                        'messages': [m.model_dump() for m in month_data.messages],
                    })
                },
                {
                    'role': 'user',
                    'content': self.jinja_env.get_template('update_docs.md.j2').render(
                        chat=chat,
                        current_date=datetime.datetime.now(tz=datetime.UTC).date().strftime('%Y-%m-%d'),
                        extra_prompt=self.config.extra_prompt,
                    ),
                },
            ])

            for file_diff in updates.diffs:
                file_path = self.docs_dir / file_diff.path
                self._apply_diff(file_path, file_diff.diff)

            state.last_processed_month = month.to_string()
            store.save_state(state)
            self.logger.info('Updated state to %s', month)

    async def reorganize_docs(self, chat: Chat):
        self.logger.info('Reorganizing docs for chat: %s', chat.title)

        updates = self.provider.request(DocumentationUpdate, [
            {
                'role': 'system',
                'content': 'Твоя задача: упорядочивать базу знаний',
            },
            {
                'role': 'user',
                'content': format_json('База знаний', self._load_docs(chat)),
            },
            {
                'role': 'user',
                'content': self.jinja_env.get_template('reorganize_docs.md.j2').render(
                    extra_prompt=self.config.extra_prompt,
                ),
            },
        ])

        for file_diff in updates.diffs:
            file_path = self.docs_dir / file_diff.path
            self._apply_diff(file_path, file_diff.diff)

    def _apply_diff(self, file_path: Path, diff_content: str):
        self.logger.info('Applying diff to %s:\n%s', file_path, diff_content)

        with file_path.open(encoding='utf-8') as f:
            content = f.read()

        patched_content = DiffParser().apply(content, diff_content)
        patched_content = self._post_process_markdown(patched_content)

        with file_path.open('w', encoding='utf-8') as f:
            f.write(patched_content)

        self.logger.info('Successfully applied diff to %s', file_path)

    def _post_process_markdown(self, content: str) -> str:
        # Replace **text** on separate lines with ### text
        content = re.sub(r'^\*\*([^*]+)\*\*$', r'### \1', content, flags=re.MULTILINE)
        # Replace 3+ consecutive newlines with exactly 2
        return re.sub(r'\n{3,}', '\n\n', content)

    def _load_docs(self, chat: Chat) -> dict[str, str]:
        auto_files = self.config.get_auto_files()
        docs = {}

        if not chat.files:
            msg = f"Chat '{chat.title}' has no files specified in config"
            raise ValueError(msg)

        for pattern in chat.files:
            if '*' in pattern or '?' in pattern:
                matched_files = list(self.docs_dir.glob(pattern))
                if not matched_files:
                    msg = f'No files found for pattern: {pattern}'
                    raise FileNotFoundError(msg)
                for file_path in matched_files:
                    rel_path = str(file_path.relative_to(self.docs_dir))
                    if rel_path in auto_files:
                        continue
                    with file_path.open(encoding='utf-8') as f:
                        docs[rel_path] = f.read()
            else:
                if pattern in auto_files:
                    continue
                full_path = self.docs_dir / pattern
                if not full_path.exists():
                    msg = f'File not found: {pattern}'
                    raise FileNotFoundError(msg)
                with full_path.open(encoding='utf-8') as f:
                    docs[pattern] = f.read()

        return docs
