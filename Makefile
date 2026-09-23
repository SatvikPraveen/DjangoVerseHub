# File: DjangoVerseHub/Makefile
.DEFAULT_GOAL := help
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
MANAGE = $(PYTHON) manage.py
SETTINGS_DEV = django_verse_hub.settings.dev

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv and install dev dependencies
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/dev.txt

install: ## Install/refresh dev dependencies into the existing venv
	$(PIP) install -r requirements/dev.txt

run: ## Run the development server (ASGI, with WebSockets)
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) runserver 0.0.0.0:8000

worker: ## Run a Celery worker
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) .venv/bin/celery -A django_verse_hub worker -l info

beat: ## Run Celery beat
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) .venv/bin/celery -A django_verse_hub beat -l info

migrate: ## Apply database migrations
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) migrate

makemigrations: ## Create new migrations
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) makemigrations

superuser: ## Create a superuser
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) createsuperuser

demo: ## Load demo data
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) generate_demo_data

shell: ## Django shell_plus
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) shell_plus

test: ## Run the test suite
	$(PYTHON) -m pytest -q

test-fast: ## Run tests in parallel
	$(PYTHON) -m pytest -q -n auto

coverage: ## Run tests with coverage report
	$(PYTHON) -m pytest -q --cov --cov-report=term-missing --cov-report=html

lint: ## Lint with ruff
	.venv/bin/ruff check .

format: ## Format with ruff
	.venv/bin/ruff format .
	.venv/bin/ruff check --fix .

typecheck: ## Type-check with mypy
	.venv/bin/mypy apps django_verse_hub

check: ## Django system checks + migration drift check
	DJANGO_SETTINGS_MODULE=$(SETTINGS_DEV) $(MANAGE) check
	DJANGO_SETTINGS_MODULE=django_verse_hub.settings.test KEEP_MIGRATIONS=1 $(MANAGE) makemigrations --check --dry-run

ci: lint check test ## What CI runs

clean: ## Remove caches and build artefacts
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml

docker-up: ## Start the full stack with docker compose
	docker compose up --build

docker-down: ## Stop the stack
	docker compose down

.PHONY: help venv install run worker beat migrate makemigrations superuser demo shell test test-fast coverage lint format typecheck check ci clean docker-up docker-down
