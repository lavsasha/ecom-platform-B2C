# Контракты ручек b2c

Базовый префикс: `/api/v1`. Ошибки: `{ "error": { "code", "message", "details", "request_id" } }`.

## Страницы (GET)

| Путь | Назначение |
| --- | --- |
| `/pages/home` | Рекомендации, категории, популярные мастера, лента подписок |
| `/pages/search` | Выдача (`q`, `page`, `limit`). GET: `q` в URL - только [percent-encoding](https://datatracker.ietf.org/doc/html/rfc3986). Для curl/PowerShell удобнее `POST /pages/search` с JSON `{"q":"чай","limit":10}`. |
| `/pages/publications` | Лента публикаций |
| `/pages/publications/{publication_id}` | Публикация + товары |
| `/pages/products/{product_id}` | Карточка товара |
| `/pages/sellers/{seller_id}` | Профиль продавца (контракт: Seller) |
| `/pages/masters/{master_id}` | Алиас для `/pages/sellers/{seller_id}` |
| `/pages/subscriptions` | Подписки покупателя (нужен пользователь) |
| `/pages/cart` | Корзина |
| `/pages/checkout` | Оформление |
| `/pages/order-success/{order_id}` | Спасибо за заказ |
| `/pages/orders` | Список заказов |
| `/pages/orders/{order_id}` | Детали заказа |

Секции страницы: `{ "status": "ok" \| "empty" \| "unavailable", "items": ... }` (или поле `data` для одиночных блоков).

## Действия

| Метод | Путь |
| --- | --- |
| POST | `/cart/items` |
| PATCH | `/cart/items/{item_id}` |
| DELETE | `/cart/items/{item_id}` |
| PUT | `/subscriptions/{seller_id}` |
| DELETE | `/subscriptions/{seller_id}` |
| POST | `/checkout/order` |
| POST | `/events` |

## HTTP API на шлюзе B2C (`/api/*`)

Ручки из [`services/b2c/contract_api/router.py`](../services/b2c/contract_api/router.py) (cookie `auth-token`, envelope `{ "data": … }`).

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/api/auth/login` | Логин, установка cookie |
| GET | `/api/posts` | Лента постов |
| GET/PATCH/DELETE | `/api/posts/{id}` | Пост |
| GET/POST | `/api/posts/{id}/comments` | Комментарии к посту |
| PATCH/DELETE | `/api/comments/{id}` | Свой комментарий |
| PUT/DELETE | `/api/posts/{id}/like` | Лайк |
| POST | `/api/users/batch` | Пакет профилей для гидратации |
| … | см. `services/b2c/contract_api/router.py` | остальные ручки каталога/заказов |
