from sqlalchemy import update

from app.core.security import create_token
from app.db.session import SessionLocal
from app.models import User
from tests.helpers import PASSWORD, login


async def test_login_me_and_roles(client):
    h = await login(client, "r1@t.mg")
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    assert me["email"] == "r1@t.mg" and me["role"] == "reviewer" and me["organisation"] == "Organisation 1"


async def test_login_is_case_insensitive_and_returns_tokens(client):
    r = await client.post("/api/v1/auth/login", data={"username": " A1@T.MG ", "password": PASSWORD})
    body = r.json()
    assert r.status_code == 200 and body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert body["access_token"] != body["refresh_token"]


async def test_bad_credentials_same_error_for_unknown_email_and_wrong_password(client):
    a = await client.post("/api/v1/auth/login", data={"username": "a1@t.mg", "password": "mauvais"})
    b = await client.post("/api/v1/auth/login", data={"username": "inconnu@t.mg", "password": "mauvais"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"]["code"] == b.json()["detail"]["code"] == "INVALID_CREDENTIALS"


async def test_no_token_or_garbage_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer pas.un.jeton"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "INVALID_TOKEN"


async def test_refresh_flow_and_token_types_are_not_interchangeable(client):
    pair = (await client.post("/api/v1/auth/login", data={"username": "a1@t.mg", "password": PASSWORD})).json()
    # le jeton de rafraîchissement ne donne pas accès aux routes
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {pair['refresh_token']}"})
    assert r.status_code == 401
    # le jeton d'accès ne peut pas servir à se rafraîchir
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": pair["access_token"]})).status_code == 401
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 200
    ok = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert ok.status_code == 200


async def test_expired_token_rejected(client, ids, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "access_token_minutes", -1)
    token, _ = create_token(user_id=ids["u_a1"], org_id=ids["org1"], role="admin", kind="access")
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_deactivated_user_loses_access_immediately(client, ids):
    h = await login(client, "r1@t.mg")
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.id_user == ids["u_r1"]).values(is_active=False))
        await s.commit()
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 401
    r = await client.post("/api/v1/auth/login", data={"username": "r1@t.mg", "password": PASSWORD})
    assert r.status_code == 401


async def test_login_rate_limit(client):
    for _ in range(5):
        r = await client.post("/api/v1/auth/login", data={"username": "a1@t.mg", "password": "x"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", data={"username": "a1@t.mg", "password": PASSWORD})
    assert r.status_code == 429 and "retry-after" in r.headers


async def test_role_hierarchy(client):
    reader, reviewer, admin = [await login(client, e) for e in ("l1@t.mg", "r1@t.mg", "a1@t.mg")]
    assert (await client.get("/api/v1/review/queue", headers=reader)).status_code == 403
    assert (await client.get("/api/v1/corpus", headers=reader)).status_code == 200
    assert (await client.get("/api/v1/review/queue", headers=reviewer)).status_code == 200
    assert (await client.get("/api/v1/corpus", headers=reviewer)).status_code == 200      # hérite du lecteur
    assert (await client.get("/api/v1/users", headers=reviewer)).status_code == 403
    assert (await client.get("/api/v1/users", headers=admin)).status_code == 200
    assert (await client.get("/api/v1/review/queue", headers=admin)).status_code == 200   # hérite du relecteur
    r = await client.get("/api/v1/users", headers=reviewer)
    assert r.json()["detail"]["code"] == "FORBIDDEN_ROLE"
