"""Datasets, entraînements, modèles, générations et journal d'audit."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (JSON, DateTime, Enum, ForeignKey, Index, Numeric, String, Text,
                        UniqueConstraint, Boolean, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, LongText, UBigInt, UInt
from app.models.archive import GENRES, JOB_STATUS


class DatasetVersion(Base):
    __tablename__ = "dataset_version"
    __table_args__ = (UniqueConstraint("id_org", "name", name="uq_dataset_org_name"),)

    id_dataset: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    num_samples: Mapped[int] = mapped_column(UInt, default=0, server_default="0")
    path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    id_org: Mapped[int] = mapped_column(UInt, ForeignKey("organisation.id_org"))

    items: Mapped[list["DatasetItem"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetItem(Base):
    __tablename__ = "dataset_item"

    id_dataset: Mapped[int] = mapped_column(UInt, ForeignKey("dataset_version.id_dataset", ondelete="CASCADE"), primary_key=True)
    id_corpus: Mapped[int] = mapped_column(UInt, ForeignKey("corpus.id_corpus", ondelete="CASCADE"), primary_key=True, index=True)

    dataset: Mapped[DatasetVersion] = relationship(back_populates="items")


class TrainingRun(Base):
    __tablename__ = "training_run"

    id_run: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    base_model: Mapped[str] = mapped_column(String(150))
    hyperparams: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Enum(*JOB_STATUS, name="run_status"), default="queued", server_default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    id_dataset: Mapped[int] = mapped_column(UInt, ForeignKey("dataset_version.id_dataset"), index=True)


class ModelArtifact(Base):
    __tablename__ = "model_artifact"

    id_model: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(500))
    eval_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    is_production: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    id_run: Mapped[int] = mapped_column(UInt, ForeignKey("training_run.id_run"), index=True)


class Generation(Base):
    __tablename__ = "generation"

    id_gen: Mapped[int] = mapped_column(UInt, primary_key=True, autoincrement=True)
    prompt: Mapped[str] = mapped_column(Text)
    genre: Mapped[str] = mapped_column(Enum(*GENRES, name="gen_genre"))
    max_tokens: Mapped[int] = mapped_column(UInt)
    output: Mapped[str] = mapped_column(LongText)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    id_user: Mapped[int] = mapped_column(UInt, ForeignKey("utilisateur.id_user"), index=True)
    id_model: Mapped[int] = mapped_column(UInt, ForeignKey("model_artifact.id_model"), index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity", "entity_id"),)

    id_log: Mapped[int] = mapped_column(UBigInt, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(UInt)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    id_user: Mapped[int | None] = mapped_column(UInt, ForeignKey("utilisateur.id_user"), nullable=True, index=True)
