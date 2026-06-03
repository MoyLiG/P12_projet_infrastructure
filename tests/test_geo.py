"""Tests des helpers géo. L'appel API est mocké via `responses`."""
import math

import pytest

from src.validate.geo import COMPANY_COORDS, address_hash, haversine_m


def test_address_hash_stable_and_normalized():
    a = address_hash("128 Rue du Port, 34000 Frontignan")
    b = address_hash("128 rue du Port, 34000 frontignan  ")
    assert a == b  # casse + espaces normalisés
    assert len(a) == 64


def test_haversine_zero_when_same_point():
    assert haversine_m(COMPANY_COORDS, COMPANY_COORDS) == 0


def test_haversine_paris_lattes_within_known_range():
    # Paris approx, Lattes approx → ~600-700 km à vol d'oiseau.
    paris = (48.8566, 2.3522)
    d_km = haversine_m(paris, COMPANY_COORDS) / 1000
    assert 580 <= d_km <= 740, f"Distance haversine inattendue : {d_km:.1f} km"


def test_haversine_short_distance_montpellier():
    # Montpellier centre → Lattes ≈ 8 km à vol d'oiseau.
    montpellier = (43.6108, 3.8767)
    d_km = haversine_m(montpellier, COMPANY_COORDS) / 1000
    assert 4 <= d_km <= 12
