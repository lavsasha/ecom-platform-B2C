from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field

from config import B2CSettings
from contract_api.cookies import clear_auth_cookie, set_auth_cookie
from contract_api.envelope import err, ok
from contract_api.errors import ApiError, forbidden, server_error
from contract_api.jwt_auth import issue_token, require_user_id, user_id_from_request
from facade import FrontendFacade

router = APIRouter(prefix="/api", tags=["frontend-contract"])

_facade: FrontendFacade | None = None
_settings: B2CSettings | None = None


def bind(facade: FrontendFacade, settings: B2CSettings) -> None:
    global _facade, _settings
    _facade = facade
    _settings = settings


def _f() -> FrontendFacade:
    assert _facade is not None
    return _facade


def _s() -> B2CSettings:
    assert _settings is not None
    return _settings


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    displayName: str
    username: str


class PatchMeBody(BaseModel):
    displayName: str | None = None
    bio: str | None = None
    avatar: str | None = None


class BecomeSellerBody(BaseModel):
    username: str
    displayName: str
    bio: str | None = None


class OrderLineIn(BaseModel):
    productId: str
    quantity: int = Field(ge=1)


class OrderGroupIn(BaseModel):
    sellerId: str
    delivery: str
    items: list[OrderLineIn]
    pickupPoint: dict | None = None


class ContactIn(BaseModel):
    name: str
    phone: str
    email: EmailStr


class CreateOrdersBody(BaseModel):
    groups: list[OrderGroupIn]
    contact: ContactIn


PLANS = [
    {
        "tier": "free",
        "name": "Free",
        "price": 0,
        "features": [
            {"label": "Товаров до 10", "included": True},
            {"label": "Постов до 5", "included": True},
            {"label": "Аналитика", "included": False},
            {"label": "Приоритет в выдаче", "included": False},
            {"label": "Комиссия 10%", "included": True},
        ],
    },
    {
        "tier": "premium",
        "name": "Premium",
        "price": 990,
        "features": [
            {"label": "Товаров до 100", "included": True},
            {"label": "Постов до 50", "included": True},
            {"label": "Аналитика", "included": True},
            {"label": "Приоритет в выдаче", "included": True},
            {"label": "Комиссия 5%", "included": True},
        ],
    },
]


@router.post("/auth/login")
async def auth_login(body: LoginBody) -> Response:
    user = await _f().login(body.email, body.password)
    token = issue_token(_s(), uuid.UUID(user["id"]))
    resp = ok({"user": user})
    set_auth_cookie(resp, _s(), token)
    return resp


@router.post("/auth/register", status_code=201)
async def auth_register(body: RegisterBody) -> Response:
    user = await _f().register(body.model_dump())
    token = issue_token(_s(), uuid.UUID(user["id"]))
    resp = ok({"user": user}, status_code=201)
    set_auth_cookie(resp, _s(), token)
    return resp


@router.post("/auth/logout")
async def auth_logout() -> Response:
    resp = ok(None)
    clear_auth_cookie(resp, _s())
    return resp


@router.get("/auth/me")
async def auth_me(request: Request) -> Response:
    uid = require_user_id(request, _s())
    user = await _f().me(uid)
    return ok({"user": user})


@router.post("/auth/refresh")
async def auth_refresh(request: Request) -> Response:
    uid = require_user_id(request, _s())
    token = issue_token(_s(), uid)
    resp = ok(None)
    set_auth_cookie(resp, _s(), token)
    return resp


@router.post("/auth/yandex")
async def auth_yandex() -> Response:
    raise server_error("Яндекс ID пока не подключён")


@router.patch("/users/me")
async def users_patch_me(request: Request, body: PatchMeBody) -> Response:
    uid = require_user_id(request, _s())
    user = await _f().patch_me(uid, body.model_dump(exclude_unset=True))
    return ok({"user": user})


@router.post("/users/me/become-seller")
async def users_become_seller(request: Request, body: BecomeSellerBody) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().become_seller(uid, body.model_dump())
    return ok(data)


