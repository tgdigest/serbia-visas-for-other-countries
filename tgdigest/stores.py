from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .helpers import compute_messages_hash, compute_text_hash
from .models import (
    CategorizedQuestion,
    CategoryNormalizedQuestions,
    Chat,
    Month,
    MonthCases,
    MonthCategorizedQuestions,
    MonthFacts,
    MonthMessages,
    MonthQuestions,
    ReferencedSummary,
)

T: TypeVar = TypeVar('T', bound=BaseModel)


class BaseMonthStore:
    """Base class for month-based storage. Subclasses should define class attributes."""

    subdir: str = None
    model_class: type[T] = None

    def __init__(self, chat_store: 'ChatStore'):
        if self.subdir is None:
            msg = f'{self.__class__.__name__} must define subdir'
            raise ValueError(msg)

        if self.model_class is None:
            msg = f'{self.__class__.__name__} must define model_class'
            raise ValueError(msg)

        self.chat_store = chat_store
        self._cache = {}

    @property
    def dir_path(self) -> Path:
        return self.chat_store.chat_dir / self.subdir

    def get_month_file(self, month: Month) -> Path:
        return self.dir_path / f'{month.to_string()}.yaml'

    def get_month(self, month: Month) -> T:
        if month not in self._cache:
            with self.get_month_file(month).open(encoding='utf-8') as f:
                self._cache[month] = self.model_class(**yaml.safe_load(f))
        return self._cache[month]

    def save_month(self, month: Month, data: T):
        self.chat_store.save_yaml(self.get_month_file(month), data)

    def get_all_months(self) -> list[Month]:
        months = []
        if self.dir_path.exists():
            for yaml_file in sorted(self.dir_path.glob('*.yaml')):
                try:
                    months.append(Month.from_string(yaml_file.stem))
                except ValueError:
                    continue
        return sorted(months)

    def get_unprocessed_months(self) -> list[Month]:
        all_months = self.chat_store.cache.get_all_months()
        if not all_months:
            return []

        unprocessed = []
        for month in all_months:
            cache_data = self.chat_store.cache.get_month(month)
            cache_md5 = cache_data.md5

            if not self.get_month_file(month).exists():
                unprocessed.append(month)
                continue

            processed_data = self.get_month(month)
            if processed_data.md5 != cache_md5:
                unprocessed.append(month)

        return unprocessed


class CacheMonthStore(BaseMonthStore):
    """Storage for raw messages from Telegram."""
    subdir = 'cache'
    model_class = MonthMessages

    def append_messages(self, month: Month, new_messages: list):
        """Append messages to existing month data, merging by ID."""
        existing_messages = []

        if self.get_month_file(month).exists():
            existing_data = self.get_month(month)
            existing_messages = existing_data.messages

        existing_ids = {msg.id for msg in existing_messages}
        for msg in new_messages:
            if msg.id not in existing_ids:
                existing_messages.append(msg)

        existing_messages.sort(key=lambda x: x.id)

        md5 = compute_messages_hash(existing_messages)
        self.save_month(month, MonthMessages(
            month=month.to_string(),
            md5=md5,
            messages=existing_messages,
        ))


class FactsMonthStore(BaseMonthStore):
    """Storage for extracted facts."""
    subdir = 'facts'
    model_class = MonthFacts

    def save_with_source(self, month: Month, facts: list[str], source_md5: str):
        """Save facts with source hash."""
        self.save_month(month, MonthFacts(
            month=month.to_string(),
            md5=source_md5,
            facts=facts,
        ))


class QuestionsMonthStore(BaseMonthStore):
    """Storage for extracted questions."""
    subdir = 'questions'
    model_class = MonthQuestions

    def save_with_source(self, month: Month, questions: list, source_md5: str):
        self.save_month(month, MonthQuestions(
            month=month.to_string(),
            md5=source_md5,
            questions=questions,
        ))

    def get_all_questions(self) -> list:
        res = []
        for month in self.get_all_months():
            month_data = self.get_month(month)
            res.extend(q for q in month_data.questions if q.answers)
        return res

    def get_all_answers_for_question(self, question_text: str, chat) -> list[ReferencedSummary]:
        res = []
        for month in self.get_all_months():
            for q in self.get_month(month).questions:
                if q.question != question_text:
                    continue
                res.extend(
                    ReferencedSummary(
                        text=answer.text,
                        message_ids=answer.message_ids,
                        sender=answer.sender,
                        month=month,
                        message_links=answer.get_message_links(chat),
                    )
                    for answer in q.answers
                )
        return res


