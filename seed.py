"""Données de démonstration : organisation, utilisateurs, sources.

Utilisation (dans Docker) :  docker compose exec api python -m scripts.seed
Le script est idempotent : on peut le relancer sans créer de doublons.
"""
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Organisation, Role, Source, User

SOURCES = [
    ("Wikipédia en malgache", "https://mg.wikipedia.org", "web", "CC BY-SA 4.0"),
    ("YouTube (liens et métadonnées)", "https://www.youtube.com", "youtube", "Licence YouTube standard (référence uniquement)"),
    ("Dépôt manuel", "manual://depot", "manual", "À préciser pour chaque archive"),
]


async def main() -> None:
    s = get_settings()
    async with SessionLocal() as db:
        org = (await db.execute(select(Organisation).where(Organisation.slug == "demo"))).scalar_one_or_none()
        if org is None:
            org = Organisation(name="Organisation de démonstration", slug="demo")
            db.add(org)
            await db.flush()
            print("+ organisation 'demo' créée")

        roles = {r.code: r for r in (await db.execute(select(Role))).scalars()}
        if not roles:
            raise SystemExit("Les rôles sont absents : le script 01_schema.sql n'a pas été exécuté.")

        users = [(s.admin_email, "admin"), ("relecteur@tantara.mg", "reviewer"), ("lecteur@tantara.mg", "reader")]
        for email, role_code in users:
            exists = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if exists is None:
                db.add(User(email=email, password_hash=hash_password(s.admin_password),
                            id_role=roles[role_code].id_role, id_org=org.id_org))
                print(f"+ utilisateur {email} ({role_code})")

        for name, url, type_, lic in SOURCES:
            exists = (await db.execute(select(Source).where(Source.id_org == org.id_org, Source.url == url))).scalar_one_or_none()
            if exists is None:
                db.add(Source(name=name, url=url, type=type_, license=lic, id_org=org.id_org))
                print(f"+ source {name}")
        await db.commit()
    print("Terminé. Connexion de démonstration :", s.admin_email, "(mot de passe défini dans .env)")


if __name__ == "__main__":
    asyncio.run(main())
