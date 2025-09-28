import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def get_jinja_env() -> Environment:
    templates_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(enabled_extensions=[], default_for_string=False)
    )
    env.globals['highlight_keywords'] = highlight_keywords
    env.globals['format_blockquote'] = format_blockquote
    return env


def highlight_keywords(text: str, keywords: list[str]) -> str:
    # Sort keywords by length descending to handle longer matches first
    for keyword in sorted(keywords, key=len, reverse=True):
        # Case-insensitive search and replace, preserving original case
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(lambda m: f'**{m.group()}**', text)
    return text


def format_blockquote(text: str) -> str:
    # Escape markdown list markers at line start
    if text.startswith('+'):
        text = '\\' + text
    if text.startswith('-'):
        text = '\\' + text
    text = text.replace('\n+', '\n\\+')
    text = text.replace('\n-', '\n\\-')
    # Replace newlines with <br> for blockquote formatting
    return text.replace('\n', '<br>\n> ')
