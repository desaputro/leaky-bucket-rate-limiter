VENV := .venv
PYTHON := $(VENV)/bin/python

.PHONY: install run test lint format

install:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -r requirements-dev.txt

run:
	$(PYTHON) -m uvicorn rate_limiter.api:app --reload

test:
	$(PYTHON) -m pytest -v

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .
