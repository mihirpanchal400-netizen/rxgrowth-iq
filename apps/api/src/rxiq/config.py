"""Application configuration.

Local development runs without Docker: a DuckDB file is the warehouse and SQLite holds
application state, both reached through SQLAlchemy so that moving to Postgres is a
connection-string change rather than a rewrite. See docs/ADR/0001-architecture.md
decision 9.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    """Runtime settings, overridable by environment variable or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="RXIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "ci", "staging", "production"] = "local"
    debug: bool = True

    # --- storage -----------------------------------------------------------
    warehouse_path: Path = Field(
        default=DATA_DIR / "rxiq.duckdb",
        description="DuckDB warehouse file. Swapped for a Postgres DSN at Phase 9.",
    )
    app_database_url: str = Field(
        default=f"sqlite:///{(DATA_DIR / 'app.sqlite').as_posix()}",
        description="Application state. SQLAlchemy URL, so Postgres is a config change.",
    )

    # --- api ---------------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

    # --- domain defaults ---------------------------------------------------
    # CLAUDE.md forbids magic numbers. Every default below is a domain decision, not a
    # convenience, and each is justified where it is defined.

    nbrx_lookback_months: int = Field(
        default=12,
        description=(
            "Months of absence before a prescription counts as new-to-brand. Twelve is the "
            "common vendor default; brands with long treatment cycles override it."
        ),
    )
    decile_count: int = Field(
        default=10,
        description="Deciles are ranked on market volume, not brand volume.",
    )
    peer_target_percentile: int = Field(
        default=75,
        description=(
            "Percentile of peer-cohort share used as the achievable target in opportunity "
            "sizing. The 75th is attainable by definition -- a quarter of the cohort is "
            "already there -- unlike a max-based target."
        ),
    )
    min_peer_cohort_size: int = Field(
        default=30,
        description=(
            "Below this, the cohort falls back to a coarser one (drop access_status, then "
            "decile). A percentile over eight prescribers is noise presented as a benchmark."
        ),
    )
    writer_status_threshold_pct: float = Field(
        default=0.10,
        description=(
            "Change below this magnitude is CONTINUING rather than GROWING or DECLINING. "
            "Prevents ordinary week-to-week variance from reading as a trend."
        ),
    )

    @property
    def is_local(self) -> bool:
        """True when running on a developer machine."""
        return self.environment == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings.

    Cached so that configuration is read once per process. ``core/`` must never call
    this -- pure functions take their parameters explicitly.
    """
    return Settings()