class CasesMonthStore(BaseMonthStore):
    """Storage for extracted cases."""
    subdir = 'cases'
    model_class = MonthCases

    def save_with_source(self, month: Month, cases: list, source_md5: str):
        """Save cases with source hash."""
        self.save_month(month, MonthCases(
            month=month.to_string(),
            md5=source_md5,
            cases=cases,
        ))


class CategorizedQuestionsMonthStore(BaseMonthStore):
    """Storage for categorized questions."""
    subdir = 'questions-categorized'
    model_class = MonthCategorizedQuestions

    def save_with_source(self, month: Month, questions: list, source_md5: str):
        self.save_month(month, MonthCategorizedQuestions(
            month=month.to_string(),
            md5=source_md5,
            questions=questions,
        ))

    def get_unprocessed_months(self) -> list[Month]:
        all_months = self.chat_store.questions.get_all_months()
        if not all_months:
            return []

        unprocessed = []
        for month in all_months:
            questions_data = self.chat_store.questions.get_month(month)
            questions_md5 = questions_data.md5

            if not self.get_month_file(month).exists():
                unprocessed.append(month)
                continue

            if self.get_month(month).md5 != questions_md5:
                unprocessed.append(month)

        return unprocessed

    def get_all_categorized(self) -> list[CategorizedQuestion]:
        all_categorized = []
        for month in self.get_all_months():
            month_data = self.get_month(month)
            all_categorized.extend(month_data.questions)
        return all_categorized


class NormalizedFAQStore:
    def __init__(self, chat_store: 'ChatStore'):
        self.chat_store = chat_store
        self._cache = {}

    def get_category_file(self, category_slug: str | None) -> Path:
        if category_slug is None:
            return self.chat_store.chat_dir / 'faq-normalized.yaml'
        return self.chat_store.chat_dir / 'faq-normalized' / f'{category_slug}.yaml'

    def save_category(self, category_slug: str | None, data: CategoryNormalizedQuestions):
        self.chat_store.save_yaml(self.get_category_file(category_slug), data)

    def load_category(self, category_slug: str | None) -> CategoryNormalizedQuestions:
        if category_slug not in self._cache:
            if self.get_category_file(category_slug).exists():
                with self.get_category_file(category_slug).open(encoding='utf-8') as f:
                    self._cache[category_slug] = CategoryNormalizedQuestions(**yaml.safe_load(f))
            else:
                self._cache[category_slug] = CategoryNormalizedQuestions(
                    category_slug=category_slug,
                    questions_text_md5='',
                    questions=[],
                )
        return self._cache[category_slug]

    def get_unprocessed_categories(self, faq_categories: list) -> list[str | None]:
        return [
            cat.slug if cat else None for cat in faq_categories
            if self.load_category(cat.slug if cat else None).questions_text_md5 != self.compute_category_md5(cat.slug if cat else None)
        ]

    def get_category_questions(self, category_slug: str | None) -> tuple[str, list[str]]:
        all_questions = []

        if category_slug is None:
            for month in self.chat_store.questions.get_all_months():
                month_data = self.chat_store.questions.get_month(month)
                all_questions.extend(q.question for q in month_data.questions if q.answers)
        else:
            for month in self.chat_store.categorized_questions.get_all_months():
                month_data = self.chat_store.categorized_questions.get_month(month)
                all_questions.extend(
                    cat_q.question
                    for cat_q in month_data.questions
                    if cat_q.category_slug == category_slug and not cat_q.is_date_specific
                )

        return compute_text_hash(all_questions), sorted(set(all_questions))

    def compute_category_md5(self, category_slug: str | None) -> str:
        return self.get_category_questions(category_slug)[0]

    def normalize_question(self, category_slug: str | None, question: str) -> str:
        normalized = self.load_category(category_slug)
        for norm_q in normalized.questions:
            if question in norm_q.source_questions:
                return norm_q.normalized_question
        return question


class ChatStore:
    """Manages all data for a chat (cache, facts, questions)."""

    def __init__(self, chat: Chat):
        self.chat = chat
        self.chat_dir = Path('store') / chat.slug

        self.cache = CacheMonthStore(self)
        self.facts = FactsMonthStore(self)
        self.questions = QuestionsMonthStore(self)
        self.cases = CasesMonthStore(self)
        self.categorized_questions = CategorizedQuestionsMonthStore(self)
        self.normalized_faq = NormalizedFAQStore(self)

    def save_yaml(self, file_path: Path, data: BaseModel):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open('w', encoding='utf-8') as f:
            yaml.dump(
                data.model_dump(exclude_defaults=True),
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
