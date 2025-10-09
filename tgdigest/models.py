import re
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel


@dataclass(frozen=True, order=True)
class Month:
    year: int
    month: int

    @classmethod
    def from_string(cls, s: str) -> 'Month':
        year, month = s.split('-')
        return cls(year=int(year), month=int(month))

    @classmethod
    def from_date(cls, dt: datetime) -> 'Month':
        return cls(year=dt.year, month=dt.month)

    def to_string(self) -> str:
        return f'{self.year:04d}-{self.month:02d}'

    def to_month_name(self) -> str:
        names = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return names[self.month - 1]


class Message(BaseModel):
    id: int
    sender: int
    text: str


class MessagesRequest(BaseModel):
    """Request model for AI - messages without storage metadata."""
    month: str
    messages: list[Message]


class MessageLink(BaseModel):
    message_id: int
    chat: 'Chat'

    def get_url(self) -> str:
        return f'{self.chat.url}/{self.message_id}'

    def get_title(self) -> str:
        return f'#{self.message_id}'


class Summary(BaseModel):
    text: str
    message_ids: list[int]
    sender: int

    def get_message_links(self, chat: 'Chat') -> list[MessageLink]:
        return [MessageLink(message_id=msg_id, chat=chat) for msg_id in self.message_ids]


class ReferencedSummary(Summary):
    month: Month
    message_links: list[MessageLink]

    @property
    def year(self) -> int:
        return self.month.year

    @property
    def sort_key(self) -> tuple:
        return -self.month.year, self.text

    def __hash__(self):
        return hash(self.sort_key)


class FactsResponse(BaseModel):
    """Response model from AI for facts extraction."""
    facts: list[Summary]


class Question(BaseModel):
    question: str
    answers: list[Summary]


class QuestionsResponse(BaseModel):
    """Response model from AI for questions extraction."""
    questions: list[Question]


class MonthMessages(BaseModel):
    month: str  # "2022-12"
    md5: str
    messages: list[Message]


class Chat(BaseModel):
    title: str
    url: str
    slug: str
    description: str
    faq: bool
    cases: bool

    def _parse_url(self):
        match = re.match(r'https://t\.me/c/(\d+)/(\d+)', self.url)
        if not match:
            msg = f'Invalid chat URL format: {self.url}. Expected format: https://t.me/c/<chat_id>/<message_id>'
            raise ValueError(msg)
        return match

    def get_chat_numeric_id(self) -> int:
        match = self._parse_url()
        return int(match.group(1))

    def get_chat_id(self) -> int:
        return -1000000000000 - self.get_chat_numeric_id()

    def get_topic_id(self) -> int:
        match = self._parse_url()
        return int(match.group(2))

    def get_page_title(self) -> str:
        return self.title


class FAQCategory(BaseModel):
    title: str
    slug: str
    description: str


class Config(BaseModel):
    extra_prompt: str = ''
    faq_categories: list[FAQCategory]
    chats: list[Chat]
    docs_dir: str = 'docs'
    openai_model: str = 'gpt-4.1-2025-04-14'
    anthropic_model: str

    def get_faq_category_by_slug(self, slug: str) -> FAQCategory:
        return next(c for c in self.faq_categories if c.slug == slug)



class FileDiff(BaseModel):
    path: str
    diff: str


class DocumentationUpdate(BaseModel):
    diffs: list[FileDiff]


class MonthFacts(BaseModel):
    month: str  # "2022-12"
    md5: str
    facts: list[Summary]


class MonthQuestions(BaseModel):
    month: str  # "2022-12"
    md5: str
    questions: list[Question]


class Case(BaseModel):
    is_approved: bool
    consulate_city: str | None = None
    summary: Summary


class CasesResponse(BaseModel):
    """Response model from AI for cases extraction."""
    cases: list[Case]


class MonthCases(BaseModel):
    month: str  # "2022-12"
    md5: str
    cases: list[Case]

    def count_approved(self) -> int:
        return sum(1 for c in self.cases if c.is_approved)

    def count_rejected(self) -> int:
        return sum(1 for c in self.cases if not c.is_approved)


class CategorizedQuestionRaw(BaseModel):
    question_id: int
    category_slug: str
    is_date_specific: bool


class CategorizedQuestion(BaseModel):
    question: str
    category_slug: str
    is_date_specific: bool = False


class QuestionCategorizationResponse(BaseModel):
    questions: list[CategorizedQuestionRaw]

    def expand(self, questions_indexed: list[dict]) -> 'QuestionCategorizationResult':
        expanded = []
        for q in self.questions:
            try:
                question = questions_indexed[q.question_id - 1]['question']
            except IndexError as e:
                msg = f'Invalid question_id={q.question_id}, max={len(questions_indexed)}'
                raise ValueError(msg) from e

            expanded.append(CategorizedQuestion(
                question=question,
                category_slug=q.category_slug,
                is_date_specific=q.is_date_specific,
            ))

        return QuestionCategorizationResult(questions=expanded)


class QuestionCategorizationResult(BaseModel):
    questions: list[CategorizedQuestion]


class MonthCategorizedQuestions(BaseModel):
    month: str
    md5: str
    questions: list[CategorizedQuestion]


class NormalizedFAQQuestion(BaseModel):
    normalized_question: str
    source_questions: list[str]


class FAQNormalizationResponse(BaseModel):
    questions: list[NormalizedFAQQuestion]


class CategoryNormalizedQuestions(BaseModel):
    category_slug: str
    questions_text_md5: str
    questions: list[NormalizedFAQQuestion]
