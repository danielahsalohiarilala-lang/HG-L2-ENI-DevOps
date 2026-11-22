import os

# Les tests utilisent SQLite : aucune base MySQL n'est nécessaire.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["APP_ENV"] = "development"
os.environ["BCRYPT_ROUNDS"] = "4"          # hachage rapide pour les tests uniquement
os.environ["JWT_SECRET"] = "secret-de-test-seulement-assez-long-0123456789"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.ratelimit import login_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import seed  # noqa: E402


@pytest_asyncio.fixture
async def ids():
    """Base vide recréée pour chaque test, puis remplie avec deux organisations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    login_limiter.clear()
    return await seed()


@pytest_asyncio.fixture
async def client(ids):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
