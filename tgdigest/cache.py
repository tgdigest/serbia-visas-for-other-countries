from pathlib import Path

import yaml

from .models import GeneratorState, Message, MonthMessages


class MessagesCache:
    def __init__(self, url: str, base_path: str = 'cache'):
        self.url = url
        self.base_path = Path(base_path)
        self.cache_dir = self._get_cache_dir()

    def _get_cache_dir(self) -> Path:
        url_parts = self.url.replace('https://', '').split('/')
        return self.base_path / Path(*url_parts)

    @property
    def generator_state_file(self) -> Path:
        return self.cache_dir / 'generator-state.yaml'

    def exists(self) -> bool:
        return self.cache_dir.exists() and any(self.cache_dir.glob('*.yaml'))

    def get_last_message_id(self) -> int | None:
        if not self.cache_dir.exists():
            return None

        yaml_files = sorted(self.cache_dir.glob('*.yaml'), reverse=True)
        if not yaml_files:
            return None

        with yaml_files[0].open(encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not data:
                return None

            month_messages = MonthMessages(**data)
            if not month_messages.messages:
                return None

            return month_messages.messages[-1].id

    def save_month(self, key: str, messages: list[Message]):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        file_path = self.cache_dir / f'{key}.yaml'

        existing_messages = []
        if file_path.exists():
            with file_path.open(encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    month_data = MonthMessages(**data)
                    existing_messages = month_data.messages

        existing_ids = {msg.id for msg in existing_messages}
        for msg in messages:
            if msg.id not in existing_ids:
                existing_messages.append(msg)

        existing_messages.sort(key=lambda x: x.id)
        month_data = MonthMessages(month=key, messages=existing_messages)

        with file_path.open('w', encoding='utf-8') as f:
            yaml.dump(
                month_data.model_dump(),
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False
            )

    def get_generator_state(self) -> GeneratorState:
        if not self.generator_state_file.exists():
            return GeneratorState()
        with self.generator_state_file.open(encoding='utf-8') as f:
            return GeneratorState(**(yaml.safe_load(f) or {}))

    def save_generator_state(self, state: GeneratorState):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with self.generator_state_file.open('w', encoding='utf-8') as f:
            yaml.dump(state.model_dump(), f, allow_unicode=True)

    def get_unprocessed_months(self) -> list[str]:
        if not self.cache_dir.exists():
            return []

        state = self.get_generator_state()
        last_processed = state.last_processed_month

        yaml_files = sorted(self.cache_dir.glob('*.yaml'))
        yaml_files = [f for f in yaml_files if f.name != 'generator-state.yaml']

        month_keys = [f.stem for f in yaml_files]

        if last_processed:
            month_keys = [m for m in month_keys if m > last_processed]

        return month_keys

    def get_messages_for_month(self, month: str) -> list[Message]:
        month_file = self.cache_dir / f'{month}.yaml'
        with month_file.open(encoding='utf-8') as f:
            month_data = MonthMessages(**yaml.safe_load(f))
            return month_data.messages
