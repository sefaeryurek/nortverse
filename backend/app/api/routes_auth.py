"""Giriş / çıkış / oturum bilgisi (Sprint 93)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, SESSION_DAYS, auth_required, login, logout, record_failure, too_many_failures
from app.db.connection import get_session

router = APIRouter()


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


@router.post("/api/auth/login")
async def post_login(body: LoginBody, request: Request, response: Response) -> dict:
    username = body.username.strip().lower()
    keys = (f"u:{username}", f"ip:{_client_ip(request)}")
    if too_many_failures(*keys):
        raise HTTPException(429, "Çok fazla hatalı deneme. 15 dakika sonra tekrar deneyin.")
    async with get_session() as session:
        result = await login(session, username, body.password, request.headers.get("user-agent"))
    if result is None:
        record_failure(*keys)
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı")
    token, user = result
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/")
    return {"username": user.username, "is_admin": user.is_admin}


@router.post("/api/auth/logout")
async def post_logout(request: Request, response: Response) -> dict:
    await logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/api/auth/me")
async def get_me(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user is None and not auth_required():
        return {"username": "yerel", "is_admin": True}  # giriş kapalı (yerel deneme / testler)
    if user is None:
        raise HTTPException(401, "Giriş gerekli")
    return {"username": user.username, "is_admin": user.is_admin}
