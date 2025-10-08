import hashlib
import json

from .models import Message


def compute_messages_hash(messages: list[Message]) -> str:
    ids = ','.join(str(msg.id) for msg in messages)
    return hashlib.md5(ids.encode()).hexdigest()


def compute_text_hash(texts: list[str]) -> str:
    combined = '|'.join(sorted(texts))
    return hashlib.md5(combined.encode()).hexdigest()


def format_json(title: str, data) -> str:
    """Format data as JSON block with title."""
    return f'{title}:\n```json\n{json.dumps(data, ensure_ascii=False)}\n```\n'


class WorkLimiter:
    """Tracks work limit across multiple operations."""

    def __init__(self, max_items: int):
        self.max_items = max_items
        self.processed = 0

    def can_process(self) -> bool:
        """Check if we can process more items."""
        return self.processed < self.max_items

    def increment(self):
        """Mark one item as processed."""
        self.processed += 1

    def remaining(self) -> int:
        """Get remaining items count."""
        return max(0, self.max_items - self.processed)

    def __str__(self) -> str:
        return f'{self.processed}/{self.max_items}'
