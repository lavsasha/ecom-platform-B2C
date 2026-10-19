from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.app import ConflictError, NotFoundError, UnauthorizedError
from common.db import Database
from dto import seller_to_dto, user_to_dto
from models import Address, Seller, Subscription, User

router = APIRouter(prefix="/api/v1")
_db: Database | None = None


def bind_db(database: Database) -> None:
    global _db
    _db = database


async def get_session() -> AsyncIterator[AsyncSession]:
    assert _db is not None
    async for session in _db.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


class AddressIn(BaseModel):
    label: str | None = None
    city: str
    street: str
    building: str
    apartment: str | None = None
    postal_code: str | None = None
    recipient_name: str
    recipient_phone: str
    is_default: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=6)
    phone: str | None = None
    avatar: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = None
    avatar: str | None = None
    bio: str | None = None
    is_active: bool | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SellerBatchRequest(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=200)


class UserBatchRequest(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=200)


class SubscriptionIn(BaseModel):
    notifications_enabled: bool = True


class BecomeSellerIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


async def _user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


@router.post("/auth/login", tags=["auth"])
async def login(payload: LoginIn, session: SessionDep) -> dict:
    user = await session.scalar(select(User).where(User.email == payload.email))
    if user is None or not _verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    return {"user": user_to_dto(user)}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(payload: UserCreate, session: SessionDep) -> dict:
    if not payload.password:
        raise ConflictError("Password required")
    exists = await session.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if exists:
        raise ConflictError("Email or username already taken")
    user = User(
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name,
        password_hash=_hash_password(payload.password),
        phone=payload.phone,
        avatar=payload.avatar,
        roles=["buyer"],
    )
    session.add(user)
    await session.flush()
    return {"user": user_to_dto(user)}


@router.get("/users/{user_id}", tags=["users"])
async def get_user(user_id: uuid.UUID, session: SessionDep) -> dict:
    return {"user": user_to_dto(await _user(session, user_id))}


@router.post("/users/batch", tags=["users"])
async def users_batch(payload: UserBatchRequest, session: SessionDep) -> dict:
    if not payload.ids:
        return {"items": []}
    rows = await session.scalars(select(User).where(User.id.in_(payload.ids)))
    by_id = {user.id: user for user in rows.all()}
    items = [user_to_dto(by_id[user_id]) for user_id in payload.ids if user_id in by_id]
    return {"items": items}


@router.patch("/users/{user_id}", tags=["users"])
async def update_user(user_id: uuid.UUID, payload: UserUpdate, session: SessionDep) -> dict:
    user = await _user(session, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "display_name" in data:
        user.display_name = data["display_name"]
    if "phone" in data:
        user.phone = data["phone"]
    if "avatar" in data:
        user.avatar = data["avatar"]
    if "bio" in data:
        user.bio = data["bio"]
    if "is_active" in data:
        user.is_active = data["is_active"]
    await session.flush()
    return {"user": user_to_dto(user)}


@router.get("/sellers", tags=["sellers"])
async def list_sellers(
    session: SessionDep,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
) -> dict:
    stmt = select(Seller)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Seller.username.ilike(like),
                Seller.display_name.ilike(like),
                Seller.bio.ilike(like),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    offset = (page - 1) * page_size
    rows = await session.scalars(
        stmt.order_by(Seller.followers_count.desc()).offset(offset).limit(page_size)
    )
    return {
        "items": [seller_to_dto(s) for s in rows.all()],
        "total": int(total or 0),
        "page": page,
        "pageSize": page_size,
    }


@router.get("/sellers/popular", tags=["sellers"])
async def list_popular_sellers(
    session: SessionDep, limit: int = Query(default=12, ge=1, le=50)
) -> dict:
    rows = await session.scalars(
        select(Seller).order_by(Seller.followers_count.desc()).limit(limit)
    )
    return {"items": [seller_to_dto(s) for s in rows.all()]}


@router.post("/sellers/batch", tags=["sellers"])
async def sellers_batch(payload: SellerBatchRequest, session: SessionDep) -> dict:
    if not payload.ids:
        return {"items": []}
    rows = await session.scalars(select(Seller).where(Seller.id.in_(payload.ids)))
    by_id = {s.id: s for s in rows.all()}
    items = [seller_to_dto(by_id[i]) for i in payload.ids if i in by_id]
    return {"items": items}


@router.get("/sellers/by-username/{username}", tags=["sellers"])
async def get_seller_by_username(username: str, session: SessionDep) -> dict:
    seller = await session.scalar(select(Seller).where(Seller.username == username))
    if seller is None:
        raise NotFoundError(f"Seller {username} not found")
    return {"seller": seller_to_dto(seller)}


@router.get("/sellers/{seller_id}", tags=["sellers"])
async def get_seller(seller_id: uuid.UUID, session: SessionDep) -> dict:
    seller = await session.get(Seller, seller_id)
    if seller is None:
        raise NotFoundError(f"Seller {seller_id} not found")
    return {"seller": seller_to_dto(seller)}


@router.get("/users/{user_id}/subscriptions", tags=["subscriptions"])
async def list_subscriptions(user_id: uuid.UUID, session: SessionDep) -> dict:
    rows = await session.scalars(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    return {
        "items": [
            {
                "id": str(s.id),
                "userId": str(s.user_id),
                "sellerId": str(s.seller_id),
                "notificationsEnabled": s.notifications_enabled,
                "createdAt": s.created_at.isoformat(),
            }
            for s in rows.all()
        ]
    }


@router.get("/users/{user_id}/subscriptions/{seller_id}/status", tags=["subscriptions"])
async def subscription_status(
    user_id: uuid.UUID, seller_id: uuid.UUID, session: SessionDep
) -> dict:
    row = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.seller_id == seller_id
        )
    )
    return {"sellerId": str(seller_id), "subscribed": row is not None}


