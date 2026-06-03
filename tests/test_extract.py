"""Tests unitaires des helpers d'extraction RH."""
import os

import pytest

from src.extract.rh import _normalize_transport, hash_pii


def test_normalize_transport_canonical_forms():
    assert _normalize_transport("Marche/running") == "Marche/running"
    assert _normalize_transport("MARCHE/RUNNING") == "Marche/running"
    assert _normalize_transport("velo/trottinette/autres") == "Vélo/Trottinette/Autres"
    assert _normalize_transport("Transports en commun") == "Transports en commun"


def test_normalize_transport_passthrough_unknown():
    # Une valeur inconnue est renvoyée telle quelle → la contrainte CHECK SQL
    # bloquera. On ne veut PAS masquer silencieusement.
    assert _normalize_transport("inventé") == "inventé"


def test_hash_pii_stable_for_same_input():
    a = hash_pii("Audrey Colin")
    b = hash_pii("Audrey Colin")
    assert a == b
    assert len(a) == 64  # SHA-256 hex


def test_hash_pii_changes_with_salt(monkeypatch):
    from src import config
    # Salt 1
    monkeypatch.setattr(
        config.settings, "pii_hash_salt",
        type(config.settings.pii_hash_salt)("salt-A"),
    )
    h1 = hash_pii("Audrey Colin")
    # Salt 2
    monkeypatch.setattr(
        config.settings, "pii_hash_salt",
        type(config.settings.pii_hash_salt)("salt-B"),
    )
    h2 = hash_pii("Audrey Colin")
    assert h1 != h2
