# Единая точка входа в проект. Список целей: make help
# Windows: установите make (choco install make) или выполняйте команды из целей вручную.
.DEFAULT_GOAL := help
PYTHON ?= python
QUESTS ?= 10
ITEMS ?= 20

.PHONY: help install env precommit run generate lint format test check clean

# ---------- Установка ----------
install: ## Установить зависимости (pip install -r requirements.txt)
	$(PYTHON) -m pip install -r requirements.txt

env: ## Создать .env из .env.example (если ещё нет)
	cp -n .env.example .env

precommit: ## Установить git-хуки pre-commit
	pre-commit install

# ---------- Запуск ----------
run: ## Запустить демо Streamlit
	streamlit run app/streamlit_app.py

generate: ## Сгенерировать квесты и предметы (QUESTS, ITEMS)
	$(PYTHON) -m lab05.generators --quests $(QUESTS) --items $(ITEMS)

# ---------- Проверка ----------
lint: ## Проверить код линтером ruff
	ruff check .

format: ## Отформатировать код и применить автоисправления ruff
	ruff format . && ruff check --fix .

test: ## Запустить тесты pytest
	pytest

check: lint test ## Линтер + тесты (то же, что CI)

# ---------- Обслуживание ----------
clean: ## Удалить кеши Python, pytest, ruff и egg-info
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name '*.egg-info' \) -prune -exec rm -rf {} +

help: ## Показать список целей
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

