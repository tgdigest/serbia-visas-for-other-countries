import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from anthropic import Anthropic
from openai import OpenAI
from pydantic import BaseModel
from pydantic_core import ValidationError

T = TypeVar('T', bound=BaseModel)


class AIProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def request(self, response_format: type[T], messages: list[dict[str, Any]]) -> T:
        pass


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key)

    def request(self, response_format: type[T], messages: list[dict[str, Any]]) -> T:
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_format,
            timeout=600,
            temperature=0,
        )
        return response.choices[0].message.parsed


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self.client = Anthropic(api_key=api_key)

    def request(self, response_format: type[T], messages: list[dict[str, Any]]) -> T:
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                anthropic_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })

        tool_definition = {
            'name': 'structured_output',
            'description': f'Generate structured output using {response_format.__name__}',
            'input_schema': response_format.model_json_schema()
        }

        kwargs = {
            'model': self.model,
            'max_tokens': 8192,
            'messages': anthropic_messages,
            'tools': [tool_definition],
            'tool_choice': {'type': 'tool', 'name': 'structured_output'},
            'temperature': 0,
        }
        if system_message:
            kwargs['system'] = system_message

        response = self.client.messages.create(**kwargs)

        tool_use = response.content[0]
        input_data = tool_use.input

        if isinstance(input_data, str):
            input_data = json.loads(input_data)

        try:
            return response_format(**input_data)
        except ValidationError as e:
            msg = f'Failed to parse response: {input_data}'
            raise ValueError(msg) from e
