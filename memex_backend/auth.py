import secrets

from fastapi import Header, HTTPException, Request, status


async def require_bearer_token(request: Request, authorization: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.api_token
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
