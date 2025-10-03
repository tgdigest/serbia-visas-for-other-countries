import logging
from pathlib import Path

from .models import AutoConfig, Chat, Config
from .stores import ChatStore
from .templates import get_jinja_env


class AutoCollector:
    def __init__(self, config: Config, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.config = config
        self.docs_dir = Path(config.docs_dir)
        self.jinja_env = get_jinja_env()

    def process_chat(self, chat: Chat):
        self.logger.info('Processing chat: %s (%s)', chat.title, chat.url)
        store = ChatStore(chat.url)

        for auto_config in chat.auto:
            self._process_auto_config(store, auto_config, chat)

    def _process_auto_config(self, store: ChatStore, auto_config: AutoConfig, chat: Chat):
        self.logger.info('Processing auto config: %s -> %s', auto_config.keywords, auto_config.file)

        messages_by_month = {}
        for month in store.cache.get_all_months():
            month_data = store.cache.get_month(month)
            for msg in month_data.messages:
                if any(keyword.lower() in msg.text.lower() for keyword in auto_config.keywords):
                    if month not in messages_by_month:
                        messages_by_month[month] = []
                    messages_by_month[month].append(msg)

        total_messages = sum(len(msgs) for msgs in messages_by_month.values())
        self.logger.info('Found %d messages matching keywords', total_messages)

        file_path = self.docs_dir / auto_config.file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Group messages by year for template
        messages_by_year = {}
        for month, msgs in messages_by_month.items():
            messages_by_year.setdefault(month.year, {})[month] = msgs

        with file_path.open('w', encoding='utf-8') as f:
            f.write(self.jinja_env.get_template('auto.md.j2').render(
                title=auto_config.title,
                description=auto_config.description,
                keywords=auto_config.keywords,
                messages_by_year=messages_by_year,
                new_first=auto_config.new_first,
                chat_numeric_id=chat.get_chat_numeric_id(),
                topic_id=chat.get_topic_id(),
            ))
