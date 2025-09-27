import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from .models import Message, DayMessages


class MessagesCache:
    def __init__(self, url: str, base_path: str = "cache"):
        self.url = url
        self.base_path = Path(base_path)
        self.cache_dir = self._get_cache_dir()
    
    def _get_cache_dir(self) -> Path:
        """Convert URL to cache directory path"""
        # https://t.me/c/1608823685/14535 -> cache/t.me/c/1608823685/14535/
        url_parts = self.url.replace("https://", "").split("/")
        return self.base_path / Path(*url_parts)
    
    def exists(self) -> bool:
        """Check if cache exists for this chat"""
        return self.cache_dir.exists() and any(self.cache_dir.glob("*.yaml"))
    
    def get_last_message_id(self) -> Optional[int]:
        """Get ID of the last cached message"""
        if not self.cache_dir.exists():
            return None
        
        yaml_files = sorted(self.cache_dir.glob("*.yaml"), reverse=True)
        if not yaml_files:
            return None
        
        # Read the most recent file
        with open(yaml_files[0], 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not data:
                return None
            
            day_messages = DayMessages(**data)
            if not day_messages.messages:
                return None
            
            # Messages are sorted by ID, so last one is max
            return day_messages.messages[-1].id
    
    def save_day(self, date: str, messages: List[Message]):
        """Save messages for a single day"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = self.cache_dir / f"{date}.yaml"
        
        # Load existing messages if file exists
        existing_messages = []
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    existing_day = DayMessages(**data)
                    existing_messages = existing_day.messages
        
        # Merge and deduplicate by ID
        existing_ids = {msg.id for msg in existing_messages}
        for msg in messages:
            if msg.id not in existing_ids:
                existing_messages.append(msg)
        
        # Sort by ID
        existing_messages.sort(key=lambda x: x.id)
        
        # Create DayMessages object
        day_data = DayMessages(
            date=date,
            messages=existing_messages
        )
        
        # Save
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                day_data.model_dump(),
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False
            )
        
        print(f"Saved {len(messages)} new messages to {file_path}")
    
    def save_messages(self, messages: List):
        """Save messages grouped by date"""
        # Group messages by date
        messages_by_date = {}
        for msg in messages:
            if not msg.text:  # Skip messages without text
                continue
                
            date_key = msg.date.strftime("%Y-%m-%d")
            
            if date_key not in messages_by_date:
                messages_by_date[date_key] = []
            
            messages_by_date[date_key].append(
                Message(
                    id=msg.id,
                    sender=msg.sender_id,
                    text=msg.text
                )
            )
        
        # Save each day's messages
        for date_key, day_messages in messages_by_date.items():
            self.save_day(date_key, day_messages)

