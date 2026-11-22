"""Données de test : deux organisations, des utilisateurs de chaque rôle, des textes et des archives."""
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.services.text_utils import content_hash
from app.models import (CleanedText, Corpus, CorpusRevision, Organisation, RawText, Role, Source, User)

PASSWORD = "Passw0rd!2026"
LONG = "Ny tantaran'i Madagasikara dia mirakitra ny zava-nitranga hatramin'ny andron'ny Andriana ka hatramin'izao. " * 3


async def seed() -> dict:
    out: dict = {}
    pw = hash_password(PASSWORD)
    async with SessionLocal() as s:
        roles = {c: Role(code=c, libelle=c) for c in ("reader", "reviewer", "admin")}
        s.add_all(roles.values())
        orgs = {1: Organisation(name="Organisation 1", slug="org1"), 2: Organisation(name="Organisation 2", slug="org2")}
        s.add_all(orgs.values())
        await s.flush()

        def user(email, role, org):
            u = User(email=email, password_hash=pw, id_role=roles[role].id_role, id_org=orgs[org].id_org)
            s.add(u)
            return u

        users = {"a1": user("a1@t.mg", "admin", 1), "r1": user("r1@t.mg", "reviewer", 1), "l1": user("l1@t.mg", "reader", 1),
                 "a2": user("a2@t.mg", "admin", 2), "r2": user("r2@t.mg", "reviewer", 2)}
        src = {1: Source(name="Source 1", url="manual://1", type="manual", license="CC BY-SA 4.0", id_org=orgs[1].id_org),
               2: Source(name="Source 2", url="manual://2", type="manual", license="CC BY 4.0", id_org=orgs[2].id_org)}
        s.add_all(src.values())
        await s.flush()

        def text(n, org, status, score, title, content=None, region=None):
            raw = RawText(title=title, content=content or f"{LONG} #{n}", language="mg", region=region,
                          status="cleaned", id_source=src[org].id_source, origin_url=f"https://x/{n}")
            s.add(raw)
            return raw, score, status, content or f"{LONG} #{n}"

        specs = {"c1": text(1, 1, "ready_for_review", 0.9, "Tantara voalohany", region="Imerina"),
                 "c2": text(2, 1, "ready_for_review", 0.4, "Tantara faharoa"),
                 "c3": text(3, 2, "ready_for_review", 0.8, "Tantara org2"),
                 "k_pub": text(4, 1, "validated", 0.9, "Archive publique", region="Imerina"),
                 "k_res": text(5, 1, "validated", 0.8, "Archive restreinte"),
                 "k_priv": text(6, 1, "validated", 0.7, "Archive privée"),
                 "k2_pub": text(7, 2, "validated", 0.9, "Archive publique org2"),
                 "k2_res": text(8, 2, "validated", 0.9, "Archive restreinte org2")}
        await s.flush()
        cleaned = {}
        for key, (raw, score, status, content) in specs.items():
            c = CleanedText(content=content, word_count=len(content.split()), quality_score=score,
                            dedupe_hash=content_hash(content), status=status, id_raw=raw.id_raw)
            s.add(c)
            cleaned[key] = c
        await s.flush()
        levels = {"k_pub": ("public", "tantara"), "k_res": ("restricted", "hira_gasy"), "k_priv": ("private", "tantara"),
                  "k2_pub": ("public", "tantara"), "k2_res": ("restricted", "tantara")}
        for key, (level, genre) in levels.items():
            co = Corpus(genre=genre, access_level=level, id_cleaned=cleaned[key].id_cleaned)
            s.add(co)
            await s.flush()
            out[key] = co.id_corpus
        out.update({k: cleaned[k].id_cleaned for k in ("c1", "c2", "c3")})
        out.update({"src1": src[1].id_source, "src2": src[2].id_source, "org1": orgs[1].id_org, "org2": orgs[2].id_org})
        out.update({f"u_{k}": u.id_user for k, u in users.items()})
        await s.commit()
    return out


async def login(client, email: str, password: str = PASSWORD) -> dict:
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
