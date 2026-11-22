"""Vérifie que les modèles SQLAlchemy forment un schéma cohérent et que la chaîne métier fonctionne."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app import models  # noqa: F401
from app.models import (CleanedText, Corpus, CorpusRevision, DatasetItem, DatasetVersion, Organisation,
                        RawText, Review, Role, Source, User)

EXPECTED_TABLES = {
    "organisation", "role", "utilisateur", "source", "scraping_job", "texte_brut", "fichier_media",
    "texte_nettoye", "revue", "corpus", "corpus_revision", "dataset_version", "dataset_item",
    "training_run", "model_artifact", "generation", "audit_log",
}


def make_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_all_tables_present():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_full_business_chain():
    with make_session() as db:
        org = Organisation(name="Demo", slug="demo")
        role = Role(code="reviewer", libelle="Relecteur")
        db.add_all([org, role]); db.flush()
        user = User(email="r@x.mg", password_hash="h", id_role=role.id_role, id_org=org.id_org)
        src = Source(name="S", url="https://x", type="web", license="CC BY-SA 4.0", id_org=org.id_org)
        db.add_all([user, src]); db.flush()
        raw = RawText(title="Tantara", content="Ny tantara", language="mg", id_source=src.id_source,
                      origin_url="https://x/a")
        db.add(raw); db.flush()
        cl = CleanedText(content="Ny tantara", word_count=2, dedupe_hash="a" * 64, id_raw=raw.id_raw)
        db.add(cl); db.flush()
        db.add(Review(action="validate", id_user=user.id_user, id_cleaned=cl.id_cleaned))
        co = Corpus(genre="tantara", access_level="public", id_cleaned=cl.id_cleaned)
        db.add(co); db.flush()
        db.add(CorpusRevision(content="Ny tantara (corrigé)", id_corpus=co.id_corpus, id_user=user.id_user))
        ds = DatasetVersion(name="v1.0", path="/data/v1.jsonl", id_org=org.id_org)
        db.add(ds); db.flush()
        db.add(DatasetItem(id_dataset=ds.id_dataset, id_corpus=co.id_corpus))
        db.commit()

        assert db.scalar(select(Corpus.genre)) == "tantara"
        assert raw.cleaned.corpus.revisions[0].content.endswith("(corrigé)")
        assert org.users[0].role.code == "reviewer"
