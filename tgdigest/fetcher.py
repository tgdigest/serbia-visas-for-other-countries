import logging
from pathlib import Path

from telethon import TelegramClient

from tgdigest.cache import MessagesCache
from tgdigest.models import Chat, Message


class Fetcher:
    def __init__(
        self,
        *,
        api_id,
        api_hash,
        phone,
        session_name='tgdigest',
        force_login=False,
        logger=None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug('Initializing TgDigest client: api_id=%s, session_name=%s', api_id, session_name)

        if force_login:
            self.logger.info('Removed existing session, forcing re-login')
            session_file = Path(f'{session_name}.session')
            if session_file.exists():
                session_file.unlink()

        self._client = TelegramClient(session_name, api_id, api_hash)
        self.logger.debug('Starting Telegram client: phone=%s', phone)
        self._started = False

    async def load_chat(self, chat: Chat):
        if not self._started:
            await self._client.start()
            self._started = True

        self.logger.info('Loading chat: %s (%s)', chat.title, chat.url)

        cache = MessagesCache(chat.url)

        current_month = None
        month_messages = []
        async for message in self._client.iter_messages(
            chat.get_chat_id(),
            reply_to=chat.get_topic_id(),
            min_id=cache.get_last_message_id() or 0,
            reverse=True,
        ):
            if not message.text:
                continue

            self.logger.debug('loaded message id=%s date=%s', message.id, message.date)

            month_key = message.date.strftime('%Y-%m')
            if current_month and month_key != current_month:
                self.logger.info('saving %d messages for month %s', len(month_messages), current_month)
                cache.save_month(current_month, month_messages)
                month_messages = []

            current_month = month_key
            month_messages.append(Message(
                id=message.id,
                sender=message.sender_id,
                text=message.text,
            ))

        if month_messages:
            self.logger.info('saving %d messages for month %s', len(month_messages), current_month)
            cache.save_month(current_month, month_messages)

    def disconnect(self):
        if not self._started:
            return
        self._client.disconnect()
