"""Site hesapları (Sprint 93 — paylaşım). Kayıt sayfası yok; hesapları site sahibi buradan açar."""

import asyncio
import re
import secrets

import typer

from app.cli._helpers import console

_NAME_RE = re.compile(r"^[a-z0-9_.-]{3,40}$")


def _password(value: str | None) -> tuple[str, bool]:
    if value:
        if len(value) < 8:
            raise typer.BadParameter("Şifre en az 8 karakter olmalı")
        return value, False
    return secrets.token_urlsafe(9), True  # verilmezse güçlü rastgele şifre üretilir ve bir kez gösterilir


def create_user_cmd(
    username: str = typer.Argument(..., help="Kullanıcı adı (küçük harf, rakam, . _ -)"),
    password: str = typer.Option(None, "--password", help="Verilmezse rastgele şifre üretilir"),
    admin: bool = typer.Option(False, "--admin", help="Yönetici: yeni maç çekimi gibi ağır işleri tetikleyebilir"),
) -> None:
    """Yeni hesap açar."""
    name = username.strip().lower()
    if not _NAME_RE.match(name):
        raise typer.BadParameter("Kullanıcı adı 3-40 karakter: küçük harf, rakam, . _ -")
    secret, generated = _password(password)

    async def run() -> bool:
        from sqlalchemy import select

        from app.auth import hash_password
        from app.db.connection import get_session
        from app.db.models import User

        async with get_session() as session:
            if (await session.execute(select(User.id).where(User.username == name))).first():
                return False
            session.add(User(username=name, password_hash=hash_password(secret), is_admin=admin))
        return True

    if not asyncio.run(run()):
        console.print(f"[red]'{name}' zaten var. Şifre değiştirmek için: set-password {name}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Hesap açıldı:[/green] {name}{' (yönetici)' if admin else ''}")
    if generated:
        console.print(f"Şifre: [bold]{secret}[/bold]  (bir kez gösterilir, not alın)")


def set_password_cmd(
    username: str = typer.Argument(...),
    password: str = typer.Option(None, "--password", help="Verilmezse rastgele şifre üretilir"),
) -> None:
    """Şifreyi değiştirir; o hesabın açık oturumları kapanır."""
    name = username.strip().lower()
    secret, generated = _password(password)

    async def run() -> bool:
        from sqlalchemy import delete, select, update

        from app.auth import forget_user_sessions_cache, hash_password
        from app.db.connection import get_session
        from app.db.models import User, UserSession

        async with get_session() as session:
            user_id = (await session.execute(select(User.id).where(User.username == name))).scalar_one_or_none()
            if user_id is None:
                return False
            await session.execute(update(User).where(User.id == user_id).values(password_hash=hash_password(secret)))
            await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
        forget_user_sessions_cache()
        return True

    if not asyncio.run(run()):
        console.print(f"[red]'{name}' bulunamadı[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Şifre değişti:[/green] {name} (açık oturumları kapatıldı)")
    if generated:
        console.print(f"Yeni şifre: [bold]{secret}[/bold]")


def list_users_cmd() -> None:
    """Hesapları listeler."""
    async def run():
        from sqlalchemy import func, select

        from app.db.connection import get_session
        from app.db.models import User, UserSession

        async with get_session() as session:
            return (await session.execute(
                select(User.username, User.is_admin, User.disabled, User.created_at, func.count(UserSession.token_hash))
                .outerjoin(UserSession, UserSession.user_id == User.id).group_by(User.id).order_by(User.id)
            )).all()

    for name, is_admin, disabled, created, sessions in asyncio.run(run()):
        flags = ", ".join(f for f, on in (("yönetici", is_admin), ("kapalı", disabled)) if on)
        console.print(f"{name:20s} {created:%Y-%m-%d}  açık oturum: {sessions}  {flags}")


def unlock_cmd(
    username: str = typer.Argument(None, help="Kilidi açılacak kullanıcı adı"),
    all_users: bool = typer.Option(False, "--all", help="Genel kilit dahil tüm giriş kilitlerini aç"),
) -> None:
    """Çok fazla hatalı denemeyle kilitlenen girişi açar (Sprint 94 E3).

    Sayaçlar backend'in belleğindedir; bu komut audit_log'a kayıt düşer, backend bir sonraki giriş
    denemesinde kaydı görüp o ana kadarki hataları unutur. Backend'i yeniden başlatmaya gerek yok.
    """
    if not username and not all_users:
        raise typer.BadParameter("Kullanıcı adı ya da --all verin")
    from app.auth import UNLOCK_OPERATION, _GLOBAL_KEY

    target = _GLOBAL_KEY if all_users else username.strip().lower()

    async def run() -> None:
        from app.db.connection import get_session
        from app.db.models import AuditLog

        async with get_session() as session:
            session.add(AuditLog(operation=UNLOCK_OPERATION, actor="cli", details={"username": target}))

    asyncio.run(run())
    console.print(f"[green]Giriş kilidi açıldı:[/green] {'tüm hesaplar' if all_users else target}")


async def _drop_sessions(user_name: str | None) -> int:
    """Oturumları siler (bir kullanıcının ya da herkesin); silinen oturum sayısı."""
    from sqlalchemy import delete, select

    from app.db.connection import get_session
    from app.db.models import User, UserSession

    async with get_session() as session:
        stmt = delete(UserSession)
        if user_name is not None:
            stmt = stmt.where(UserSession.user_id.in_(select(User.id).where(User.username == user_name)))
        return (await session.execute(stmt)).rowcount or 0


def disable_user_cmd(
    username: str = typer.Argument(..., help="Kapatılacak hesap"),
    enable: bool = typer.Option(False, "--enable", help="Kapatılmış hesabı yeniden aç"),
) -> None:
    """Hesabı kapatır (giriş yapamaz) ve açık oturumlarını siler; --enable ile geri açar (Sprint 94 E8).

    Backend çözülmüş oturumları en fazla 15 sn bellekte tutar; açık canlı bağlantı en geç ~1 dk içinde kapanır.
    """
    name = username.strip().lower()

    async def run() -> int | None:
        from sqlalchemy import update

        from app.db.connection import get_session
        from app.db.models import AuditLog, User

        async with get_session() as session:
            result = await session.execute(update(User).where(User.username == name).values(disabled=not enable))
            if not result.rowcount:
                return None
            session.add(AuditLog(operation="user_enable" if enable else "user_disable", actor="cli",
                                 details={"username": name}))
        return 0 if enable else await _drop_sessions(name)

    dropped = asyncio.run(run())
    if dropped is None:
        console.print(f"[red]'{name}' bulunamadı[/red]")
        raise typer.Exit(1)
    if enable:
        console.print(f"[green]Hesap yeniden açıldı:[/green] {name}")
    else:
        console.print(f"[yellow]Hesap kapatıldı:[/yellow] {name} — {dropped} oturum silindi")


def logout_all_cmd(
    username: str = typer.Argument(None, help="Sadece bu hesabın oturumları (boşsa herkes)"),
) -> None:
    """Tüm açık oturumları kapatır — herkes yeniden giriş yapar (şüpheli durumda, Sprint 94 E8)."""
    name = username.strip().lower() if username else None
    dropped = asyncio.run(_drop_sessions(name))
    console.print(f"[yellow]{dropped} oturum kapatıldı[/yellow]{' (' + name + ')' if name else ' (tüm hesaplar)'}")
