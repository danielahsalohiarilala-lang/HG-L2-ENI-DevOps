"""Mots de passe (bcrypt) et jetons JWT (accès et rafraîchissement)."""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    # bcrypt ne lit que les 72 premiers octets : on les tronque explicitement
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except ValueError:
        return False


_dummy_hash: str | None = None


def dummy_verify(password: str) -> None:
    """Fait un calcul de hachage factice : la durée de réponse ne révèle pas si l'e-mail existe."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password")
    verify_password(password, _dummy_hash)


class TokenError(Exception):
    """Jeton invalide, expiré ou d'un mauvais type."""


def create_token(*, user_id: int, org_id: int, role: str, kind: str) -> tuple[str, int]:
    """Crée un jeton 'access' ou 'refresh'. Retourne (jeton, durée de validité en secondes)."""
    s = get_settings()
    delta = timedelta(minutes=s.access_token_minutes) if kind == "access" else timedelta(days=s.refresh_token_days)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "org": org_id, "role": role, "type": kind,
               "iat": now, "exp": now + delta, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), int(delta.total_seconds())


def decode_token(token: str, kind: str) -> dict:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub", "type"]})
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if data.get("type") != kind:
        raise TokenError("mauvais type de jeton")
    return data
