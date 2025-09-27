.PHONY: install run clean lint

install:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

run:
	./venv/bin/python run_tgdigest.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -f *.session *.session-journal

lint:
	./venv/bin/python -m ruff check tgdigest/ *.py