@router.put("/users/{user_id}/subscriptions/{seller_id}", tags=["subscriptions"])
async def subscribe(
    user_id: uuid.UUID, seller_id: uuid.UUID, payload: SubscriptionIn, session: SessionDep
) -> dict:
    await _user(session, user_id)
    if await session.get(Seller, seller_id) is None:
        raise NotFoundError(f"Seller {seller_id} not found")
    row = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.seller_id == seller_id
        )
    )
    if row is None:
        row = Subscription(
            user_id=user_id,
            seller_id=seller_id,
            notifications_enabled=payload.notifications_enabled,
        )
        session.add(row)
        seller = await session.get(Seller, seller_id)
        if seller:
            seller.followers_count += 1
    else:
        row.notifications_enabled = payload.notifications_enabled
    await session.flush()
    return {
        "subscription": {
            "id": str(row.id),
            "sellerId": str(seller_id),
            "notificationsEnabled": row.notifications_enabled,
        }
    }


@router.delete(
    "/users/{user_id}/subscriptions/{seller_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["subscriptions"],
)
async def unsubscribe(
    user_id: uuid.UUID, seller_id: uuid.UUID, session: SessionDep
) -> Response:
    result = await session.execute(
        delete(Subscription).where(
            Subscription.user_id == user_id, Subscription.seller_id == seller_id
        )
    )
    if not result.rowcount:
        raise NotFoundError("Subscription not found")
    seller = await session.get(Seller, seller_id)
    if seller:
        seller.followers_count = max(0, seller.followers_count - 1)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/become-seller", tags=["sellers"])
async def become_seller(
    user_id: uuid.UUID, payload: BecomeSellerIn, session: SessionDep
) -> dict:
    user = await _user(session, user_id)
    if await session.scalar(select(Seller).where(Seller.username == payload.username)):
        raise ConflictError("Username already taken")
    if await session.scalar(select(Seller).where(Seller.user_id == user.id)):
        raise ConflictError("Already a seller")
    seller = Seller(
        user_id=user.id,
        username=payload.username,
        display_name=payload.display_name,
        bio=payload.bio,
        avatar=user.avatar,
    )
    roles = list(user.roles or ["buyer"])
    if "seller" not in roles:
        roles.append("seller")
    user.roles = roles
    session.add(seller)
    await session.flush()
    return {"user": user_to_dto(user), "seller": seller_to_dto(seller)}


@router.get("/users/{user_id}/addresses", tags=["users"])
async def list_addresses(user_id: uuid.UUID, session: SessionDep) -> list[dict]:
    await _user(session, user_id)
    rows = await session.scalars(
        select(Address).where(Address.user_id == user_id).order_by(Address.is_default.desc())
    )
    return [
        {
            "id": str(a.id),
            "label": a.label,
            "city": a.city,
            "street": a.street,
            "building": a.building,
            "apartment": a.apartment,
            "postalCode": a.postal_code,
            "recipientName": a.recipient_name,
            "recipientPhone": a.recipient_phone,
            "isDefault": a.is_default,
        }
        for a in rows.all()
    ]
