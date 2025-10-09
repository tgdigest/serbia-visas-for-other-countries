.PHONY: install fetch extract-facts extract-questions extract-cases yaml2md categorize-questions normalize-faq serve clean lint lint-fix test

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

all: \
	fetch \
	extract-facts \
	extract-questions \
	extract-cases

fetch:
	./venv/bin/python -m tgdigest fetch

extract-facts:
	./venv/bin/python -m tgdigest extract-facts --max-months=1

extract-questions:
	./venv/bin/python -m tgdigest extract-questions --max-months=3

categorize-questions:
	./venv/bin/python -m tgdigest categorize-questions --max-months=12

normalize-questions:
	./venv/bin/python -m tgdigest normalize-questions --max-categories=10

extract-cases:
	./venv/bin/python -m tgdigest extract-cases --max-months=3

yaml2md:
	./venv/bin/python -m tgdigest yaml2md

serve: clean yaml2md
	cd site && hugo server

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf site/public

lint:
	./venv/bin/python -m ruff check tgdigest/

lint-fix:
	./venv/bin/python -m ruff check --fix tgdigest/

test:
	./venv/bin/pytest tgdigest/tests.py -v
