from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str
    provider: str  # "google" | "linkedin"


class OAuthUserInfo(BaseModel):
    provider: str
    provider_user_id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None