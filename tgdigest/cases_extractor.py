import logging

from .ai import AIProvider
from .helpers import WorkLimiter, format_json
from .models import Chat, Config, CasesResponse, MessagesRequest
from .stores import ChatStore
from .templates import get_jinja_env


class CasesExtractor:
    def __init__(self, config: Config, provider: AIProvider, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.provider = provider
        self.config = config
        self.jinja_env = get_jinja_env()

    def process_chat(self, chat: Chat, limiter: WorkLimiter):
        self.logger.info('Processing chat: %s (%s)', chat.title, chat.url)

        store = ChatStore(chat.url)
        unprocessed_months = store.cases.get_unprocessed_months()

        if not unprocessed_months:
            self.logger.info('No new months to extract cases from')
            return

        for month in unprocessed_months:
            if not limiter.can_process():
                self.logger.info('Work limit reached (%s), stopping', limiter)
                break
            self.logger.info('Extracting cases for month: %s', month)

            month_data = store.cache.get_month(month)
            if not month_data.messages:
                self.logger.info('No messages found for month %s, skipping', month)
                continue

            request = MessagesRequest(month=month_data.month, messages=month_data.messages)
            response = self.provider.request(CasesResponse, [
                {
                    'role': 'user',
                    'content': format_json('Сообщения', request.model_dump()),
                },
                {
                    'role': 'user',
                    'content': self.jinja_env.get_template('extract_cases.md.j2').render(),
                },
            ])

            store.cases.save_with_source(month, response.cases, month_data.md5)
            limiter.increment()
            self.logger.info('Saved %d cases for %s (%s)', len(response.cases), month, limiter)
