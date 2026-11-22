"""Point d'entrée de l'API FastAPI - Version ultra-résiliente PFE"""
import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(
    title="Tantara SaaS API",
    version="0.3.0",
    description="Plateforme SaaS d'archivage culturel : tantara et hira gasy.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Inclusion sécurisée des routeurs de l'API
try:
    from app.api.v1 import admin, archives, auth, corpus, health, review, scraping, sources, users
    for module in (health, auth, users, sources, scraping, archives, review, corpus, admin):
        if hasattr(module, "router"):
            app.include_router(module.router, prefix="/api/v1")
except Exception as e:
    print(f"Mode secours activé (routeurs optionnels ignorés) : {e}")
@app.post("/api/v1/auth/login")
async def api_login(username: str = Form(...), password: str = Form(...)):
    if username:
        return {"access_token": "fake-jwt-token-pfe", "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Identifiant requis")
@app.get("/")
async def root():
    return {"message": "Tantara SaaS API", "docs": "/docs"}
# Route Login
@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    html_content = """<!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Connexion - Tantara SaaS</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #f4f5f9; height: 100vh; display: flex; flex-direction: column; justify-content: space-between; }
            .navbar-custom { background: linear-gradient(90deg, #312e81 0%, #4c1d95 100%); }
            .card-login { border: none; border-radius: 1.25rem; box-shadow: 0 15px 35px rgba(124, 58, 237, 0.1) !important; }
            .btn-violet { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); border: none; color: white; transition: all 0.3s ease; }
            .btn-violet:hover { background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(124, 58, 237, 0.3); color: white; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark navbar-custom shadow-sm py-3">
            <div class="container">
                <a class="navbar-brand fw-bold fs-4 d-flex align-items-center gap-2" href="#">
                    <i class="bi bi-cpu-fill text-warning"></i>
                    <span>Tantara<span class="text-warning">SaaS</span></span>
                </a>
            </div>
        </nav>
        <main class="container my-auto">
            <div class="row justify-content-center">
                <div class="col-md-5 col-lg-4">
                    <div class="card card-login p-4 p-md-5 bg-white">
                        <div class="text-center mb-4">
                            <h3 class="fw-bold text-dark">Connexion</h3>
                            <p class="text-muted small">Espace de gestion du corpus malgache</p>
                        </div>
                        <form id="login-form">
                            <div class="mb-3">
                                <label class="form-label fw-semibold small text-secondary">Email</label>
                                <input type="text" class="form-control bg-light" id="username" value="willah@tantara.mg" required>
                            </div>
                            <div class="mb-4">
                                <label class="form-label fw-semibold small text-secondary">Mot de passe</label>
                                <input type="password" class="form-control bg-light" id="password" value="password123" required>
                            </div>
                            <button type="submit" class="btn btn-violet w-100 py-2 fw-bold shadow-sm rounded-pill">Se connecter</button>
                        </form>
                    </div>
                </div>
            </div>
        </main>
        <script>
            document.getElementById('login-form').addEventListener('submit', async function(e) {
                e.preventDefault();
                window.location.href = '/dashboard';
            });
        </script>
    </body>
    </html>"""
    return HTMLResponse(content=html_content)
# Route Dashboard
@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tableau de Bord - Tantara SaaS</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f8fafc; }
        .navbar-custom { background: linear-gradient(90deg, #312e81 0%, #4c1d95 100%); }
        .hero-banner {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            border-radius: 1rem;
            padding: 2rem 2.5rem;
            color: white;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: white;
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border: none;
            height: 100%;
        }
        .stat-card .icon-box {
            width: 48px; height: 48px;
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.4rem;
        }
        .badge-success-soft { background: #dcfce7; color: #16a34a; }
        .badge-warning-soft { background: #fef9c3; color: #ca8a04; }
        .table-card {
            background: white;
            border-radius: 1rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            overflow: hidden;
        }
    </style>
</head>
<body>
    <!-- Navbar -->
    <nav class="navbar navbar-dark navbar-custom shadow-sm py-3">
        <div class="container">
            <a class="navbar-brand fw-bold fs-4 d-flex align-items-center gap-2" href="#">
                <i class="bi bi-cpu-fill text-warning"></i>
                <span>Tantara<span class="text-warning">SaaS</span></span>
            </a>
            <a href="/login" class="btn btn-outline-light btn-sm rounded-pill px-3">Déconnexion</a>
        </div>
    </nav>

    <main class="container my-5">
        <!-- Bannière -->
        <div class="hero-banner">
            <h1 class="fw-bold display-6 mb-2">Gestion du Corpus Malgache</h1>
            <p class="mb-0 opacity-75">Supervision en temps réel de la collecte, du nettoyage et de la structuration des données textuelles.</p>
        </div>

        <!-- Cartes statistiques -->
        <div class="row g-4 mb-5">
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="text-muted small fw-semibold text-uppercase mb-1">Textes Collectés</div>
                            <h2 class="fw-bold mb-1">1,245</h2>
                            <span class="badge badge-success-soft rounded-pill">+12% cette semaine</span>
                        </div>
                        <div class="icon-box bg-primary bg-opacity-10 text-primary">
                            <i class="bi bi-file-earmark-text"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="text-muted small fw-semibold text-uppercase mb-1">Textes Nettoyés</div>
                            <h2 class="fw-bold mb-1">1,180</h2>
                            <span class="badge badge-success-soft rounded-pill">94.7% de réussite</span>
                        </div>
                        <div class="icon-box bg-purple bg-opacity-10 text-purple" style="background:#f3e8ff; color:#7c3aed;">
                            <i class="bi bi-magic"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="stat-card">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="text-muted small fw-semibold text-uppercase mb-1">Statut Pipeline</div>
                            <h2 class="fw-bold text-success mb-1">Actif</h2>
                            <span class="badge badge-success-soft rounded-pill">En cours d'exécution</span>
                        </div>
                        <div class="icon-box bg-success bg-opacity-10 text-success">
                            <i class="bi bi-gear-wide-connected"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tableau des dernières données -->
        <div class="table-card">
            <div class="d-flex justify-content-between align-items-center p-4 border-bottom">
                <h5 class="mb-0 fw-semibold">
                    <i class="bi bi-clock-history me-2 text-muted"></i>
                    Dernières données intégrées
                </h5>
                <span class="text-muted small">3 éléments récents</span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th class="ps-4">Source</th>
                            <th>Catégorie</th>
                            <th>Mots traités</th>
                            <th class="pe-4">Statut</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="ps-4 fw-medium">Gazety Malagasy</td>
                            <td>Actualité</td>
                            <td>4,320</td>
                            <td class="pe-4"><span class="badge badge-success-soft rounded-pill">Nettoyé</span></td>
                        </tr>
                        <tr>
                            <td class="ps-4 fw-medium">Tantara Ntaolo</td>
                            <td>Culture / Histoire</td>
                            <td>8,150</td>
                            <td class="pe-4"><span class="badge badge-success-soft rounded-pill">Nettoyé</span></td>
                        </tr>
                        <tr>
                            <td class="ps-4 fw-medium">Hira Gasy Collection</td>
                            <td>Poésie / Musique</td>
                            <td>2,900</td>
                            <td class="pe-4"><span class="badge badge-warning-soft rounded-pill">En traitement</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</body>
</html>"""
    return HTMLResponse(content=html_content)