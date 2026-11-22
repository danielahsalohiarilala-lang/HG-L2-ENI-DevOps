from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import RawText
from tests.helpers import login

CONTENT = "Ity ny lahatsoratra napetraka tanana, lava ampy mba hampiasaina amin'ny fitahirizana ao amin'ny tahiry."


async def test_deposit_creates_pending_text(client, ids):
    h = await login(client, "r1@t.mg")
    r = await client.post("/api/v1/archives", headers=h, json={
        "id_source": ids["src1"], "title": "Tantara napetraka", "content": CONTENT, "creator": "Rakoto", "region": "Imerina"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    async with SessionLocal() as s:
        raw = await s.get(RawText, r.json()["id_raw"])
        assert raw.status == "pending" and raw.creator == "Rakoto" and raw.media_type == "text" and raw.language == "mg"


async def test_deposit_validation_and_isolation(client, ids):
    h = await login(client, "r1@t.mg")
    base = {"title": "Titre de test", "content": CONTENT}
    assert (await client.post("/api/v1/archives", headers=h, json={**base, "id_source": ids["src2"]})).status_code == 404   # source org 2
    assert (await client.post("/api/v1/archives", headers=h, json={**base, "id_source": ids["src1"], "content": "court"})).status_code == 422
    assert (await client.post("/api/v1/archives", headers=await login(client, "l1@t.mg"),
                              json={**base, "id_source": ids["src1"]})).status_code == 403


async def test_scraping_jobs_queue_and_isolation(client, ids):
    admin, other = await login(client, "a1@t.mg"), await login(client, "a2@t.mg")
    r = await client.post("/api/v1/scraping/jobs", headers=admin,
                          json={"id_source": ids["src1"], "params": {"wiki_query": "tantara", "limit": 3}})
    assert r.status_code == 202 and r.json()["status"] == "queued" and r.json()["params"]["limit"] == 3
    job = r.json()["id_job"]
    assert (await client.get(f"/api/v1/scraping/jobs/{job}", headers=admin)).json()["texts_count"] == 0
    assert (await client.get(f"/api/v1/scraping/jobs/{job}", headers=other)).status_code == 404
    assert (await client.post("/api/v1/scraping/jobs", headers=other, json={"id_source": ids["src1"]})).status_code == 404
    assert (await client.get("/api/v1/scraping/jobs", headers=admin)).json()["total"] == 1
    assert (await client.get("/api/v1/scraping/jobs", headers=other)).json()["total"] == 0
    assert (await client.post("/api/v1/scraping/jobs", headers=await login(client, "r1@t.mg"),
                              json={"id_source": ids["src1"]})).status_code == 403


async def test_admin_stats_are_scoped(client):
    s1 = (await client.get("/api/v1/admin/stats", headers=await login(client, "a1@t.mg"))).json()
    s2 = (await client.get("/api/v1/admin/stats", headers=await login(client, "a2@t.mg"))).json()
    assert s1["users_by_role"] == {"admin": 1, "reader": 1, "reviewer": 1} and s1["sources"] == 1
    assert s1["cleaned_texts_by_status"] == {"ready_for_review": 2, "validated": 3}
    assert s1["corpus_by_genre"] == {"hira_gasy": 1, "tantara": 2}
    assert s2["users_by_role"] == {"admin": 1, "reviewer": 1} and s2["cleaned_texts_by_status"] == {"ready_for_review": 1, "validated": 2}


async def test_audit_journal_records_actions_and_is_scoped(client, ids):
    r1, a1, a2 = await login(client, "r1@t.mg"), await login(client, "a1@t.mg"), await login(client, "a2@t.mg")
    await client.post(f"/api/v1/review/{ids['c1']}/decision", headers=r1, json={"action": "validate", "genre": "tantara"})
    await client.post("/api/v1/sources", headers=a1, json={"name": "Source test", "url": "https://s.mg", "type": "web", "license": "CC0"})
    log = (await client.get("/api/v1/admin/audit", headers=a1)).json()
    assert [(i["action"], i["user"]) for i in log["items"]] == [("source.create", "a1@t.mg"), ("review.validate", "r1@t.mg")]
    assert (await client.get("/api/v1/admin/audit?action=review.validate", headers=a1)).json()["total"] == 1
    assert (await client.get("/api/v1/admin/audit", headers=a2)).json()["total"] == 0                      # l'org 2 ne voit rien
    assert (await client.get("/api/v1/admin/audit", headers=r1)).status_code == 403


async def test_text_helpers_match_pipeline_rules():
    from app.services import text_utils as t
    assert t.words("tantaran'i zava-nitranga 1895") == ["tantaran", "i", "zava-nitranga", "1895"]
    assert t.content_hash("Ny  Tantara, dia tsara!") == t.content_hash("ny tantara dia   tsara")
