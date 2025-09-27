import logging


class Generator:
    def __init__(self, openai_api_key: str, logger=None):
        self.logger = logger or logging.getLogger(__name__)

