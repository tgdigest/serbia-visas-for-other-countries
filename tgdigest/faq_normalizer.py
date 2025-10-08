import logging

from .ai import AIProvider
from .helpers import WorkLimiter, format_json
from .models import CategoryNormalizedQuestions, Chat, Config, FAQNormalizationResponse
from .stores import ChatStore
from .templates import get_jinja_env


class FAQNormalizer:
    def __init__(self, config: Config, provider: AIProvider, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.provider = provider
        self.config = config
        self.jinja_env = get_jinja_env()

    def process_chat(self, chat: Chat, limiter: WorkLimiter):
        self.logger.info('Normalizing FAQ for: %s', chat.title)

        store = ChatStore(chat)
        unprocessed = store.normalized_faq.get_unprocessed_categories(self.config.faq_categories)

        if not unprocessed:
            self.logger.info('No categories need normalization')
            return

        for cat_slug in unprocessed:
            if not limiter.can_process():
                self.logger.info('Work limit reached (%s), stopping', limiter)
                break

            questions_md5, questions = store.normalized_faq.get_category_questions(cat_slug)

            self.logger.info('Normalizing %s: %d unique questions', cat_slug, len(questions))

            response = self.provider.request(FAQNormalizationResponse, [
                {
                    'role': 'user',
                    'content': format_json('Вопросы', questions),
                },
                {
                    'role': 'user',
                    'content': self.jinja_env.get_template('prompts/normalize_faq.md.j2').render(),
                },
            ])

            store.normalized_faq.save_category(cat_slug, CategoryNormalizedQuestions(
                category_slug=cat_slug,
                questions_text_md5=questions_md5,
                questions=response.questions,
            ))
            limiter.increment()
            self.logger.info('Saved %d normalized questions for %s (%s)', len(response.questions), cat_slug, limiter)
