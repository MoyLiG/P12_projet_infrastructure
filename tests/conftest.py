"""
Configuration pytest.

Marqueur custom `@pytest.mark.integration` pour les tests nécessitant
Postgres en route. Lancés seulement si `RUN_INTEGRATION=1` est set →
en CI ou en local quand la stack docker tourne.

    # tests unitaires seuls
    pytest -m "not integration"

    # tout (Postgres requis sur localhost:5432)
    RUN_INTEGRATION=1 pytest
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: nécessite Postgres en route")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="integration tests skipped (RUN_INTEGRATION!=1)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
