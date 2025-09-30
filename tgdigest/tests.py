import tempfile
from pathlib import Path

from tgdigest.ai import OpenAIProvider
from tgdigest.diff_parser import DiffParser
from tgdigest.generator import Generator
from tgdigest.models import Config


def test_diff_parser_whitespace_handling():
    """Test that diff parser correctly handles whitespace in additions."""
    parser = DiffParser()

    # Test case where additions have different indentation than context
    original = '   - Item two'
    diff = """@@ ... @@
    - Item two
+   - Item three"""

    result = parser.apply(original, diff)
    # Should preserve indentation from the additions in diff
    assert result == '   - Item two\n   - Item three\n'


def test_diff_parser_mixed_indentation():
    """Test additions with mixed indentation levels."""
    parser = DiffParser()

    original = """1. List
   - Item one
   - Item two"""

    # The problem: context has 3 spaces indentation but shown as 4 in diff
    diff = """@@ ... @@
    - Item two
+   - Item three"""

    result = parser.apply(original, diff)
    # The addition should have 3 spaces to match the file's indentation
    expected = """1. List
   - Item one
   - Item two
   - Item three
"""
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_diff_parser_additions_only():
    parser = DiffParser()

    original = """1. List
   - Item one
   - Item two"""

    diff = """@@ ... @@
 1. List
    - Item one
    - Item two
+   - Item three
+   - Item four"""

    # Since original doesn't end with newline, result preserves this
    expected = """1. List
   - Item one
   - Item two
   - Item three
   - Item four
"""

    result = parser.apply(original, diff)
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_diff_parser_replacements():
    parser = DiffParser()

    original = """ - **Standard**: 2 weeks
 - **Fast**: 12-15 days
 - **Delayed**: may extend"""

    diff = """@@ ... @@
- - **Standard**: 2 weeks
- - **Fast**: 12-15 days
- - **Delayed**: may extend
+
+- **Standard**: 2 weeks
+- **Fast**: next day sometimes
+- **Delayed**: may extend"""

    expected = """
- **Standard**: 2 weeks
- **Fast**: next day sometimes
- **Delayed**: may extend
"""

    result = parser.apply(original, diff)
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_diff_parser_addition_after_context():
    parser = DiffParser()

    original = """5. **Waiting**
   - They take passport
   - Give receipt
   - Call when ready

## Processing times"""

    diff = """@@ ... @@
 5. **Waiting**
    - They take passport
    - Give receipt
    - Call when ready
+   - Can't track online
 
 ## Processing times"""

    expected = """5. **Waiting**
   - They take passport
   - Give receipt
   - Call when ready
   - Can't track online

## Processing times"""

    result = parser.apply(original, diff)
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_no_extra_newlines():
    """Test that diff parser doesn't add extra newlines."""
    parser = DiffParser()

    # Original content already has proper newlines
    original = """## Title

Some content here.

## Another section
More content."""

    # Simple addition that shouldn't create extra newlines
    diff = """@@ ... @@
 ## Title
 
 Some content here.
+Added line here.
 
 ## Another section"""

    result = parser.apply(original, diff)
    
    # Count newlines - should not increase more than added lines
    original_newlines = original.count('\n')
    result_newlines = result.count('\n')
    added_lines = 1
    
    assert result_newlines <= original_newlines + added_lines + 1, \
        f'Too many newlines: original had {original_newlines}, result has {result_newlines}'
    
    # Should not have double newlines
    expected = """## Title

Some content here.
Added line here.

## Another section
More content."""
    
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_no_double_newlines_when_already_present():
    """Test that we don't add newline if line already has one."""
    parser = DiffParser()
    
    original = """Line one
Line two
Line three"""
    
    diff = """@@ ... @@
 Line one
 Line two
+Added line
 Line three"""
    
    result = parser.apply(original, diff)
    
    # Should not have double newlines between lines
    assert '\n\n' not in result.replace('Line three', ''), \
        f'Found double newlines in result: {result!r}'
    
    expected = """Line one
Line two
Added line
Line three"""
    
    assert result == expected, f'Result:\n{result!r}\n\nExpected:\n{expected!r}'


