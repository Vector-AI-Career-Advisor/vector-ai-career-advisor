from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from core.security import get_current_user
from features.auth.schemas import UserCreate, UserLogin, TokenResponse, OAuthCallbackRequest
from features.auth import service

router = APIRouter()


@router.post("/signup", status_code=201)
def signup(user: UserCreate):
    return service.signup(user)


@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin):
    return service.login(user)


@router.get("/me")
def get_me(user_id: str = Depends(get_current_user)):
    return service.get_me(user_id)


@router.post("/oauth/callback", response_model=TokenResponse)
def oauth_callback(body: OAuthCallbackRequest):
    """
    Exchange an OAuth authorization code for a Vector JWT.
    Frontend POSTs { code, redirect_uri, provider } here after the
    provider redirects back to the SPA.
    """
    return service.oauth_login(body)


# ── Legal pages ────────────────────────────────────────────────────────────────

@router.get("/terms-of-service", response_class=HTMLResponse, include_in_schema=False)
def terms_of_service():
    return service.render_terms()


@router.get("/privacy-policy", response_class=HTMLResponse, include_in_schema=False)
def privacy_policy():
    return service.render_privacy()
