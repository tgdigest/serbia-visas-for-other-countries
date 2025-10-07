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

    def process_chat(self, chat: Chat):
        self.logger.info('Categorizing questions for: %s', chat.title)

        store = ChatStore(chat)
        all_questions = store.questions.get_all_questions()
        unique_questions = sorted({q.question for q in all_questions})

        self.logger.info('Found %d unique questions', len(unique_questions))

        response = self.provider.request(QuestionCategorizationResponse, [
            {
                'role': 'user',
                'content': format_json('Вопросы', unique_questions),
            },
            {
                'role': 'user',
                'content': format_json('Категории', self.config.faq_categories),
            },
            {
                'role': 'user',
                'content': self.jinja_env.get_template('prompts/categorize_questions.md.j2').render(),
            },
        ])

        store.save_yaml('questions-categorized.yaml', response)
        self.logger.info('Saved %d normalized questions', len(response.normalized))
