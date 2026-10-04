"""
FastAPI application entry point.
Mounts presentation routes, REST API routers, static assets, and lifecycle hooks.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from project.config.settings import settings
from project.config.database import init_db
from project.routes.jobs import router as jobs_router
from project.routes.results import router as results_router
from project.routes.errors import router as errors_router
from project.routes.dashboard import router as dashboard_router
from project.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown hooks."""
    logger.info("Initializing Automated Web Data Acquisition System...")
    try:
        await init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as db_exc:
        logger.warning(
            f"Could not connect to PostgreSQL on startup ({db_exc}). "
            "Database operations will require an active database connection."
        )
    yield
    logger.info("Shutting down Web Data Acquisition System.")


app = FastAPI(
    title="Automated Web Data Acquisition and Preprocessing System",
    description="Moderate-scale web data crawler and dataset preprocessor for LLM training.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static assets
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount Presentation Layer routes (HTML UI)
app.include_router(dashboard_router)

# Mount Application Layer REST API routes
app.include_router(jobs_router)
app.include_router(results_router)
app.include_router(errors_router)
