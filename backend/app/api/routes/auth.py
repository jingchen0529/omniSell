from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import build_expiration, generate_access_token, hash_password, verify_password
from app.db.models import AuthToken, PasswordResetToken, User
from app.db.session import get_db
from app.schemas.auth import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    existing_user = db.scalar(select(User).where(User.email == payload.email).limit(1))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    token_response = issue_token_for_user(db, user)
    db.commit()
    return token_response


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email).limit(1))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    token_response = issue_token_for_user(db, user)
    db.commit()
    return token_response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return serialize_user(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.execute(delete(AuthToken).where(AuthToken.user_id == current_user.id))
    db.commit()


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    user = db.scalar(select(User).where(User.email == payload.email).limit(1))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found.")

    settings = get_settings()
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))

    reset_token = generate_access_token()
    token_record = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=build_expiration(settings.password_reset_token_expire_hours),
    )
    db.add(token_record)
    db.commit()

    return ForgotPasswordResponse(
        message="Password reset token created.",
        reset_token=reset_token,
        reset_url=f"/reset-password?token={reset_token}",
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> None:
    token_record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token == payload.token).limit(1)
    )
    if token_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reset token not found.")

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if token_record.used_at is not None or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired.")

    user = db.get(User, token_record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.password_hash = hash_password(payload.new_password)
    token_record.used_at = datetime.now(timezone.utc)
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
    db.commit()


def issue_token_for_user(db: Session, user: User) -> AuthTokenResponse:
    settings = get_settings()
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id))

    token = generate_access_token()
    token_record = AuthToken(
        user_id=user.id,
        token=token,
        expires_at=build_expiration(settings.auth_token_expire_hours),
    )
    db.add(token_record)
    db.flush()
    return AuthTokenResponse(access_token=token, user=serialize_user(user))


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
    )
