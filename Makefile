.PHONY: help venv build test lint format serve pdf clean

PY := .venv/bin/python
PIP := .venv/bin/pip

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n",$$1,$$2}'

venv: ## Create the virtualenv and install dependencies
	python3 -m venv .venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -r requirements-dev.txt
	$(PIP) install -q -e .

build: ## Build the static site into dist/
	$(PY) -m mealplanner.build

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Check formatting and lint rules
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

format: ## Apply formatting and safe autofixes
	$(PY) -m ruff format src tests
	$(PY) -m ruff check --fix src tests

serve: build ## Build then serve the site at http://localhost:8000
	cd dist && ../$(PY) -m http.server 8000

pdf: ## Regenerate the PDF documents (requires Google Chrome)
	$(PY) scripts/mkpdf.py

validate: ## Validate the recipe catalogue against the food database
	$(PY) scripts/validate_recipes.py data/recipes/*.json

nutrition: ## Print the full nutrition report (legacy fixed-week plan)
	$(PY) -m mealplanner.nutrition

clean: ## Remove build output and caches
	rm -rf dist .pytest_cache .ruff_cache
	find . -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

icons: ## Regenerate the app icons from assets/icon.svg (requires Google Chrome)
	$(PY) scripts/mkicons.py
