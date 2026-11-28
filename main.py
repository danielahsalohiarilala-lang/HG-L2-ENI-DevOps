import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    if not DATABASE_URL:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS corpus (
            id SERIAL PRIMARY KEY,
            source VARCHAR(100),
            categorie VARCHAR(100),
            mots INT,
            statut VARCHAR(50)
        );
    """)
    cur.execute("SELECT COUNT(*) as c FROM corpus")
    if cur.fetchone()['c'] == 0:
        cur.execute("""
            INSERT INTO corpus (source, categorie, mots, statut) VALUES
            ('Gazety Malagasy', 'Actualité', 4320, 'Nettoyé'),
            ('Tantara Ntaolo', 'Culture / Histoire', 8150, 'Nettoyé'),
            ('Hira Gasy Collection', 'Poésie / Musique', 2900, 'En traitement');
        """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM corpus ORDER BY id")
        rows = cur.fetchall()
        total = len(rows)
        nettoyes = sum(1 for r in rows if r['statut'] == 'Nettoyé')
        total_mots = sum(r['mots'] for r in rows)
        cur.close()
        conn.close()
    except Exception as e:
        rows = []
        total = 0
        nettoyes = 0
        total_mots = 0

    lignes = "".join([f"<tr><td>{r['source']}</td><td>{r['categorie']}</td><td>{r['mots']:,}</td><td>{r['statut']}</td></tr>" for r in rows])

    return f"""
    <html><head><style>body{{font-family:sans-serif;padding:20px}} .card{{display:inline-block;padding:20px;margin:10px;background:#f1f1ff;border-radius:10px}} table{{width:100%;border-collapse:collapse}} td,th{{padding:10px;border-bottom:1px solid #ddd}}</style></head>
    <body>
    <h1 style="background:#6d28d9;color:white;padding:20px;border-radius:10px">Gestion du Corpus Malgache</h1>
    <div class="card"><h3>TEXTES COLLECTÉS</h3><h1>{total}</h1><p>En base PostgreSQL</p></div>
    <div class="card"><h3>TEXTES NETTOYÉS</h3><h1>{nettoyes}</h1></div>
    <div class="card"><h3>MOTS TRAITÉS</h3><h1>{total_mots:,}</h1></div>
    <h2>Dernières données intégrées - {total} éléments récents (depuis tantara-db)</h2>
    <table><tr><th>Source</th><th>Catégorie</th><th>Mots traités</th><th>Statut</th></tr>{lignes}</table>
    <p>✅ Connecté à PostgreSQL via DATABASE_URL</p>
    </body></html>
    """

@app.get("/")
def root():
    return {"message": "OK, va sur /dashboard"}
