import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def get_jinja_env() -> Environment:
    templates_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(enabled_extensions=[], default_for_string=False)
    )
    env.globals['format_blockquote'] = format_blockquote
    return env


def format_blockquote(text: str) -> str:
    # Make all hashtags bold
    text = re.sub(r'(#\w+)', r'**\1**', text)

    # Escape markdown headers and list markers at line start
    if text.startswith('#'):
        text = '\\' + text
    if text.startswith('+'):
        text = '\\' + text
    if text.startswith('-'):
        text = '\\' + text
    text = text.replace('\n#', '\n\\#')
    text = text.replace('\n+', '\n\\+')
    text = text.replace('\n-', '\n\\-')
    # Replace newlines with <br> for blockquote formatting
    return text.replace('\n', '<br>\n> ')
