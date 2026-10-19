#!/usr/bin/env python3
"""Load demo data into service databases, MeiliSearch, and Gorse."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import asyncpg
import bcrypt
import httpx

DEMO_PASSWORD = "secret123"


def _password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# --- fixed demo ids -----------------------------------------------------------

BUYER1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
BUYER2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
BUYER3 = uuid.UUID("33333333-3333-3333-3333-333333333333")

SELLERS = [
    uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
    uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2"),
    uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3"),
    uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4"),
    uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5"),
]

CAT_JEWELRY = uuid.UUID("c1000000-0000-4000-8000-000000000001")
CAT_HOME = uuid.UUID("c1000000-0000-4000-8000-000000000002")
CAT_ART = uuid.UUID("c1000000-0000-4000-8000-000000000003")

PRODUCT_IDS = [
    uuid.UUID(f"b1000001-0000-4000-8000-{i:012x}") for i in range(1, 16)
]

NOW = datetime.now(UTC)

PG_USER = os.getenv("POSTGRES_USER", "ecom")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "ecom")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700").rstrip("/")
MEILI_KEY = os.getenv("MEILI_MASTER_KEY", "masterKeyForLocalDevOnly")
GORSE_URL = os.getenv("GORSE_URL", "http://gorse:8088").rstrip("/")
GORSE_KEY = os.getenv("GORSE_API_KEY", "gorseApiKeyForLocalDevOnly")


def dsn(db: str) -> str:
    return f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:5432/{db}"


async def run_ddl(conn: asyncpg.Connection, statements: str) -> None:
    await conn.execute(statements)


async def seed_users(conn: asyncpg.Connection) -> None:
    await run_ddl(
        conn,
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            email VARCHAR(320) UNIQUE NOT NULL,
            username VARCHAR(64) UNIQUE NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            password_hash VARCHAR(255),
            phone VARCHAR(32),
            avatar TEXT,
            bio TEXT,
            roles JSONB DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS addresses (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            label VARCHAR(64),
            city VARCHAR(120) NOT NULL,
            street VARCHAR(200) NOT NULL,
            building VARCHAR(32) NOT NULL,
            apartment VARCHAR(32),
            postal_code VARCHAR(16),
            recipient_name VARCHAR(200) NOT NULL,
            recipient_phone VARCHAR(32) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS sellers (
            id UUID PRIMARY KEY,
            user_id UUID UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            username VARCHAR(120) UNIQUE NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            bio TEXT,
            avatar TEXT,
            cover_url TEXT,
            city VARCHAR(120),
            rating NUMERIC(2,1) NOT NULL DEFAULT 0,
            followers_count INT NOT NULL DEFAULT 0,
            products_count INT NOT NULL DEFAULT 0,
            posts_count INT NOT NULL DEFAULT 0,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            seller_id UUID NOT NULL,
            notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, seller_id)
        );
        """,
    )
    buyers = [
        (BUYER1, "buyer1@example.com", "anna_buyer", "Анна Покупатель"),
        (BUYER2, "buyer2@example.com", "boris_buyer", "Борис Покупатель"),
        (BUYER3, "buyer3@example.com", "vika_buyer", "Вика Покупатель"),
    ]
    for uid, email, username, name in buyers:
        await conn.execute(
            """
            INSERT INTO users (id, email, username, display_name, phone, password_hash, roles, is_active)
            VALUES ($1, $2, $3, $4, '+79000000001', $5, '["buyer"]'::jsonb, TRUE)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                password_hash = EXCLUDED.password_hash
            """,
            uid,
            email,
            username,
            name,
            _password_hash(DEMO_PASSWORD),
        )

    addr_id = uuid.UUID("a1000000-0000-4000-8000-000000000001")
    await conn.execute(
        """
        INSERT INTO addresses (
            id, user_id, label, city, street, building, apartment,
            postal_code, recipient_name, recipient_phone, is_default
        ) VALUES ($1,$2,'Дом','Москва','Тверская','1','10','125009',$3,'+79001112233',TRUE)
        ON CONFLICT (id) DO NOTHING
        """,
        addr_id,
        BUYER1,
        "Анна Покупатель",
    )

    seller_rows = [
        (SELLERS[0], "maria-clay", "Мария Гончар", "Керамика ручной работы", "Москва", 4.8, 3, 8, 540),
        (SELLERS[1], "ivan-wood", "Иван Резчик", "Деревянный декор", "Санкт-Петербург", 4.6, 3, 5, 210),
        (SELLERS[2], "olga-textile", "Ольга Текстиль", "Текстиль для дома", "Казань", 4.9, 3, 10, 880),
        (SELLERS[3], "nina-jewelry", "Нина Украшения", "Авторские украшения", "Москва", 4.7, 3, 6, 430),
        (SELLERS[4], "pavel-art", "Павел Арт", "Картины и постеры", "Екатеринбург", 4.5, 3, 4, 150),
    ]
    for sid, username, name, bio, city, rating, pc, posts, subs in seller_rows:
        await conn.execute(
            """
            INSERT INTO sellers (
                id, username, display_name, bio, city, rating,
                products_count, posts_count, followers_count, is_verified
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            sid,
            username,
            name,
            bio,
            city,
            rating,
            pc,
            posts,
            subs,
        )

    await conn.execute(
        """
        INSERT INTO subscriptions (id, user_id, seller_id, notifications_enabled)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (user_id, seller_id) DO NOTHING
        """,
        uuid.UUID("51000000-0000-4000-8000-000000000001"),
        BUYER1,
        SELLERS[0],
    )
    await conn.execute(
        """
        INSERT INTO subscriptions (id, user_id, seller_id, notifications_enabled)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (user_id, seller_id) DO NOTHING
        """,
        uuid.UUID("51000000-0000-4000-8000-000000000002"),
        BUYER1,
        SELLERS[3],
    )


async def seed_goods(conn: asyncpg.Connection) -> list[dict]:
    await run_ddl(
        conn,
        """
        CREATE TABLE IF NOT EXISTS categories (
            id UUID PRIMARY KEY,
            slug VARCHAR(120) UNIQUE NOT NULL,
            title VARCHAR(200) NOT NULL,
            parent_id UUID REFERENCES categories(id) ON DELETE SET NULL,
            image_url TEXT,
            position INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY,
            slug VARCHAR(160) UNIQUE NOT NULL,
            title VARCHAR(300) NOT NULL,
            subtitle VARCHAR(300),
            description TEXT,
            seller_id UUID NOT NULL,
            category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
            images JSONB NOT NULL DEFAULT '[]',
            attributes JSONB NOT NULL DEFAULT '[]',
            tags JSONB NOT NULL DEFAULT '[]',
            rating NUMERIC(2,1) NOT NULL DEFAULT 0,
            reviews_count INT NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS offers (
            id UUID PRIMARY KEY,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            title VARCHAR(200),
            price_amount NUMERIC(12,2) NOT NULL,
            old_price_amount NUMERIC(12,2),
            currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
            stock INT NOT NULL DEFAULT 0,
            is_default BOOLEAN NOT NULL DEFAULT TRUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        ALTER TABLE products ADD COLUMN IF NOT EXISTS sale_mode VARCHAR(32) NOT NULL DEFAULT 'online';
        ALTER TABLE products ADD COLUMN IF NOT EXISTS available_deliveries JSONB NOT NULL DEFAULT '["pickup","cdek"]'::jsonb;
        ALTER TABLE products ADD COLUMN IF NOT EXISTS pickup_points JSONB;
        ALTER TABLE products ADD COLUMN IF NOT EXISTS deal_contacts TEXT;
        ALTER TABLE products ALTER COLUMN attributes SET DEFAULT '[]'::jsonb;
        UPDATE products SET attributes = '[]'::jsonb WHERE attributes IS NULL;
        UPDATE products SET available_deliveries = '["pickup","cdek"]'::jsonb
            WHERE available_deliveries IS NULL;
        """,
    )
    categories = [
        (CAT_JEWELRY, "jewelry", "Украшения", 1),
        (CAT_HOME, "home", "Для дома", 2),
        (CAT_ART, "art", "Арт", 3),
    ]
    for cid, slug, title, pos in categories:
        await conn.execute(
            """
            INSERT INTO categories (id, slug, title, position)
            VALUES ($1,$2,$3,$4) ON CONFLICT (id) DO NOTHING
            """,
            cid,
            slug,
            title,
            pos,
        )

    titles = [
        ("ceramic-mug-blue", "Керамическая кружка «Море»", CAT_HOME, SELLERS[0], 890),
        ("ceramic-plate-set", "Набор тарелок ручной работы", CAT_HOME, SELLERS[0], 4200),
        ("clay-vase", "Ваза из глины", CAT_HOME, SELLERS[0], 3100),
        ("wood-tray", "Деревянный поднос", CAT_HOME, SELLERS[1], 2400),
        ("wood-clock", "Настенные часы из ясеня", CAT_HOME, SELLERS[1], 5600),
        ("linen-napkins", "Льняные салфетки, 4 шт.", CAT_HOME, SELLERS[2], 1200),
        ("woven-blanket", "Плед ручного ткачества", CAT_HOME, SELLERS[2], 7800),
        ("silver-earrings", "Серебряные серьги «Капля»", CAT_JEWELRY, SELLERS[3], 3500),
        ("beaded-bracelet", "Браслет из натуральных камней", CAT_JEWELRY, SELLERS[3], 980),
        ("gold-plated-ring", "Кольцо с позолотой", CAT_JEWELRY, SELLERS[3], 2100),
        ("abstract-poster", "Постер «Абстракция»", CAT_ART, SELLERS[4], 1400),
        ("landscape-print", "Печать «Горный рассвет»", CAT_ART, SELLERS[4], 2200),
        ("mini-canvas", "Мини-холст 20×20", CAT_ART, SELLERS[4], 3900),
        ("ceramic-bowl", "Пиала для чая", CAT_HOME, SELLERS[0], 650),
        ("wood-spoon-set", "Набор ложек из оливкового дерева", CAT_HOME, SELLERS[1], 1100),
    ]

    docs: list[dict] = []
    for idx, (slug, title, cat_id, seller_id, price) in enumerate(titles):
        pid = PRODUCT_IDS[idx]
        image = [{"url": f"https://pics.example/handmade/{slug}.jpg", "alt": title}]
        tags = ["handmade", "demo"]
        attributes: list = []
        deliveries = ["pickup", "cdek"]
        await conn.execute(
            """
            INSERT INTO products (
                id, slug, title, subtitle, description, seller_id, category_id,
                images, attributes, tags, rating, reviews_count, is_active,
                sale_mode, available_deliveries
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,$12,TRUE,$13,$14::jsonb
            ) ON CONFLICT (id) DO NOTHING
            """,
            pid,
            slug,
            title,
            "Авторская работа",
            f"{title}. Демо-описание для витрины.",
            seller_id,
            cat_id,
            json.dumps(image),
            json.dumps(attributes),
            json.dumps(tags),
            Decimal("4.5") + Decimal(idx % 5) / 10,
            10 + idx * 3,
            "online",
            json.dumps(deliveries),
        )
        offer_id = uuid.UUID(f"f1000001-0000-4000-8000-{idx + 1:012x}")
        await conn.execute(
            """
            INSERT INTO offers (
                id, product_id, title, price_amount, old_price_amount, currency, stock, is_default, is_active
            ) VALUES ($1,$2,'Стандарт',$3,$4,'RUB',25,TRUE,TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            offer_id,
            pid,
            Decimal(price),
            Decimal(price + 200) if idx % 3 == 0 else None,
        )
        cat_slug = next(c[1] for c in categories if c[0] == cat_id)
        cat_title = next(c[2] for c in categories if c[0] == cat_id)
        docs.append(
            {
                "product_id": str(pid),
                "slug": slug,
                "title": title,
                "subtitle": "Авторская работа",
                "description": f"{title}. Демо-описание для витрины.",
                "seller_id": str(seller_id),
                "category_id": str(cat_id),
                "category_slug": cat_slug,
                "category_title": cat_title,
                "tags": tags,
                "rating": float(Decimal("4.5") + Decimal(idx % 5) / 10),
                "reviews_count": 10 + idx * 3,
                "is_active": True,
                "min_price": float(price),
                "created_at": NOW.isoformat(),
            }
        )
    return docs


async def seed_publications(conn: asyncpg.Connection) -> None:
    await run_ddl(
        conn,
        """
        CREATE TABLE IF NOT EXISTS posts (
            id UUID PRIMARY KEY,
            slug VARCHAR(160) UNIQUE NOT NULL,
            seller_id UUID NOT NULL,
            title VARCHAR(300) NOT NULL,
            summary VARCHAR(600),
            body TEXT NOT NULL DEFAULT '',
            cover_image TEXT,
            published_at TIMESTAMPTZ,
            likes_count INT NOT NULL DEFAULT 0,
            comments_count INT NOT NULL DEFAULT 0,
            is_published BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS post_products (
            id UUID PRIMARY KEY,
            post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            product_id UUID NOT NULL,
            position INT NOT NULL DEFAULT 0,
            UNIQUE (post_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS post_comments (
            id UUID PRIMARY KEY,
            post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_post_comments_post_id_created_at
            ON post_comments (post_id, created_at);
        """,
    )
    pubs = [
        (
            uuid.UUID("e2000001-0000-4000-8000-000000000001"),
            "maria-new-glaze",
            SELLERS[0],
            "Новая глазурь для осенней коллекции",
            "Рассказываю, как получился оттенок «Море».",
            [PRODUCT_IDS[0], PRODUCT_IDS[2]],
        ),
        (
            uuid.UUID("e2000001-0000-4000-8000-000000000002"),
            "ivan-workshop-tour",
            SELLERS[1],
            "Экскурсия по мастерской",
            "Показываю процесс резки и сборки часов.",
            [PRODUCT_IDS[4]],
        ),
        (
            uuid.UUID("e2000001-0000-4000-8000-000000000003"),
            "nina-silver-care",
            SELLERS[3],
            "Как ухаживать за серебром",
            "Простые советы для украшений ручной работы.",
            [PRODUCT_IDS[7], PRODUCT_IDS[8]],
        ),
    ]
    for pub_id, slug, seller_id, title, summary, product_ids in pubs:
        await conn.execute(
            """
            INSERT INTO posts (
                id, slug, seller_id, title, summary, body, cover_image,
                published_at, likes_count, comments_count, is_published
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            pub_id,
            slug,
            seller_id,
            title,
            summary,
            f"{summary}\n\nПолный текст демо-публикации.",
            f"https://pics.example/pub/{slug}.jpg",
            NOW,
            12,
            0,
        )
        for pos, product_id in enumerate(product_ids):
            await conn.execute(
                """
                INSERT INTO post_products (id, post_id, product_id, position)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (post_id, product_id) DO NOTHING
                """,
                uuid.uuid4(),
                pub_id,
                product_id,
                pos,
            )

    demo_comments = [
        (
            uuid.UUID("e3000001-0000-4000-8000-000000000001"),
            pubs[0][0],
            BUYER1,
            "Очень красивый оттенок, жду коллекцию!",
        ),
        (
            uuid.UUID("e3000001-0000-4000-8000-000000000002"),
            pubs[0][0],
            BUYER1,
            "А можно фото крупным планом глазури?",
        ),
    ]
    for comment_id, post_id, user_id, body in demo_comments:
        await conn.execute(
            """
            INSERT INTO post_comments (id, post_id, user_id, body, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $5)
            ON CONFLICT (id) DO NOTHING
            """,
            comment_id,
            post_id,
            user_id,
            body,
            NOW,
        )
    await conn.execute(
        """
        UPDATE posts p
        SET comments_count = sub.cnt
        FROM (
            SELECT post_id, COUNT(*)::int AS cnt
            FROM post_comments
            GROUP BY post_id
        ) sub
        WHERE p.id = sub.post_id
        """
    )


async def seed_cart(conn: asyncpg.Connection) -> None:
    await run_ddl(
        conn,
        """
        CREATE TABLE IF NOT EXISTS carts (
            id UUID PRIMARY KEY,
            user_id UUID UNIQUE NOT NULL,
            currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
            promo_code VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            id UUID PRIMARY KEY,
            cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
            product_id UUID NOT NULL,
            offer_id UUID NOT NULL,
            seller_id UUID,
            quantity INT NOT NULL DEFAULT 1,
            price_amount NUMERIC(12,2) NOT NULL,
            title VARCHAR(300) NOT NULL DEFAULT '',
            image_url TEXT,
            is_selected BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (cart_id, offer_id)
        );
        """,
    )
    cart_id = uuid.UUID("c1000000-0000-4000-8000-000000000001")
    await conn.execute(
        """
        INSERT INTO carts (id, user_id, currency) VALUES ($1,$2,'RUB')
        ON CONFLICT (user_id) DO NOTHING
        """,
        cart_id,
        BUYER1,
    )
    items = [
        (uuid.UUID("c2000001-0000-4000-8000-000000000001"), PRODUCT_IDS[0], uuid.UUID("f1000001-0000-4000-8000-000000000001"), SELLERS[0], 2, Decimal("890"), "Керамическая кружка «Море»"),
        (uuid.UUID("c2000001-0000-4000-8000-000000000002"), PRODUCT_IDS[7], uuid.UUID("f1000001-0000-4000-8000-000000000008"), SELLERS[3], 1, Decimal("3500"), "Серебряные серьги «Капля»"),
    ]
    for item_id, product_id, offer_id, seller_id, qty, price, title in items:
        await conn.execute(
            """
            INSERT INTO cart_items (
                id, cart_id, product_id, offer_id, seller_id, quantity, price_amount, title, is_selected
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,TRUE)
            ON CONFLICT (cart_id, offer_id) DO NOTHING
            """,
            item_id,
            cart_id,
            product_id,
            offer_id,
            seller_id,
            qty,
            price,
            title,
        )


async def seed_orders(conn: asyncpg.Connection) -> None:
    await run_ddl(
        conn,
        """
        CREATE TABLE IF NOT EXISTS orders (
            id UUID PRIMARY KEY,
            number VARCHAR(32) UNIQUE NOT NULL,
            user_id UUID NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'created',
            idempotency_key VARCHAR(80) UNIQUE,
            currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
            items_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            delivery_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
            delivery_method VARCHAR(32) NOT NULL DEFAULT 'courier',
            delivery_address TEXT,
            delivery_eta_days INT,
            recipient_name VARCHAR(200) NOT NULL DEFAULT '',
            recipient_phone VARCHAR(32) NOT NULL DEFAULT '',
            payment_method VARCHAR(32) NOT NULL DEFAULT 'card',
            comment TEXT,
            paid_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_id UUID NOT NULL,
            offer_id UUID NOT NULL,
            seller_id UUID,
            title VARCHAR(300) NOT NULL DEFAULT '',
            image_url TEXT,
            quantity INT NOT NULL DEFAULT 1,
            price_amount NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS order_status_history (
            id UUID PRIMARY KEY,
            order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            status VARCHAR(32) NOT NULL,
            comment TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    )
    orders = [
        (
            uuid.UUID("d1000001-0000-4000-8000-000000000001"),
            "HM-SEED-001",
            BUYER1,
            "paid",
            Decimal("1780"),
            Decimal("390"),
            Decimal("0"),
            Decimal("2170"),
        ),
        (
            uuid.UUID("d1000001-0000-4000-8000-000000000002"),
            "HM-SEED-002",
            BUYER2,
            "created",
            Decimal("3500"),
            Decimal("390"),
            Decimal("0"),
            Decimal("3890"),
        ),
    ]
    for oid, number, user_id, status, items_amt, delivery, discount, total in orders:
        await conn.execute(
            """
            INSERT INTO orders (
                id, number, user_id, status, currency, items_amount, delivery_amount,
                discount_amount, total_amount, delivery_method, delivery_address,
                delivery_eta_days, recipient_name, recipient_phone, payment_method, paid_at
            ) VALUES (
                $1,$2,$3,$4,'RUB',$5,$6,$7,$8,'courier','Москва, Тверская 1',$9,$10,$11,'card',$12
            ) ON CONFLICT (id) DO NOTHING
            """,
            oid,
            number,
            user_id,
            status,
            items_amt,
            delivery,
            discount,
            total,
            3,
            "Получатель",
            "+79000000000",
            NOW if status == "paid" else None,
        )
        await conn.execute(
            """
            INSERT INTO order_status_history (id, order_id, status, comment)
            VALUES ($1,$2,$3,'Seed order') ON CONFLICT DO NOTHING
            """,
            uuid.uuid4(),
            oid,
            status,
        )

    await conn.execute(
        """
        INSERT INTO order_items (
            id, order_id, product_id, offer_id, seller_id, title, quantity, price_amount
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING
        """,
        uuid.UUID("d2000001-0000-4000-8000-000000000001"),
        orders[0][0],
        PRODUCT_IDS[0],
        uuid.UUID("f1000001-0000-4000-8000-000000000001"),
        SELLERS[0],
        "Керамическая кружка «Море»",
        2,
        Decimal("890"),
    )
    await conn.execute(
        """
        INSERT INTO order_items (
            id, order_id, product_id, offer_id, seller_id, title, quantity, price_amount
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING
        """,
        uuid.UUID("d2000001-0000-4000-8000-000000000002"),
        orders[1][0],
        PRODUCT_IDS[7],
        uuid.UUID("f1000001-0000-4000-8000-000000000008"),
        SELLERS[3],
        "Серебряные серьги «Капля»",
        1,
        Decimal("3500"),
    )


async def _wait_for_http(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 120.0,
    label: str = "service",
) -> bool:
    """Wait until HTTP endpoint responds (2xx/4xx), not connection refused."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(
                base_url=base_url, headers=headers or {}, timeout=5.0
            ) as client:
                response = await client.get(path)
                if response.status_code < 500:
                    return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(2)
    print(f"seed: {label} not ready at {base_url}{path} after {timeout_seconds}s")
    return False


async def index_meili(documents: list[dict]) -> None:
    headers = {"Authorization": f"Bearer {MEILI_KEY}"}
    async with httpx.AsyncClient(base_url=MEILI_URL, headers=headers, timeout=30.0) as client:
        exists = await client.get("/indexes/products")
        if exists.status_code == 404:
            await client.post("/indexes", json={"uid": "products", "primaryKey": "product_id"})
            await client.patch(
                "/indexes/products/settings",
                json={
                    "searchableAttributes": [
                        "title",
                        "subtitle",
                        "description",
                        "tags",
                        "category_title",
                    ],
                    "filterableAttributes": [
                        "category_id",
                        "category_slug",
                        "seller_id",
                        "is_active",
                        "tags",
                    ],
                    "sortableAttributes": ["rating", "reviews_count", "min_price", "created_at"],
                },
            )
        response = await client.post("/indexes/products/documents", json=documents)
        response.raise_for_status()


async def seed_gorse(documents: list[dict]) -> None:
    if os.getenv("SEED_SKIP_GORSE", "").lower() in ("1", "true", "yes"):
        print("seed: skipping Gorse (SEED_SKIP_GORSE)")
        return
    if not documents:
        print("seed: no documents for Gorse, skip")
        return

    headers = {"X-API-Key": GORSE_KEY}
    gorse_base = GORSE_URL
    ready = await _wait_for_http(
        gorse_base,
        "/api/health/live",
        headers=headers,
        timeout_seconds=60.0,
        label="Gorse",
    )
    if not ready:
        fallback = "http://gorse:8088"
        if gorse_base.rstrip("/") != fallback:
            print(f"seed: retry Gorse at {fallback} …")
            gorse_base = fallback
            ready = await _wait_for_http(
                gorse_base,
                "/api/health/live",
                headers=headers,
                timeout_seconds=60.0,
                label="Gorse",
            )
    if not ready:
        raise RuntimeError(
            f"Gorse API unavailable (tried {GORSE_URL} and http://gorse:8088). "
            "Run: docker compose up -d gorse  (or SEED_SKIP_GORSE=1 to skip)"
        )

    items = [
        {
            "ItemId": doc["product_id"],
            "Categories": [doc.get("category_slug") or "handmade"],
            "Labels": doc.get("tags") or [],
            "Timestamp": NOW.isoformat(),
        }
        for doc in documents
    ]
    feedback = [
        {
            "FeedbackType": "view",
            "UserId": str(BUYER1),
            "ItemId": documents[0]["product_id"],
            "Timestamp": NOW.isoformat(),
        },
        {
            "FeedbackType": "purchase",
            "UserId": str(BUYER1),
            "ItemId": documents[0]["product_id"],
            "Timestamp": NOW.isoformat(),
        },
        {
            "FeedbackType": "view",
            "UserId": str(BUYER2),
            "ItemId": documents[7]["product_id"],
            "Timestamp": NOW.isoformat(),
        },
    ]
    async with httpx.AsyncClient(base_url=gorse_base, headers=headers, timeout=60.0) as client:
        items_resp = await client.post("/api/items", json=items)
        items_resp.raise_for_status()
        fb_resp = await client.post("/api/feedback", json=feedback)
        fb_resp.raise_for_status()
    print(f"seed: Gorse loaded {len(items)} items, {len(feedback)} feedback rows")


async def main() -> None:
    users = await asyncpg.connect(dsn("ecom_users"))
    goods = await asyncpg.connect(dsn("ecom_goods"))
    pubs = await asyncpg.connect(dsn("ecom_publications"))
    cart = await asyncpg.connect(dsn("ecom_cart"))
    orders = await asyncpg.connect(dsn("ecom_orders"))
    try:
        await seed_users(users)
        meili_docs = await seed_goods(goods)
        await seed_publications(pubs)
        await seed_cart(cart)
        await seed_orders(orders)
    finally:
        await users.close()
        await goods.close()
        await pubs.close()
        await cart.close()
        await orders.close()

    print("seed: indexing MeiliSearch…")
    await index_meili(meili_docs)
    print("seed: loading Gorse…")
    await seed_gorse(meili_docs)
    print("seed: done (postgres + meili + gorse)")


if __name__ == "__main__":
    asyncio.run(main())
