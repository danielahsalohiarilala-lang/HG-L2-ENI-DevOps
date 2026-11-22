"""Gestion des utilisateurs de l'organisation (administrateur)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import PageParams, error, require_role
from app.core.security import hash_password
from app.db.session import get_session
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["utilisateurs"])


def _out(u: User) -> UserOut:
    return UserOut(id_user=u.id_user, email=u.email, role=u.role.code, locale=u.locale,
                   is_active=u.is_active, created_at=u.created_at)


async def _role_id(session: AsyncSession, code: str) -> int:
    rid = (await session.execute(select(Role.id_role).where(Role.code == code))).scalar_one_or_none()
    if rid is None:
        raise error(500, "ROLE_MISSING", f"Rôle {code} absent de la base")
    return rid


@router.get("", response_model=Page[UserOut], summary="Lister les utilisateurs de l'organisation")
async def list_users(p: PageParams = Depends(), admin: User = Depends(require_role("admin")),
                     session: AsyncSession = Depends(get_session)):
    total = (await session.execute(select(func.count()).select_from(User).where(User.id_org == admin.id_org))).scalar_one()
    rows = (await session.execute(
        select(User).options(joinedload(User.role)).where(User.id_org == admin.id_org)
        .order_by(User.id_user).offset(p.offset).limit(p.size))).scalars().all()
    return Page(items=[_out(u) for u in rows], total=total, page=p.page, size=p.size)


@router.post("", response_model=UserOut, status_code=201, summary="Créer un utilisateur")
async def create_user(body: UserCreate, admin: User = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_session)):
    email = body.email.lower()
    exists = (await session.execute(select(User.id_user).where(User.email == email))).scalar_one_or_none()
    if exists:
        raise error(409, "EMAIL_EXISTS", "Cet e-mail est déjà utilisé")
    user = User(email=email, password_hash=hash_password(body.password), locale=body.locale,
                id_role=await _role_id(session, body.role), id_org=admin.id_org)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise error(409, "EMAIL_EXISTS", "Cet e-mail est déjà utilisé") from exc
    audit(session, admin.id_user, "user.create", "utilisateur", user.id_user, {"email": email, "role": body.role})
    await session.commit()
    user = (await session.execute(select(User).options(joinedload(User.role)).where(User.id_user == user.id_user))).scalar_one()
    return _out(user)


@router.patch("/{id_user}", response_model=UserOut, summary="Modifier rôle, langue, activation ou mot de passe")
async def update_user(id_user: int, body: UserUpdate, admin: User = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_session)):
    user = (await session.execute(select(User).options(joinedload(User.role))
                                  .where(User.id_user == id_user, User.id_org == admin.id_org))).scalar_one_or_none()
    if user is None:
        raise error(404, "NOT_FOUND", "Utilisateur introuvable")
    changes: dict = {}
    if user.id_user == admin.id_user and (body.is_active is False or (body.role and body.role != "admin")):
        raise error(400, "SELF_LOCKOUT", "Vous ne pouvez pas vous désactiver ni retirer votre propre rôle d'administrateur")
    if body.role is not None and body.role != user.role.code:
        changes["role"] = {"from": user.role.code, "to": body.role}
        user.id_role = await _role_id(session, body.role)
    if body.locale is not None and body.locale != user.locale:
        changes["locale"] = body.locale
        user.locale = body.locale
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = body.is_active
        user.is_active = body.is_active
    if body.password is not None:
        changes["password"] = "modifié"
        user.password_hash = hash_password(body.password)
    if changes:
        audit(session, admin.id_user, "user.update", "utilisateur", user.id_user, changes)
    await session.commit()
    # populate_existing : recharge aussi la relation « role » déjà en mémoire (sinon l'ancien rôle serait renvoyé)
    user = (await session.execute(select(User).options(joinedload(User.role)).where(User.id_user == id_user)
                                  .execution_options(populate_existing=True))).scalar_one()
    return _out(user)
