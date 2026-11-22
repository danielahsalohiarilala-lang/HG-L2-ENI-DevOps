from tests.helpers import PASSWORD, login


async def test_admin_creates_user_who_can_login(client):
    h = await login(client, "a1@t.mg")
    r = await client.post("/api/v1/users", headers=h, json={"email": "Nouveau@T.mg", "password": "Motdepasse1", "role": "reviewer", "locale": "mg"})
    assert r.status_code == 201 and r.json()["email"] == "nouveau@t.mg" and r.json()["role"] == "reviewer"
    assert (await client.get("/api/v1/auth/me", headers=await login(client, "nouveau@t.mg", "Motdepasse1"))).json()["organisation"] == "Organisation 1"


async def test_duplicate_email_weak_password_and_bad_role(client):
    h = await login(client, "a1@t.mg")
    dup = await client.post("/api/v1/users", headers=h, json={"email": "r2@t.mg", "password": "Motdepasse1"})   # existe chez l'org 2
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "EMAIL_EXISTS"
    assert (await client.post("/api/v1/users", headers=h, json={"email": "x@t.mg", "password": "court"})).status_code == 422
    assert (await client.post("/api/v1/users", headers=h, json={"email": "x@t.mg", "password": "Motdepasse1", "role": "root"})).status_code == 422


async def test_user_list_and_update_are_scoped_to_organisation(client, ids):
    h = await login(client, "a1@t.mg")
    emails = {u["email"] for u in (await client.get("/api/v1/users", headers=h)).json()["items"]}
    assert emails == {"a1@t.mg", "r1@t.mg", "l1@t.mg"}
    r = await client.patch(f"/api/v1/users/{ids['u_r2']}", headers=h, json={"role": "admin"})   # utilisateur de l'org 2
    assert r.status_code == 404
    r = await client.patch(f"/api/v1/users/{ids['u_l1']}", headers=h, json={"role": "reviewer", "locale": "mg"})
    assert r.status_code == 200 and r.json()["role"] == "reviewer" and r.json()["locale"] == "mg"


async def test_admin_cannot_lock_themselves_out(client, ids):
    h = await login(client, "a1@t.mg")
    me = ids["u_a1"]
    assert (await client.patch(f"/api/v1/users/{me}", headers=h, json={"is_active": False})).json()["detail"]["code"] == "SELF_LOCKOUT"
    assert (await client.patch(f"/api/v1/users/{me}", headers=h, json={"role": "reader"})).status_code == 400


async def test_password_change_and_deactivation(client, ids):
    h = await login(client, "a1@t.mg")
    await client.patch(f"/api/v1/users/{ids['u_l1']}", headers=h, json={"password": "NouveauMdp12"})
    assert (await client.post("/api/v1/auth/login", data={"username": "l1@t.mg", "password": PASSWORD})).status_code == 401
    await login(client, "l1@t.mg", "NouveauMdp12")
    await client.patch(f"/api/v1/users/{ids['u_l1']}", headers=h, json={"is_active": False})
    assert (await client.post("/api/v1/auth/login", data={"username": "l1@t.mg", "password": "NouveauMdp12"})).status_code == 401


async def test_sources_license_required_unique_and_scoped(client, ids):
    admin, reviewer = await login(client, "a1@t.mg"), await login(client, "r1@t.mg")
    body = {"name": "Nouvelle source", "url": "https://exemple.mg", "type": "web", "license": "CC BY-SA 4.0"}
    assert (await client.post("/api/v1/sources", headers=admin, json={**body, "license": ""})).status_code == 422
    assert (await client.post("/api/v1/sources", headers=admin, json={k: v for k, v in body.items() if k != "license"})).status_code == 422
    assert (await client.post("/api/v1/sources", headers=reviewer, json=body)).status_code == 403
    assert (await client.post("/api/v1/sources", headers=admin, json=body)).status_code == 201
    assert (await client.post("/api/v1/sources", headers=admin, json=body)).json()["detail"]["code"] == "SOURCE_EXISTS"
    names = {s["name"] for s in (await client.get("/api/v1/sources", headers=reviewer)).json()}
    assert names == {"Source 1", "Nouvelle source"}                                   # pas la source de l'org 2
    assert (await client.patch(f"/api/v1/sources/{ids['src2']}", headers=admin, json={"license": "MIT"})).status_code == 404
    r = await client.patch(f"/api/v1/sources/{ids['src1']}", headers=admin, json={"license": "CC0"})
    assert r.status_code == 200 and r.json()["license"] == "CC0"
