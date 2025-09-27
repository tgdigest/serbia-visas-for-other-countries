import re
from pydantic import BaseModel
from typing import List

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
        match = re.match(r'https://t\.me/c/(\d+)/(\d+)', self.url)
        if match:
            return -1000000000000 - int(match.group(1))
        return None
    
    def get_topic_id(self) -> int:
        match = re.match(r'https://t\.me/c/(\d+)/(\d+)', self.url)
        if match:
            return int(match.group(2))
        return None
    
class Config(BaseModel):
    chats: List[Chat]