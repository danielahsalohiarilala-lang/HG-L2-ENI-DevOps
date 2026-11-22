from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ArchiveCreate(BaseModel):
    id_source: int
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=50, description="Texte à archiver (50 caractères minimum)")
    language: Literal["mg", "fr"] = "mg"
    creator: str | None = Field(default=None, max_length=200, description="Auteur, conteur ou troupe")
    region: str | None = Field(default=None, max_length=100)
    date_origin: str | None = Field(default=None, max_length=50)


class ArchiveOut(BaseModel):
    id_raw: int
    status: str
    message: str


class JobCreate(BaseModel):
    id_source: int
    params: dict[str, Any] | None = Field(
        default=None, description='Ex. {"wiki_query": "tantara", "lang": "mg", "limit": 10} ou {"urls": ["https://..."]}')


class JobOut(BaseModel):
    id_job: int
    id_source: int
    status: str
    params: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    texts_count: int = 0
