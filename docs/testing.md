# Тестирование

Три уровня тестов живут в каталоге [`tests/`](../tests/):

| Уровень | Каталог | Маркер | Зависимости |
|--------|---------|--------|-------------|
| **Unit** | `tests/unit/` | `unit` | только Python + `libs/common` |
| **Validation** | `tests/validation/` | `validation` | контракты, envelope, часть B2C без БД |
| **Integration** | `tests/integration/` | `integration` | **PostgreSQL** (`ecom_*`), ASGI-сервисы |

## Локально (Windows / Linux)

Установите зависимости:

```bash
pip install -r requirements.txt
```

### Unit (быстро, без Docker)

```bash
make test-unit
# или
pytest tests/unit -m unit -v
```

### Validation

```bash
make test-validation
# или
pytest tests/validation -m validation -v
```

### Integration

Поднимите Postgres:

```bash
docker compose up -d postgres
```

С хоста (порт 5432):

```bash
set TEST_POSTGRES_HOST=localhost
make test-integration
```

Интеграционные тесты **запускаются отдельным процессом pytest на каждый микросервис** (`b2c`, `cart`, `users`, `orders`, `publications`), чтобы не смешивать ORM-модели с общим `common.db.Base`.

Или полный прогон:

```bash
make test-all
```

### Покрытие

`make test-all` и `make test-docker` добавляют `--cov` по `libs/common` и `services/`.

## Docker (рекомендуется для integration)

```bash
docker compose --profile test run --rm test
# или
make test-docker
```

Внутри compose `TEST_POSTGRES_HOST=postgres`.

## Что куда отнесено

- **Unit:** `gather`, мапперы B2C, DTO, курсоры publications, суммы cart, граф статусов orders, маппинг search indexer, фильтр Gorse feedback в eventer.
- **Validation:** `{data, error}` envelope, Pydantic-контракты, HTTP-форматы `/api/*` и BFF validation.
- **Integration:** реальные CRUD cart/users/publications/orders через ASGI; B2C с `respx` (моки апстримов).

Старый каталог `services/b2c/tests` удалён — используйте `tests/integration/b2c/`.
