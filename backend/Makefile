.PHONY: install check lint typecheck test format

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests

format:
	ruff format src tests && ruff check --fix src tests

typecheck:
	mypy src

test:
	pytest -q

check: lint typecheck test
