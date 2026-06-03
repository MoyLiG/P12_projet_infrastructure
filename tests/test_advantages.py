"""
Golden values des calculs métier.

Le calcul prime = rate × salaire est trivial mais on veut surtout vérifier
que la *règle composée* (transport actif ET déclaration cohérente) est
bien câblée. Tests intégration : nécessitent une staging.employees peuplée.
"""
import pytest
from sqlalchemy import text

from src.load.db import session_scope
from src.transform.advantages import compute_prime, compute_wellbeing


pytestmark = pytest.mark.integration


def _reset_and_seed():
    with session_scope() as s:
        s.execute(text(
            "TRUNCATE staging.employees, staging.activities, "
            "marts.eligibility_prime, marts.eligibility_wellbeing CASCADE"
        ))
        # 3 cas de test :
        # 1) actif + déclaration OK  -> éligible prime
        # 2) actif + suspect          -> NON éligible (flag rouge)
        # 3) transports en commun     -> NON éligible
        s.execute(text("""
            INSERT INTO staging.employees
                (id_employee, nom, prenom, nom_hash, date_naissance, bu,
                 date_embauche, salaire_brut, type_contrat, jours_cp,
                 adresse_domicile, moyen_deplacement,
                 distance_domicile_m, is_declaration_suspect)
            VALUES
                (1, 'A', 'A', 'h1', '1990-01-01', 'Marketing', '2020-01-01',
                 30000, 'CDI', 25, 'addr1', 'Marche/running', 5000, FALSE),
                (2, 'B', 'B', 'h2', '1990-01-01', 'R&D', '2020-01-01',
                 50000, 'CDI', 25, 'addr2', 'Vélo/Trottinette/Autres', 60000, TRUE),
                (3, 'C', 'C', 'h3', '1990-01-01', 'Ventes', '2020-01-01',
                 40000, 'CDI', 25, 'addr3', 'Transports en commun', NULL, FALSE)
        """))


def test_prime_golden_values():
    _reset_and_seed()
    nb = compute_prime(rate=0.05, run_id="test-run")
    assert nb == 1  # seul le salarié 1 est éligible

    with session_scope() as s:
        rows = s.execute(text(
            "SELECT id_employee, is_eligible, prime_amount, reason "
            "FROM marts.eligibility_prime ORDER BY id_employee"
        )).all()

    assert rows[0] == (1, True, 1500.00, 'OK — transport actif + déclaration cohérente')
    assert rows[1][1] is False
    assert "suspecte" in rows[1][3]
    assert rows[2][1] is False
    assert "non actif" in rows[2][3]


def test_prime_rate_change_recomputes():
    """Démo OC : changer le taux relance le calcul, prime_amount change."""
    _reset_and_seed()
    compute_prime(rate=0.05, run_id="r1")
    compute_prime(rate=0.07, run_id="r2")
    with session_scope() as s:
        amount = s.execute(text(
            "SELECT prime_amount FROM marts.eligibility_prime WHERE id_employee=1"
        )).scalar_one()
    assert amount == 2100.00  # 0.07 × 30 000


def test_wellbeing_threshold_boundary():
    """Salarié avec exactement threshold activités → éligible."""
    _reset_and_seed()
    with session_scope() as s:
        # 15 activités récentes pour l'employé 1
        s.execute(text("""
            INSERT INTO staging.activities
                (id_employee, start_dt, end_dt, sport_type, distance_m)
            SELECT 1, now() - (g || ' days')::interval,
                   now() - (g || ' days')::interval + interval '1 hour',
                   'Course à pied', 5000
            FROM generate_series(1, 15) AS g
        """))
    nb = compute_wellbeing(threshold=15, run_id="r3")
    assert nb == 1

    nb_high = compute_wellbeing(threshold=16, run_id="r4")
    assert nb_high == 0
