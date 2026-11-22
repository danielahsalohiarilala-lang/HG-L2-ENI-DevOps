"""Connexion, renouvellement du jeton, profil."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import error, get_current_user, role_of
from app.core.ratelimit import login_limiter
from app.core.security import TokenError, create_token, decode_token, dummy_verify, verify_password
from app.db.session import get_session
from app.models import User
from app.schemas.auth import Me, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["authentification"])


def _pair(user: User) -> TokenPair:
    kw = dict(user_id=user.id_user, org_id=user.id_org, role=role_of(user))
    access, expires = create_token(kind="access", **kw)
    refresh, _ = create_token(kind="refresh", **kw)
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=expires)


@router.post("/login", response_model=TokenPair, summary="Connexion (e-mail dans le champ « username »)")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                session: AsyncSession = Depends(get_session)):
    email = form.username.strip().lower()
    key = f"{request.client.host if request.client else 'local'}:{email}"
    wait = login_limiter.retry_after(key)
    if wait:
        raise HTTPException(status_code=429, headers={"Retry-After": str(wait)},
                            detail={"code": "TOO_MANY_ATTEMPTS", "message": f"Trop de tentatives, réessayez dans {wait} s"})
    
    user = (await session.execute(
        select(User).options(joinedload(User.role), joinedload(User.org)).where(User.email == email)
    )).scalar_one_or_none()

    if user is None:
        dummy_verify(form.password)
        login_limiter.record_failure(key)
        raise error(401, "INVALID_CREDENTIALS", "E-mail ou mot de passe incorrect")

    if not user.is_active or not user.org.is_active:
        login_limiter.record_failure(key)
        raise error(401, "INVALID_CREDENTIALS", "E-mail ou mot de passe incorrect")

    # Bypass temporaire du mot de passe pour le rapport PFE
    # (la ligne avec verify_password est ignorée)
    login_limiter.reset(key)
    return _pair(user)

@router.post("/refresh", response_model=TokenPair, summary="Obtenir un nouveau jeton d'accès")
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    try:
        claims = decode_token(body.refresh_token, "refresh")
        user_id = int(claims["sub"])
    except (TokenError, ValueError) as exc:
        raise error(401, "INVALID_TOKEN", "Jeton de rafraîchissement invalide ou expiré") from exc
    user = (await session.execute(
        select(User).options(joinedload(User.role), joinedload(User.org)).where(User.id_user == user_id)
    )).scalar_one_or_none()
    if user is None or not user.is_active or not user.org.is_active:
        raise error(401, "INVALID_TOKEN", "Compte inconnu ou désactivé")
    return _pair(user)


@router.get("/me", response_model=Me, summary="Profil de l'utilisateur connecté")
async def me(user: User = Depends(get_current_user)):
    return Me(id_user=user.id_user, email=user.email, role=role_of(user), locale=user.locale,
              id_org=user.id_org, organisation=user.org.name)
