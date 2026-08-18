"""Scaffold smoke tests.

These assert the structural invariants Phase 0 establishes, so a later refactor that
quietly breaks one fails here rather than in Phase 2.
"""

from __future__ import annotations

import pkgutil

from fastapi.testclient import TestClient

import rxiq
from rxiq.api.main import create_app
from rxiq.config import Settings


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app(Settings(environment="ci")))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment"] == "ci"


def test_all_declared_subpackages_import() -> None:
    # The layout in docs/BRIEF.md section 2.2 is load-bearing: services import from core,
    # never the reverse. A missing package here means a later import lands somewhere else.
    expected = {"api", "core", "domain", "llm", "ml", "repositories", "services"}
    found = {module.name for module in pkgutil.iter_modules(rxiq.__path__) if module.ispkg}

    assert expected <= found, f"missing subpackages: {expected - found}"


def test_core_is_pure_no_io_imports() -> None:
    """``core/`` must not reach for I/O. See docs/ADR/0001-architecture.md decision 1.

    Checked structurally rather than by convention, because the whole property-testing
    strategy for the decomposition identities depends on these functions having no
    environment to stub.
    """
    import rxiq.core

    forbidden = {"sqlalchemy", "duckdb", "fastapi", "httpx", "requests", "datetime"}
    imported = set(vars(rxiq.core)) & forbidden

    assert not imported, f"core/ must stay pure; found I/O imports: {imported}"


def test_settings_defaults_are_domain_decisions() -> None:
    # CLAUDE.md bans magic numbers. These are the Phase 0 domain defaults; changing one is
    # a deliberate act that should break this test and prompt a docs update.
    settings = Settings()

    assert settings.nbrx_lookback_months == 12
    assert settings.peer_target_percentile == 75
    assert settings.min_peer_cohort_size == 30
    assert settings.decile_count == 10


def test_synthetic_npi_prefix_matches_the_scanner() -> None:
    """The generator and the CI gate must agree on the reserved range.

    If these drift, either the guard starts flagging our own synthetic data or -- far
    worse -- it stops flagging real identifiers. See docs/compliance.md section 1.
    """
    import rxsynth

    assert rxsynth.SYNTHETIC_NPI_PREFIX == "9"
