import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.mark.asyncio
async def test_health_and_overview():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/health")
        assert r.status_code == 200 and r.json() == {"status": "ok", "database": "up"}
        r = await client.get("/api/v1/dev/overview")
        assert r.status_code == 200 and r.json()["corpus"] == 0
        r = await client.get("/")
        assert r.json()["docs"] == "/docs"
