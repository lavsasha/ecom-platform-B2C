COMPOSE ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

.PHONY: env
env: ## Copy .env.example to .env if missing
	@test -f .env || cp .env.example .env

.PHONY: up
up: env ## Start platform
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Stop containers
	$(COMPOSE) down

.PHONY: seed
seed: ## Load demo data
	$(COMPOSE) run --rm seed python /deploy/seed.py

.PHONY: test test-unit test-integration test-validation test-all
test: test-all ## Run unit + validation + integration (needs Postgres for integration)

test-unit: ## Fast tests, no database
	pytest tests/unit -m unit -q

test-validation: ## Contract envelopes and DTO validation
	pytest tests/validation -m validation -q

test-integration: ## Service and BFF tests (Postgres; one process per service)
	pytest tests/integration/b2c -m integration -q
	pytest tests/integration/cart -m integration -q
	pytest tests/integration/users -m integration -q
	pytest tests/integration/orders -m integration -q
	pytest tests/integration/publications -m integration -q

test-all: ## Full suite with coverage summary
	pytest tests/unit -m unit -q
	pytest tests/validation -m validation -q
	$(MAKE) test-integration
	pytest tests/integration/publications -m integration -q --cov=libs/common --cov=services --cov-report=term-missing:skip-covered

test-docker: ## Run full suite inside compose (postgres on TEST_POSTGRES_HOST=postgres)
	$(COMPOSE) --profile test run --rm test
