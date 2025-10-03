from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from .helpers import compute_messages_hash
from .models import GeneratorState, MonthFacts, MonthMessages, MonthQuestions

T = TypeVar('T', bound=BaseModel)


@dataclass(frozen=True, order=True)
class Month:
    """Represents a year-month period."""
    year: int
    month: int

    @classmethod
    def from_string(cls, s: str) -> 'Month':
        """Parse from YYYY-MM format."""
        year, month = s.split('-')
        return cls(year=int(year), month=int(month))

    @classmethod
    def from_date(cls, dt: datetime) -> 'Month':
        """Create from datetime."""
        return cls(year=dt.year, month=dt.month)

    def to_string(self) -> str:
        """Convert to YYYY-MM format."""
        return f'{self.year:04d}-{self.month:02d}'

    def to_month_name(self) -> str:
        """Get month name in Russian."""
        names = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return names[self.month - 1]

    def __str__(self) -> str:
        return self.to_string()


class BaseMonthStore:
    """Base class for month-based storage. Subclasses should define class attributes."""

    subdir: str = None
    model_class: type[T] = None
    state_field: str | None = None

    def __init__(self, chat_store: 'ChatStore'):
        if self.subdir is None:
            msg = f'{self.__class__.__name__} must define subdir'
            raise ValueError(msg)
        if self.model_class is None:
            msg = f'{self.__class__.__name__} must define model_class'
            raise ValueError(msg)

        self.chat_store = chat_store

    @property
    def dir_path(self) -> Path:
        return self.chat_store.chat_dir / self.subdir

    def get_month(self, month: Month) -> T:
        """Load data for a specific month."""
        month_file = self.dir_path / f'{month.to_string()}.yaml'
        with month_file.open(encoding='utf-8') as f:
            return self.model_class(**yaml.safe_load(f))

    def save_month(self, month: Month, data: T | dict):
        """Save data for a specific month."""
        self.dir_path.mkdir(parents=True, exist_ok=True)
        month_file = self.dir_path / f'{month.to_string()}.yaml'

        data_dict = data.model_dump() if isinstance(data, BaseModel) else data

        with month_file.open('w', encoding='utf-8') as f:
            yaml.dump(
                data_dict,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False
            )

    def exists(self) -> bool:
        """Check if directory exists and has any data."""
        return self.dir_path.exists() and any(self.dir_path.glob('*.yaml'))

    def get_all_months(self) -> list[Month]:
        """Get all available months sorted."""
        if not self.dir_path.exists():
            return []

        months = []
        for yaml_file in sorted(self.dir_path.glob('*.yaml')):
            try:
                month = Month.from_string(yaml_file.stem)
                months.append(month)
            except ValueError:
                continue

        return sorted(months)

    def get_unprocessed_months(self) -> list[Month]:
        """Get months that need processing based on md5 hash comparison."""
        if not self.state_field:
            return self.get_all_months()

        all_months = self.chat_store.cache.get_all_months()
        if not all_months:
            return []

        unprocessed = []
        for month in all_months:
            cache_data = self.chat_store.cache.get_month(month)
            cache_md5 = cache_data.md5

            month_file = self.dir_path / f'{month.to_string()}.yaml'
            if not month_file.exists():
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
        month_file = self.dir_path / f'{month.to_string()}.yaml'

        if month_file.exists():
            existing_data = self.get_month(month)
            existing_messages = existing_data.messages

        existing_ids = {msg.id for msg in existing_messages}
        for msg in new_messages:
            if msg.id not in existing_ids:
                existing_messages.append(msg)

        existing_messages.sort(key=lambda x: x.id)

        md5 = compute_messages_hash(existing_messages)
        data = MonthMessages(month=month.to_string(), md5=md5, messages=existing_messages)
        self.save_month(month, data)


class FactsMonthStore(BaseMonthStore):
    """Storage for extracted facts."""
    subdir = 'facts'
    model_class = MonthFacts
    state_field = 'last_extracted_facts_month'

    def save_with_source(self, month: Month, facts: list[str], source_md5: str):
        """Save facts with source hash."""
        data = MonthFacts(month=month.to_string(), md5=source_md5, facts=facts)
        self.save_month(month, data)


class QuestionsMonthStore(BaseMonthStore):
    """Storage for extracted questions."""
    subdir = 'questions'
    model_class = MonthQuestions
    state_field = 'last_extracted_questions_month'


class ChatStore:
    """Manages all data for a chat (cache, facts, questions, state)."""

    def __init__(self, url: str, base_path: str = '.'):
        self.url = url
        self.base_path = Path(base_path)
        self.chat_dir = self._get_chat_dir()

        self.cache = CacheMonthStore(self)
        self.facts = FactsMonthStore(self)
        self.questions = QuestionsMonthStore(self)

    def _get_chat_dir(self) -> Path:
        url_parts = self.url.replace('https://', '').split('/')
        return self.base_path / Path(*url_parts)

    @property
    def state_file(self) -> Path:
        return self.chat_dir / 'state.yaml'

    def get_state(self) -> GeneratorState:
        """Load state from state.yaml."""
        if not self.state_file.exists():
            return GeneratorState()
        with self.state_file.open(encoding='utf-8') as f:
            return GeneratorState(**(yaml.safe_load(f) or {}))

    def save_state(self, state: GeneratorState):
        """Save state to state.yaml."""
        self.chat_dir.mkdir(parents=True, exist_ok=True)
        with self.state_file.open('w', encoding='utf-8') as f:
            yaml.dump(state.model_dump(), f, allow_unicode=True)
