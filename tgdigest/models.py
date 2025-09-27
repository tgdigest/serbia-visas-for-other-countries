import re
from typing import List

from pydantic import BaseModel


class Message(BaseModel):
    id: int
    sender: int
    text: str


class MonthMessages(BaseModel):
    month: str  # "2022-12"
    messages: List[Message]


class Chat(BaseModel):
    title: str
    url: str

    def get_chat_id(self) -> int:
        match = re.match(r"https://t\.me/c/(\d+)/(\d+)", self.url)
        if not match:
            msg = f"Invalid chat URL format: {self.url}. Expected format: https://t.me/c/<chat_id>/<message_id>"
            raise ValueError(msg)
        return -1000000000000 - int(match.group(1))

    def get_topic_id(self) -> int:
        match = re.match(r"https://t\.me/c/(\d+)/(\d+)", self.url)
        if not match:
            msg = f"Invalid chat URL format: {self.url}. Expected format: https://t.me/c/<chat_id>/<message_id>"
            raise ValueError(msg)
        return int(match.group(2))


class Config(BaseModel):
    chats: List[Chat]
