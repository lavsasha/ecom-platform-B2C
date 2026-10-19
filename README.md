# ecom-platform — B2C

Центральный модуль **`b2c`** — stateless BFF: одна ручка на страницу фронта, данные собираются из микросервисов по HTTP. Собственной БД у B2C нет.

Контрактные сущности (`Seller`, `Product`, `Post`, …) описаны в [`libs/common/contract.py`](libs/common/contract.py); HTTP-ручки `/api/*` — в [`services/b2c/contract_api/router.py`](services/b2c/contract_api/router.py). Сервисы хранят данные у себя, B2C маппит ответы в общий формат.

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build   # postgres, kafka, redis, gorse, meili, сервисы, b2c
docker compose run --rm seed
```

Если Gorse не нужен для проверки каталога: `SEED_SKIP_GORSE=1 docker compose run --rm seed`

- **HTTP API для фронта:** http://localhost:8080/api — cookie `auth-token`, CORS `http://localhost:3000`  
- **BFF страницы:** `GET /api/v1/pages/*` — [docs/page-contracts.md](docs/page-contracts.md)  
- Swagger: http://localhost:8080/docs  
- Dev без cookie: `X-User-Id: 11111111-1111-1111-1111-111111111111`  
- Демо-логин: `anna_buyer` / email `buyer1@example.com` / пароль `secret123` → `POST http://localhost:8080/api/auth/login`

После смены схемы сервисов (masters → sellers, publications → posts) при старом томе Postgres может понадобиться `docker compose down -v` и повторный `seed`.

## Архитектура

```
services/b2c/     clients → mappers → pages → /api/v1/pages/*
services/users/   User, Seller, подписки (PostgreSQL)
services/publications/  Post, лайки, комментарии (PostgreSQL)
services/cart/    корзина (PostgreSQL)
services/orders/  заказы (PostgreSQL)
services/goods/   каталог (PostgreSQL) + Kafka consumer
services/search/  MeiliSearch
services/eventer/ события → Redis / Kafka / Gorse
```

Подробнее: [docs/architecture.md](docs/architecture.md), [docs/testing.md](docs/testing.md).

## Команды

| Команда | Действие |
| --- | --- |
| `make up` | Поднять платформу |
| `make seed` | Демо-данные |
| `make test-unit` | Unit-тесты (без БД) |
| `make test-validation` | Контракты и envelope |
| `make test-integration` | Интеграция (нужен Postgres) |
| `make test-all` | Все уровни + coverage |
| `make test-docker` | Полный прогон в compose |
| `make down` | Остановить |

На Windows без `make` используйте те же команды `pytest …` из [docs/testing.md](docs/testing.md) или `docker compose --profile test run --rm test`.

Проверка readiness (в контейнере есть **curl**, не wget):

```bash
docker compose exec eventer curl -fsS http://localhost:8000/readyz
curl -fsS http://localhost:8005/readyz   # с хоста (порт eventer)
```
