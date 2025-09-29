from abc import ABC, abstractmethod
from typing import Any, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class AIProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def request(self, response_format: Type[T], messages: list[dict[str, Any]]) -> T:
        pass


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key)

    def request(self, response_format: Type[T], messages: list[dict[str, Any]]) -> T:
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_format,
            timeout=600,
            temperature=0,
        )
        return response.choices[0].message.parsed