def test_apply_real_diff():

    original = """## Процесс подачи

1. **Запись онлайн** через сайт консульства
   - Слоты появляются в случайное время утром
   - Даются на ближайшие 1-4 недели
   - Нужно ловить
   
2. **Подача документов**
   - Приносите все оригиналы + копии
   - При записи выбирайте "Apply" (а не "Appeal")

3. **Собеседование с консулом**
   - Задают вопросы о целях поездки, маршруте
   - Спрашивают про основание ВНЖ, почему подаётесь в Сербии
   - Лучше подготовиться к стандартным вопросам
   - Может быть на английском
   - Могут спросить про предыдущие поездки по визам

5. **Ожидание**
   - Паспорт забирают на время рассмотрения
   - Дают талончик
   - Присылают письмо/звонят когда виза готова

## Сроки рассмотрения

 - **Стандартный срок**: 2 недели (фиксированный)
 - **Быстрые случаи**: 12-15 дней (подал 7 декабря, забрал 19)
 - **С задержками**: могут продлить рассмотрение 2 раза

## Советы

13. **Report back form** — всё чаще требуют! При выдаче визы дают бумажку с требованием по возвращению отправить на почту: сканы паспорта о пересечении границы (въезд/выезд), подтверждение возврата в Сербию, чеки из отеля. Это предусмотрено правилами Шенгена

16. **Минимальный срок ВНЖ** — НЕТ требования по минимальному сроку владения ВНЖ. Можно подаваться даже с 1-2 месячным ВНЖ
"""

    diff = """--- hungary/guide.md
+++ hungary/guide.md
@@ ... @@
 ## Процесс подачи
 
 1. **Запись онлайн** через сайт консульства
    - Слоты появляются в случайное время утром
    - Даются на ближайшие 1-4 недели
    - Нужно ловить
+   - Можно также записаться по электронной почте в консульство Суботицы (visa.sab@mfa.gov.hu) — иногда отвечают оперативно, возможно записаться даже если на сайте нет свободных слотов
+   - В Суботице также можно записаться по телефону — есть русскоговорящая женщина, иногда предоставляют отдельные даты вне онлайн-календаря
    
 2. **Подача документов**
    - Приносите все оригиналы + копии
@@ ... @@
    - При записи выбирайте "Apply" (а не "Appeal")
 
 3. **Собеседование с консулом**
    - Задают вопросы о целях поездки, маршруте
    - Спрашивают про основание ВНЖ, почему подаётесь в Сербии
    - Лучше подготовиться к стандартным вопросам
    - Может быть на английском
    - Могут спросить про предыдущие поездки по визам
+   - В Суботице иногда вызывают всех членов семьи (в том числе детей) для сдачи отпечатков и собеседования
@@ ... @@
 
 5. **Ожидание**
    - Паспорт забирают на время рассмотрения
    - Дают талончик
    - Присылают письмо/звонят когда виза готова
+   - Отслеживать статус рассмотрения онлайн в Белграде нельзя, решение высылают по электронной почте или сообщают при выдаче
 
 ## Сроки рассмотрения
 
- - **Стандартный срок**: 2 недели (фиксированный)
- - **Быстрые случаи**: 12-15 дней (подал 7 декабря, забрал 19)
- - **С задержками**: могут продлить рассмотрение 2 раза
+
+- **Стандартный срок**: 2 недели (фиксированный)
+- **Быстрые случаи**: иногда готовы на следующий день после подачи
+- **С задержками**: могут продлить рассмотрение 2 раза
@@ ... @@
 
 ## Советы
 
@@ ... @@
 13. **Report back form** — всё чаще требуют! При выдаче визы дают бумажку с требованием по возвращению отправить на почту: сканы паспорта о пересечении границы (въезд/выезд), подтверждение возврата в Сербию, чеки из отеля. Это предусмотрено правилами Шенгена
+
+    - По новым правилам, часто требуют не позднее чем через 2 недели после возвращения предоставить сканы штампов о пересечении границы (или лично принести их в посольство), иногда также просят посадочные билеты (если применимо). Важно обязательно выслать эти документы, иначе могут возникнуть проблемы с получением следующих виз.
@@ ... @@
 16. **Минимальный срок ВНЖ** — НЕТ требования по минимальному сроку владения ВНЖ. Можно подаваться даже с 1-2 месячным ВНЖ
"""

    expected = """## Процесс подачи

1. **Запись онлайн** через сайт консульства
   - Слоты появляются в случайное время утром
   - Даются на ближайшие 1-4 недели
   - Нужно ловить
   - Можно также записаться по электронной почте в консульство Суботицы (visa.sab@mfa.gov.hu) — иногда отвечают оперативно, возможно записаться даже если на сайте нет свободных слотов
   - В Суботице также можно записаться по телефону — есть русскоговорящая женщина, иногда предоставляют отдельные даты вне онлайн-календаря
   
2. **Подача документов**
   - Приносите все оригиналы + копии
   - При записи выбирайте "Apply" (а не "Appeal")

3. **Собеседование с консулом**
   - Задают вопросы о целях поездки, маршруте
   - Спрашивают про основание ВНЖ, почему подаётесь в Сербии
   - Лучше подготовиться к стандартным вопросам
   - Может быть на английском
   - Могут спросить про предыдущие поездки по визам
   - В Суботице иногда вызывают всех членов семьи (в том числе детей) для сдачи отпечатков и собеседования

5. **Ожидание**
   - Паспорт забирают на время рассмотрения
   - Дают талончик
   - Присылают письмо/звонят когда виза готова
   - Отслеживать статус рассмотрения онлайн в Белграде нельзя, решение высылают по электронной почте или сообщают при выдаче

## Сроки рассмотрения


- **Стандартный срок**: 2 недели (фиксированный)
- **Быстрые случаи**: иногда готовы на следующий день после подачи
- **С задержками**: могут продлить рассмотрение 2 раза

## Советы

13. **Report back form** — всё чаще требуют! При выдаче визы дают бумажку с требованием по возвращению отправить на почту: сканы паспорта о пересечении границы (въезд/выезд), подтверждение возврата в Сербию, чеки из отеля. Это предусмотрено правилами Шенгена

    - По новым правилам, часто требуют не позднее чем через 2 недели после возвращения предоставить сканы штампов о пересечении границы (или лично принести их в посольство), иногда также просят посадочные билеты (если применимо). Важно обязательно выслать эти документы, иначе могут возникнуть проблемы с получением следующих виз.

16. **Минимальный срок ВНЖ** — НЕТ требования по минимальному сроку владения ВНЖ. Можно подаваться даже с 1-2 месячным ВНЖ
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(original)
        temp_file = Path(f.name)

    try:
        config = Config(chats=[])
        provider = OpenAIProvider(api_key='dummy', model='gpt-4')
        gen = Generator(config=config, provider=provider)
        gen._apply_diff(temp_file, diff)

        result = temp_file.read_text(encoding='utf-8')
        assert result == expected, f'Expected:\n{expected!r}\n\nGot:\n{result!r}'
    finally:
        temp_file.unlink()
