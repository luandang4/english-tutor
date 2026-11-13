"""Accounts and login sessions."""

import time
from collections import defaultdict, deque
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    new_session_token,
    password_problem,
    token_hash,
    verify_password,
)
from app.db.base import utcnow
from app.models.conversation import ConversationSession
from app.models.lesson import Lesson
from app.models.pronunciation import PronunciationAttempt
from app.models.user import AuthSession, User
from app.models.vocab import VocabCard
from app.models.writing import WritingTask
from app.services import access

OWNED_MODELS = (Lesson, WritingTask, VocabCard, ConversationSession, PronunciationAttempt)


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def check_password_strength(password: str) -> None:
    if problem := password_problem(password):
        raise AuthError(problem, 422)


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register(session: AsyncSession, *, email: str, password: str, display_name: str) -> User:
    """Self-service sign-up from the web. New accounts get the admin's default features (none = wait for
    approval), so open sign-up cannot be used to spend AI quota."""
    if not await access.registration_open(session):
        raise AuthError("Đăng ký tài khoản mới đang tắt.", 403)
    return await create_user(session, email=email, password=password, display_name=display_name)


async def create_user(
    session: AsyncSession, *, email: str, password: str, display_name: str, admin: bool = False
) -> User:
    """Create an account (also used by scripts/create_user.py). The very first account becomes admin."""
    check_password_strength(password)
    email = normalize_email(email)
    if await session.scalar(select(User.id).where(User.email == email)):
        raise AuthError("Email này đã được đăng ký.", 409)
    is_first = not await session.scalar(select(User.id).limit(1))
    is_admin = admin or is_first
    user = User(
        email=email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        is_admin=is_admin,
        features=access.ALL_FEATURES if is_admin else (await access.get_system(session)).default_features,
    )
    session.add(user)
    await session.flush()
    if is_first:
        await _claim_unowned_data(session, user.id)
    await session.commit()
    return user


async def _claim_unowned_data(session: AsyncSession, user_id: int) -> None:
    """Learning data created before accounts existed belongs to the first account."""
    for model in OWNED_MODELS:
        await session.execute(update(model).where(model.user_id.is_(None)).values(user_id=user_id))


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(DUMMY_HASH, password)  # same cost as a real check
        raise AuthError("Email hoặc mật khẩu không đúng.", 401)
    if not verify_password(user.password_hash, password):
        raise AuthError("Email hoặc mật khẩu không đúng.", 401)
    if not user.is_active:
        raise AuthError("Tài khoản đã bị khoá. Hãy liên hệ admin.", 403)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    return user


async def create_session(session: AsyncSession, user: User) -> str:
    token = new_session_token()
    now = utcnow()
    user.last_login_at = now  # sign-up also counts as a login
    await session.execute(delete(AuthSession).where(AuthSession.expires_at < now))  # housekeeping
    session.add(
        AuthSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now + timedelta(days=get_settings().session_days),
        )
    )
    await session.commit()
    return token


async def user_for_token(session: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    row = await session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if row is None or row.expires_at < utcnow():
        return None
    user = await session.get(User, row.user_id)
    return user if user is not None and user.is_active else None


async def end_session(session: AsyncSession, token: str | None) -> None:
    if token:
        await session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        await session.commit()


async def change_password(session: AsyncSession, user: User, current: str, new: str, keep_token: str) -> None:
    if not verify_password(user.password_hash, current):
        raise AuthError("Mật khẩu hiện tại không đúng.", 400)
    check_password_strength(new)
    user.password_hash = hash_password(new)
    # sign out every other device
    await session.execute(
        delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != token_hash(keep_token))
    )
    await session.commit()


class LoginLimiter:
    """In-memory brute-force guard: max N failed logins per client IP within a window."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 900) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q = self._failures[key]
        while q and time.monotonic() - q[0] > self.window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        if len(self._prune(key)) >= self.max_failures:
            raise AuthError("Đăng nhập sai quá nhiều lần, hãy thử lại sau 15 phút.", 429)

    def fail(self, key: str) -> None:
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


login_limiter = LoginLimiter()
