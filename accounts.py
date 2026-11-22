"""Organisations, rôles et utilisateurs."""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UInt


class Organisation(Base):
    __tablename__ = "organisation"

    id_org: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="org")
    sources: Mapped[list["Source"]] = relationship(back_populates="org")  # noqa: F821


class Role(Base):
    __tablename__ = "role"

    id_role: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    libelle: Mapped[str] = mapped_column(String(50))


class User(Base):
    __tablename__ = "utilisateur"
    __table_args__ = (CheckConstraint("locale IN ('fr','mg')", name="ck_utilisateur_locale"),)

    id_user: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(2), default="fr", server_default="fr")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    id_role: Mapped[int] = mapped_column(UInt, ForeignKey("role.id_role"))
    id_org: Mapped[int] = mapped_column(UInt, ForeignKey("organisation.id_org"), index=True)

    role: Mapped[Role] = relationship()
    org: Mapped[Organisation] = relationship(back_populates="users")
