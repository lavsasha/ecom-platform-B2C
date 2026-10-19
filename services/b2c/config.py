from __future__ import annotations

from common.app import BaseServiceSettings


class B2CSettings(BaseServiceSettings):
    service_name: str = "b2c"
    service_title: str = "B2C API (BFF + frontend contract)"
    cors_origin: str = "http://localhost:3000"
    auth_jwt_secret: str = "changeme"
    auth_jwt_algorithm: str = "HS256"
    auth_access_ttl_seconds: int = 3600
    auth_cookie_name: str = "auth-token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "strict"
    auth_dev_mode: bool = True
    payment_stub_url: str = "https://yoomoney.ru/checkout/demo"
    users_url: str = "http://users:8000"
    publications_url: str = "http://publications:8000"
    cart_url: str = "http://cart:8000"
    orders_url: str = "http://orders:8000"
    goods_url: str = "http://goods:8000"
    search_url: str = "http://search:8000"
    eventer_url: str = "http://eventer:8000"
    gorse_url: str = "http://gorse:8088"
    gorse_api_key: str = "gorseApiKeyForLocalDevOnly"
    upstream_timeout_seconds: float = 2.0
    upstream_retries: int = 2
