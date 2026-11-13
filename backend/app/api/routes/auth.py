"""Register / login / logout with an HttpOnly session cookie."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.core.constants import FEATURE_INFO
from app.models.user import User
from app.schemas.api import FeatureUsage, LoginIn, PasswordChangeIn, RegisterIn, UserOut
from app.services import access, auth

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie,
        token,
        max_age=s.session_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )


async def _user_out(session: SessionDep, user: User) -> UserOut:
    features = access.effective_features(user, await access.get_system(session))
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        is_admin=user.is_admin,
        features=features,
        pending=not user.is_admin and not user.features,
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, response: Response, session: SessionDep):  # noqa: ANN201
    try:
        user = await auth.register(session, email=body.email, password=body.password, display_name=body.display_name)
    except auth.AuthError as e:
        raise HTTPException(e.status, str(e)) from e
    _set_cookie(response, await auth.create_session(session, user))
    return await _user_out(session, user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response, session: SessionDep):  # noqa: ANN201
    key = _client_key(request)
    try:
        auth.login_limiter.check(key)
        user = await auth.authenticate(session, email=body.email, password=body.password)
    except auth.AuthError as e:
        if e.status == 401:
            auth.login_limiter.fail(key)
        raise HTTPException(e.status, str(e)) from e
    auth.login_limiter.reset(key)
    _set_cookie(response, await auth.create_session(session, user))
    return await _user_out(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep) -> Response:
    s = get_settings()
    await auth.end_session(session, request.cookies.get(s.session_cookie))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(s.session_cookie, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser, session: SessionDep) -> UserOut:
    return await _user_out(session, user)


@router.get("/me/usage", response_model=list[FeatureUsage])
async def my_usage(user: CurrentUser, session: SessionDep) -> list[FeatureUsage]:
    """Today's usage and daily limit for each feature the user may use."""
    system = await access.get_system(session)
    out = []
    for feature in access.effective_features(user, system):
        limit = None if user.is_admin or not system.daily_limits.get(feature) else system.daily_limits[feature]
        used = await access.usage_today(session, user.id, feature)
        out.append(FeatureUsage(feature=feature, used=used, limit=limit, **FEATURE_INFO[feature]))
    return out


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChangeIn, request: Request, user: CurrentUser, session: SessionDep) -> Response:
    try:
        await auth.change_password(
            session, user, body.current_password, body.new_password, request.cookies[get_settings().session_cookie]
        )
    except auth.AuthError as e:
        raise HTTPException(e.status, str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
