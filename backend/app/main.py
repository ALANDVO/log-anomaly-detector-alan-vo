import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.auth import router as auth_router
from app.api.logs import router as logs_router
from app.api.incidents import router as incidents_router
from app.api.evaluation import router as eval_router
from app.api.audit import router as audit_router

def get_product_version() -> str:
    """Reads product version from VERSION file or pyproject.toml."""
    version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "1.0.0"

PRODUCT_VERSION = get_product_version()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify safety constraints: refuse demo mode in production
    settings.verify_runtime_safety()
    # Initialize SQLite tables and schemas
    init_db()
    yield

app = FastAPI(
    title="log-anomaly-detector-alan-vo",
    description="AI-powered Log Anomaly Detection, Cross-Service Event Correlation, and Root-Cause Advisory",
    version=PRODUCT_VERSION,
    lifespan=lifespan
)

# CORS setup
origins = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(logs_router)
app.include_router(incidents_router)
app.include_router(eval_router)
app.include_router(audit_router)

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Healthcheck endpoint for Docker and load balancers."""
    return {
        "status": "healthy",
        "version": PRODUCT_VERSION,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.DEMO_MODE,
        "auth_provider": "keycloak-oidc"
    }

@app.get("/api/meta", tags=["Metadata"])
async def get_metadata():
    """Exposes public non-secret configuration and version metadata."""
    return {
        "name": "log-anomaly-detector-alan-vo",
        "version": PRODUCT_VERSION,
        "author": "Alan Vo",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_configured": bool(settings.LLM_API_KEY.strip()),
        "demo_mode": settings.DEMO_MODE
    }
