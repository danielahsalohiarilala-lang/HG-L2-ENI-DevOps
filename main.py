import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    if not DATABASE_URL:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS corpus (
            id SERIAL PRIMARY KEY,
            titre VARCHAR(100),
            genre VARCHAR(100),
            mots INT,
            statut VARCHAR(50)
        );
    """)
    cur.execute("SELECT COUNT(*) as c FROM corpus")
    if cur.fetchone()['c'] == 0:
        cur.execute("""
            INSERT INTO corpus (titre, genre, mots, statut) VALUES
            ('Gazety Malagasy', 'Actualité', 4320, 'Validé'),
            ('Tantara Ntaolo', 'Culture / Histoire', 8150, 'Validé'),
            ('Hira Gasy Collection', 'Poésie / Musique', 2900, 'En attente');
        """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM corpus ORDER BY id")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        source = "PostgreSQL Render"
        sous_titre = "Données chargées depuis la base PostgreSQL • Lecture vocale des textes réels"
    except Exception as e:
        rows = [
            {'id':1,'titre':'Gazety Malagasy','genre':'Actualité','mots':4320,'statut':'Validé'},
            {'id':2,'titre':'Tantara Ntaolo','genre':'Culture / Histoire','mots':8150,'statut':'Validé'},
            {'id':3,'titre':'Hira Gasy Collection','genre':'Poésie / Musique','mots':2900,'statut':'En attente'},
        ]
        source = "Démo locale"
        sous_titre = "Données chargées depuis la base MySQL • Lecture vocale des textes réels"

    total = len(rows)
    valides = sum(1 for r in rows if r['statut']=='Validé')

    lignes = ""
    for r in rows:
        couleur = "#2563eb" if r['statut']=='Validé' else "#f59e0b"
        lignes += f"""
        <tr>
            <td>#{r['id']}</td>
            <td><b>{r['titre']}</b></td>
            <td><span style="background:#eef2ff;color:#4f46e5;padding:5px 12px;border-radius:20px;font-size:13px">{r['genre']}</span></td>
            <td>{r['mots']:,}</td>
            <td><span style="background:#eef2ff;color:{couleur};padding:5px 12px;border-radius:20px;font-size:13px">{r['statut']}</span></td>
            <td><button onclick="alert('Lecture : {r['titre']}')" style="background:#eef2ff;border:1px solid #c7d2fe;color:#4f46e5;padding:6px 12px;border-radius:20px;cursor:pointer">🔊 Écouter</button></td>
        </tr>"""

    return f"""
    <html><head><meta charset="utf-8"><style>
    body{{font-family:Segoe UI, sans-serif;background:#f8f7ff;padding:20px;margin:0}}
    .header{{background:#1d4ed8;color:white;padding:25px 30px;border-radius:15px}}
    .header p{{opacity:0.8;margin:5px 0 0}}
    .cards{{display:flex;gap:20px;margin:20px 0}}
    .card{{flex:1;background:white;padding:20px;border-radius:15px;box-shadow:0 2px 10px #eee}}
    .card h1{{font-size:32px;margin:5px 0}}
    .box{{background:white;padding:20px;border-radius:15px}}
    table{{width:100%;border-collapse:collapse;margin-top:15px}}
    th{{text-align:left;color:#666;font-size:13px;padding:12px}}
    td{{padding:14px 12px;border-top:1px solid #eee}}
    </style></head><body>
    <div class="header"><h1>Gestion du Corpus Malgache</h1><p>{sous_titre}</p></div>
    <div class="cards">
        <div class="card"><small>TOTAL TEXTES</small><h1>{total}</h1></div>
        <div class="card"><small>TEXTES VALIDÉS</small><h1>{valides}</h1></div>
        <div class="card"><small>SOURCE</small><h1 style="font-size:20px;color:#1d4ed8">{source}</h1></div>
    </div>
    <div class="box">
        <b>📋 Corpus chargé depuis PostgreSQL</b> <span style="float:right">⟳ Actualiser</span>
        <table><tr><th>ID</th><th>Titre / Source</th><th>Genre</th><th>Mots</th><th>Statut</th><th>Audio</th></tr>{lignes}</table>
    </div>
    </body></html>
    """