@router.get("/sellers")
async def sellers_list(
    request: Request,
    q: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> Response:
    viewer = user_id_from_request(request, _s())
    data = await _f().list_sellers(q, page, pageSize, viewer)
    return ok(data)


@router.get("/sellers/{username}/posts")
async def sellers_posts(
    username: str,
    request: Request,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> Response:
    viewer = user_id_from_request(request, _s())
    seller = await _f().seller_by_username(username, viewer)
    sid = uuid.UUID(seller["id"])
    data = await _f().list_posts(
        q=None,
        page=page,
        page_size=pageSize,
        cursor=None,
        limit=pageSize,
        viewer_id=viewer,
        seller_id=sid,
    )
    return ok(data)


@router.get("/sellers/{username}/products")
async def sellers_products(
    username: str,
    request: Request,
    q: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> Response:
    viewer = user_id_from_request(request, _s())
    seller = await _f().seller_by_username(username, viewer)
    data = await _f().list_products(
        q=q,
        page=page,
        page_size=pageSize,
        seller_id=uuid.UUID(seller["id"]),
        delivery=None,
        sale_mode=None,
        viewer_id=viewer,
    )
    return ok(data)


@router.get("/sellers/{username}")
async def sellers_by_username(username: str, request: Request) -> Response:
    viewer = user_id_from_request(request, _s())
    seller = await _f().seller_by_username(username, viewer)
    return ok(seller)


@router.post("/sellers/{seller_id}/follow")
async def sellers_follow(seller_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().follow(uid, uuid.UUID(seller_id))
    return ok(data)


@router.delete("/sellers/{seller_id}/follow")
async def sellers_unfollow(seller_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().unfollow(uid, uuid.UUID(seller_id))
    return ok(data)


@router.get("/products")
async def products_list(
    request: Request,
    q: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    sellerId: str | None = None,
    delivery: str | None = None,
    saleMode: str | None = None,
) -> Response:
    viewer = user_id_from_request(request, _s())
    sid = uuid.UUID(sellerId) if sellerId else None
    data = await _f().list_products(
        q=q,
        page=page,
        page_size=pageSize,
        seller_id=sid,
        delivery=delivery,
        sale_mode=saleMode,
        viewer_id=viewer,
    )
    return ok(data)


@router.get("/products/{product_id}")
async def products_get(product_id: str, request: Request) -> Response:
    viewer = user_id_from_request(request, _s())
    product = await _f().get_product(uuid.UUID(product_id), viewer)
    return ok(product)


@router.get("/posts")
async def posts_list(
    request: Request,
    q: str | None = None,
    page: int | None = Query(None, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    limit: int = Query(10, ge=1, le=50),
) -> Response:
    viewer = user_id_from_request(request, _s())
    data = await _f().list_posts(
        q=q,
        page=page,
        page_size=pageSize,
        cursor=cursor,
        limit=limit,
        viewer_id=viewer,
    )
    return ok(data)


@router.get("/posts/{post_id}")
async def posts_get(post_id: str, request: Request) -> Response:
    viewer = user_id_from_request(request, _s())
    post = await _f().get_post(uuid.UUID(post_id), viewer)
    return ok(post)


@router.post("/posts/{post_id}/like")
async def posts_like(post_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().like_post(uid, uuid.UUID(post_id))
    return ok(data)


@router.delete("/posts/{post_id}/like")
async def posts_unlike(post_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().unlike_post(uid, uuid.UUID(post_id))
    return ok(data)


class CommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/posts/{post_id}/comments")
async def posts_comments_list(
    post_id: str,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    viewer = user_id_from_request(request, _s())
    data = await _f().list_post_comments(
        uuid.UUID(post_id),
        cursor=cursor,
        limit=limit,
        viewer_id=viewer,
    )
    return ok(data)


@router.post("/posts/{post_id}/comments", status_code=201)
async def posts_comments_create(
    post_id: str, request: Request, body: CommentBody
) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().create_post_comment(uid, uuid.UUID(post_id), body.body.strip())
    return ok(data, status_code=201)


@router.patch("/comments/{comment_id}")
async def comments_update(
    comment_id: str, request: Request, body: CommentBody
) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().update_post_comment(uid, uuid.UUID(comment_id), body.body.strip())
    return ok(data)


@router.delete("/comments/{comment_id}")
async def comments_delete(comment_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    await _f().delete_post_comment(uid, uuid.UUID(comment_id))
    return ok(None)


@router.post("/orders", status_code=201)
async def orders_create(request: Request, body: CreateOrdersBody) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().create_orders_from_cart(
        uid,
        body.model_dump(),
        _s().payment_stub_url,
    )
    return ok(data, status_code=201)


@router.get("/orders")
async def orders_list(
    request: Request,
    role: str = Query("buyer"),
    status: str | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
) -> Response:
    uid = require_user_id(request, _s())
    data = await _f().list_orders(uid, page, pageSize, role, status)
    return ok(data)


@router.get("/orders/{order_id}")
async def orders_get(order_id: str, request: Request) -> Response:
    uid = require_user_id(request, _s())
    order = await _f().get_order(uuid.UUID(order_id), uid)
    return ok(order)


@router.get("/plans")
async def plans_list() -> Response:
    return ok(PLANS)


@router.get("/seller/profile")
async def seller_profile_stub() -> Response:
    raise forbidden("Кабинет продавца — отдельный модуль")
