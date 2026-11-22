"""Dépendances FastAPI : utilisateur courant, contrôle des rôles, pagination."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import TokenError, decode_token
from app.db.session import get_session
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
ROLE_RANK = {"reader": 1, "reviewer": 2, "admin": 3}


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def get_current_user(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)) -> User:
    """Valide le jeton d'accès, puis recharge l'utilisateur : rôle et état viennent de la base, pas du jeton."""
    try:
        claims = decode_token(token, "access")
        user_id = int(claims["sub"])
    except (TokenError, ValueError) as exc:
        raise error(401, "INVALID_TOKEN", "Jeton invalide ou expiré") from exc
    user = (await session.execute(
        select(User).options(joinedload(User.role), joinedload(User.org)).where(User.id_user == user_id)
    )).scalar_one_or_none()
    if user is None or not user.is_active or not user.org.is_active:
        raise error(401, "INVALID_TOKEN", "Compte inconnu ou désactivé")
    return user


def role_of(user: User) -> str:
    return user.role.code


def require_role(minimum: str):
    """Autorise le rôle indiqué et les rôles supérieurs (reader < reviewer < admin)."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK[role_of(user)] < ROLE_RANK[minimum]:
            raise error(403, "FORBIDDEN_ROLE", f"Rôle {minimum} requis")
        return user
    return checker


@dataclass
class PageParams:
    page: int = Query(1, ge=1, description="Numéro de page")
    size: int = Query(20, ge=1, le=100, description="Éléments par page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
