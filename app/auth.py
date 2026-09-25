from __future__ import annotations

from fastapi import HTTPException, Request, status

from .security import verify_session

SESSION_COOKIE = "reys_session"


def session_user_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.query_params.get("token", "")
    return verify_session(token)


def require_session(request: Request) -> str:
    user = session_user_from_request(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tizimga kirilmagan (Avtorizatsiya talab etiladi)",
        )
    return user
