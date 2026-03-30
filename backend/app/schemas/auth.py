from datetime import datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: datetime


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=2, max_length=80)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str
    reset_url: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=128)
