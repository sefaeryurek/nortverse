"""Giriş / çıkış / oturum bilgisi (Sprint 93)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    COOKIE_NAME,
    SESSION_DAYS,
    auth_required,
    forget_failures,
    last_unlock,
    login,
    login_blocked,
    logout,
    record_login_failure,
)
from app.db.connection import get_session

router = APIRouter()


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


@router.post("/api/auth/login")
async def post_login(body: LoginBody, request: Request, response: Response) -> dict:
    username = body.username.strip().lower()
    if login_blocked(username):
        async with get_session() as session:
            unlocked_at = await last_unlock(session, username)
        if unlocked_at is not None:
            forget_failures(username, unlocked_at)
        if login_blocked(username):
            raise HTTPException(429, "Çok fazla hatalı deneme. 15 dakika sonra tekrar deneyin.")
    async with get_session() as session:
        result = await login(session, username, body.password, request.headers.get("user-agent"))
    if result is None:
        record_login_failure(username)
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı")
    token, user = result
    # Sprint 94 E8: Tailscale (HTTPS) üzerinden girildiyse çerez sadece HTTPS'te gider. Başlık taklit edilse bile
    # çerez yalnızca daha sıkı olur (yerel http://127.0.0.1 girişinde secure kapalı kalır).
    secure = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/",
                        secure=secure)
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
