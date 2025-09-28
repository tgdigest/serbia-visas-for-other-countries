import re

from pydantic import BaseModel


class Message(BaseModel):
    id: int
    sender: int
    text: str


class MonthMessages(BaseModel):
    month: str  # "2022-12"
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

    def get_auto_files(self) -> set[str]:
        return {auto_config.file for chat in self.chats for auto_config in chat.auto}


class FileDiff(BaseModel):
    path: str
    diff: str


class DocumentationUpdate(BaseModel):
    diffs: list[FileDiff]


class GeneratorState(BaseModel):
    last_processed_month: str | None = None
