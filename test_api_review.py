from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditLog, CleanedText, Corpus, Review
from app.services.text_utils import content_hash
from tests.helpers import login

NEW = "Ity ny andalana vaovao nasaina hanitsiana ny lahatsoratra, ary lava ampy hotazonina eto amin'ny tahiry."


async def test_queue_is_scoped_filtered_and_ordered(client, ids):
    h = await login(client, "r1@t.mg")
    q = (await client.get("/api/v1/review/queue", headers=h)).json()
    assert q["total"] == 2 and {i["id_cleaned"] for i in q["items"]} == {ids["c1"], ids["c2"]}   # pas c3 (org 2)
    low = (await client.get("/api/v1/review/queue?order=score_asc", headers=h)).json()["items"]
    assert [i["id_cleaned"] for i in low] == [ids["c2"], ids["c1"]]
    assert (await client.get("/api/v1/review/queue?min_score=0.8", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/review/queue?q=faharoa", headers=h)).json()["total"] == 1
    assert (await client.get("/api/v1/review/queue?size=1&page=2", headers=h)).json()["items"].__len__() == 1


async def test_detail_and_cross_organisation_access_is_404(client, ids):
    h = await login(client, "r1@t.mg")
    d = (await client.get(f"/api/v1/review/{ids['c1']}", headers=h)).json()
    assert d["title"] == "Tantara voalohany" and d["source"]["license"] == "CC BY-SA 4.0" and d["reviews"] == []
    assert (await client.get(f"/api/v1/review/{ids['c3']}", headers=h)).status_code == 404     # texte de l'org 2
    assert (await client.patch(f"/api/v1/review/{ids['c3']}/content", headers=h, json={"content": NEW})).status_code == 404
    assert (await client.post(f"/api/v1/review/{ids['c3']}/decision", headers=h,
                              json={"action": "validate", "genre": "tantara"})).status_code == 404


async def test_edit_content_updates_count_hash_and_audit(client, ids):
    h = await login(client, "r1@t.mg")
    d = (await client.patch(f"/api/v1/review/{ids['c1']}/content", headers=h, json={"content": NEW})).json()
    assert d["content"] == NEW and d["word_count"] == 16
    async with SessionLocal() as s:
        c = await s.get(CleanedText, ids["c1"])
        assert c.dedupe_hash == content_hash(NEW)
        assert (await s.execute(select(AuditLog.action))).scalars().all() == ["review.edit"]


async def test_edit_to_existing_content_is_refused(client, ids):
    h = await login(client, "r1@t.mg")
    other = (await client.get(f"/api/v1/review/{ids['c2']}", headers=h)).json()["content"]
    r = await client.patch(f"/api/v1/review/{ids['c1']}/content", headers=h, json={"content": other})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "DUPLICATE_CONTENT"


async def test_validate_creates_corpus_entry_and_audit(client, ids):
    h = await login(client, "r1@t.mg")
    r = await client.post(f"/api/v1/review/{ids['c1']}/decision", headers=h,
                          json={"action": "validate", "genre": "hira_gasy", "access_level": "public"})
    assert r.status_code == 201 and r.json()["status"] == "validated" and r.json()["id_corpus"]
    async with SessionLocal() as s:
        co = (await s.execute(select(Corpus).where(Corpus.id_cleaned == ids["c1"]))).scalar_one()
        assert co.genre == "hira_gasy" and co.access_level == "public"
        assert (await s.get(CleanedText, ids["c1"])).status == "validated"
        assert (await s.execute(select(Review.action))).scalars().all() == ["validate"]
        assert (await s.execute(select(AuditLog.action))).scalars().all() == ["review.validate"]
    assert (await client.get("/api/v1/review/queue", headers=h)).json()["total"] == 1            # sorti de la file
    detail = (await client.get(f"/api/v1/review/{ids['c1']}", headers=h)).json()
    assert detail["status"] == "validated" and detail["reviews"][0]["reviewer"] == "r1@t.mg"


async def test_double_validation_and_late_reject_are_refused(client, ids):
    h = await login(client, "r1@t.mg")
    ok = {"action": "validate", "genre": "tantara"}
    assert (await client.post(f"/api/v1/review/{ids['c1']}/decision", headers=h, json=ok)).status_code == 201
    r = await client.post(f"/api/v1/review/{ids['c1']}/decision", headers=h, json=ok)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_PENDING"
    r = await client.post(f"/api/v1/review/{ids['c1']}/decision", headers=h, json={"action": "reject", "comment": "trop tard"})
    assert r.status_code == 409
    assert (await client.patch(f"/api/v1/review/{ids['c1']}/content", headers=h, json={"content": NEW})).status_code == 409


async def test_decision_rules_rg15_and_required_genre(client, ids):
    h = await login(client, "r1@t.mg")
    url = f"/api/v1/review/{ids['c2']}/decision"
    assert (await client.post(url, headers=h, json={"action": "reject"})).status_code == 422                       # RG15
    assert (await client.post(url, headers=h, json={"action": "reject", "comment": "   "})).status_code == 422
    assert (await client.post(url, headers=h, json={"action": "validate"})).status_code == 422                    # genre requis
    assert (await client.post(url, headers=h, json={"action": "validate", "genre": "poeme"})).status_code == 422
    assert (await client.post(url, headers=h, json={"action": "comment"})).status_code == 422


async def test_reject_and_comment_flow(client, ids):
    h = await login(client, "r1@t.mg")
    r = await client.post(f"/api/v1/review/{ids['c2']}/decision", headers=h, json={"action": "comment", "comment": "À vérifier"})
    assert r.status_code == 201 and r.json()["status"] == "ready_for_review"                    # un commentaire ne change rien
    r = await client.post(f"/api/v1/review/{ids['c2']}/decision", headers=h,
                          json={"action": "reject", "comment": "Orthographe non corrigeable"})
    assert r.status_code == 201 and r.json()["status"] == "rejected" and r.json()["id_corpus"] is None
    d = (await client.get(f"/api/v1/review/{ids['c2']}", headers=h)).json()
    assert [rv["action"] for rv in d["reviews"]] == ["comment", "reject"]
    assert (await client.get("/api/v1/review/queue", headers=h)).json()["total"] == 1
    async with SessionLocal() as s:
        assert (await s.execute(select(Corpus).where(Corpus.id_cleaned == ids["c2"]))).first() is None   # rien au corpus
