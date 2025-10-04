import re

from pydantic import BaseModel


class Message(BaseModel):
    id: int
    sender: int
    text: str


class MessagesRequest(BaseModel):
    """Request model for AI - messages without storage metadata."""
    month: str
    messages: list[Message]


class Summary(BaseModel):
    text: str
    message_ids: list[int]


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


class AutoConfig(BaseModel):
    keywords: list[str]
    file: str
    title: str
    new_first: bool = True
    description: str | None = None


class Chat(BaseModel):
    title: str
    url: str
    auto: list[AutoConfig] = []
    files: list[str] = []

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


class Config(BaseModel):
    extra_prompt: str = ''
    chats: list[Chat]
    docs_dir: str = 'docs'
    openai_model: str = 'gpt-4.1-2025-04-14'
    anthropic_model: str

    def get_auto_files(self) -> set[str]:
        return {auto_config.file for chat in self.chats for auto_config in chat.auto}


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
