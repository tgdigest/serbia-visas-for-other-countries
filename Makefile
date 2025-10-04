.PHONY: install fetch generate collect extract-facts extract-questions reorganize serve clean lint lint-fix test

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

all: fetch collect extract-facts extract-questions

fetch:
	./venv/bin/python -m tgdigest fetch

extract-facts:
	./venv/bin/python -m tgdigest extract-facts --max-months=1

extract-questions:
	./venv/bin/python -m tgdigest extract-questions --max-months=1

extract-cases:
	./venv/bin/python -m tgdigest extract-cases --max-months=1

collect:
	./venv/bin/python -m tgdigest collect

generate:
	./venv/bin/python -m tgdigest generate --max-months=1

reorganize:
	./venv/bin/python -m tgdigest reorganize

serve:
	./venv/bin/mkdocs serve

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -f *.session *.session-journal

lint:
	./venv/bin/python -m ruff check tgdigest/

lint-fix:
	./venv/bin/python -m ruff check --fix tgdigest/

test:
	./venv/bin/pytest tgdigest/tests.py -v
