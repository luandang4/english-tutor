"""Register / login / logout with an HttpOnly session cookie."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.schemas.api import LoginIn, PasswordChangeIn, RegisterIn, UserOut
from app.services import auth

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


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, response: Response, session: SessionDep):  # noqa: ANN201
    try:
        user = await auth.register(session, email=body.email, password=body.password, display_name=body.display_name)
    except auth.AuthError as e:
        raise HTTPException(e.status, str(e)) from e
    _set_cookie(response, await auth.create_session(session, user))
    return user


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
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep) -> Response:
    s = get_settings()
    await auth.end_session(session, request.cookies.get(s.session_cookie))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(s.session_cookie, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):  # noqa: ANN201
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChangeIn, request: Request, user: CurrentUser, session: SessionDep) -> Response:
    try:
        await auth.change_password(
            session, user, body.current_password, body.new_password, request.cookies[get_settings().session_cookie]
        )
    except auth.AuthError as e:
        raise HTTPException(e.status, str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
