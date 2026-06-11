from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.routes import router

app = FastAPI(
    title="HealthAI Admin API",
    description=(
        "API d'administration HealthAI Coach — CRUD complet sur les données, "
        "workflow de validation, export et analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Expose Prometheus metrics on /internal-metrics (scraped by Prometheus, visualised in
# Grafana). NB : pas /metrics car ce chemin est déjà pris par le CRUD des métriques
# quotidiennes (metrique_quotidienne) de l'API admin.
Instrumentator().instrument(app).expose(app, endpoint="/internal-metrics", include_in_schema=False)
