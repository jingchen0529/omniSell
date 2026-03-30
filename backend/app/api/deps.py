from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthToken, User
from app.db.session import get_db


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    token_record = db.scalar(
        select(AuthToken).where(AuthToken.token == credentials.credentials).limit(1)
    )
    if token_record is None:
        raise unauthorized

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        raise unauthorized

    user = db.get(User, token_record.user_id)
    if user is None:
        raise unauthorized

    return user
