.PHONY: install fetch generate collect serve clean lint lint-fix test

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

all: fetch collect generate

fetch:
	./venv/bin/python -m tgdigest fetch

generate:
	./venv/bin/python -m tgdigest generate --max-months=6

collect:
	./venv/bin/python -m tgdigest collect

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
