import logging

from .ai import AIProvider
from .helpers import format_json
from .models import Chat, Config, QuestionCategorizationResponse
from .stores import ChatStore
from .templates import get_jinja_env


class QuestionsCategorizer:
    def __init__(self, config: Config, provider: AIProvider, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.provider = provider
        self.config = config
        self.jinja_env = get_jinja_env()

    def process_chat(self, chat: Chat, limiter):
        self.logger.info('Categorizing questions for: %s', chat.title)

        store = ChatStore(chat)
        unprocessed_months = store.categorized_questions.get_unprocessed_months()

        if not unprocessed_months:
            self.logger.info('No new months to categorize')
            return

        categories_with_id = [{'id': i + 1, **cat.model_dump()} for i, cat in enumerate(self.config.faq_categories)]

        for month in unprocessed_months:
            if not limiter.can_process():
                self.logger.info('Work limit reached (%s), stopping', limiter)
                break

            month_data = store.questions.get_month(month)
            month_questions = [q.question for q in month_data.questions]

            if not month_questions:
                continue

            unique_questions = sorted(set(month_questions))
            self.logger.info('Processing %s: %d unique questions', month, len(unique_questions))

            questions_indexed = [{'id': i + 1, 'question': q} for i, q in enumerate(unique_questions)]

            response = self.provider.request(QuestionCategorizationResponse, [
                {
                    'role': 'user',
                    'content': format_json('Вопросы', questions_indexed),
                },
                {
                    'role': 'user',
                    'content': format_json('Категории', categories_with_id),
                },
                {
                    'role': 'user',
                    'content': self.jinja_env.get_template('prompts/categorize_questions.md.j2').render(),
                },
            ])

            result = response.expand(questions_indexed)
            self._validate_completeness(response, questions_indexed, month)
            store.categorized_questions.save_with_source(month, result.questions, month_data.md5)
            limiter.increment()
            self.logger.info('Saved %d categorized questions for %s (%s)', len(result.questions), month, limiter)

    def _validate_completeness(self, response, questions_indexed, month):
        expected_ids = {q['id'] for q in questions_indexed}
        actual_ids = {q.question_id for q in response.questions}

        if expected_ids != actual_ids:
            missing = expected_ids - actual_ids
            extra = actual_ids - expected_ids
            msg = f'Categorization mismatch for {month}: missing={missing}, extra={extra}'
            raise ValueError(msg)
