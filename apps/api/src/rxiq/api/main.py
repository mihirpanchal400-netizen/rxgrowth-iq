"""FastAPI application entry point.

Phase 0 ships the app factory, health surface, and CORS only. Routers arrive in Phase 3
once the metric engine they expose exists -- see docs/ROADMAP.md.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rxiq import __version__
from rxiq.config import Settings, get_settings

TITLE: Final = "RxGrowth IQ API"

DESCRIPTION: Final = """
Prescription growth intelligence.

**All data served by this API is synthetic.** See `docs/compliance.md`.
"""


class Health(BaseModel):
    """Liveness response."""

    status: str
    version: str
    environment: str


class MetricEnvelope(BaseModel):
    """Envelope every metric-bearing response is wrapped in.

    ``definition_id`` and ``period_basis`` travel with the value so the UI can show how a
    number was calculated without inferring it from the endpoint. ``causal`` marks
    correlational metrics -- ``promo.call_yield`` in particular -- so neither the UI nor
    the narrative layer can present an association as a cause. See
    docs/metric-dictionary.md section 9.
    """

    definition_id: str
    period_basis: str
    alignment_basis: str = "CURRENT"
    causal: bool = False
    data_as_of: str | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Takes settings as a parameter so tests can construct an app without touching the
    environment.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health, tags=["meta"])
    def health() -> Health:
        """Liveness probe."""
        return Health(
            status="ok",
            version=__version__,
            environment=settings.environment,
        )

    return app


app = create_app()
