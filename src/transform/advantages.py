"""
Calcul des deux avantages métier.

Règles (cf. note de cadrage Juliette) :

**Prime sportive** : prime_rate × salaire_brut si le salarié :
  - déclare Marche/running OU Vélo/Trottinette comme moyen de déplacement
  - ET sa déclaration n'est PAS suspecte (distance ≤ seuil)

**Jours bien-être** : 5 jours si le salarié a réalisé ≥ threshold activités
sportives sur les 365 derniers jours.

Les deux paramètres sont injectés depuis Kestra (inputs du flow) — c'est
ce qui rend la démo live possible (changer le taux et relancer).
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from src.config import settings
from src.load.db import session_scope
from src.monitoring.metrics import current_run_id, step


ACTIVE_TRANSPORTS = ("Marche/running", "Vélo/Trottinette/Autres")
WELLBEING_DAYS_GRANTED = 5


def compute_prime(rate: float, run_id: str) -> int:
    """Insère / remplace les lignes marts.eligibility_prime. Retourne nb éligibles."""
    sql = """
    INSERT INTO marts.eligibility_prime
        (id_employee, is_eligible, prime_rate, prime_amount, reason, run_id)
    SELECT
        e.id_employee,
        (e.moyen_deplacement = ANY(:active)
            AND COALESCE(e.is_declaration_suspect, FALSE) = FALSE) AS is_eligible,
        :rate AS prime_rate,
        CASE
            WHEN e.moyen_deplacement = ANY(:active)
                 AND COALESCE(e.is_declaration_suspect, FALSE) = FALSE
            THEN ROUND((:rate * e.salaire_brut)::numeric, 2)
            ELSE 0
        END AS prime_amount,
        CASE
            WHEN e.moyen_deplacement = ANY(:active)
                 AND COALESCE(e.is_declaration_suspect, FALSE) = FALSE
            THEN 'OK — transport actif + déclaration cohérente'
            WHEN e.moyen_deplacement = ANY(:active)
                 AND e.is_declaration_suspect = TRUE
            THEN 'KO — déclaration suspecte (distance hors seuil)'
            ELSE 'KO — transport non actif'
        END AS reason,
        :run_id
    FROM staging.employees e
    ON CONFLICT (id_employee) DO UPDATE SET
        is_eligible = EXCLUDED.is_eligible,
        prime_rate  = EXCLUDED.prime_rate,
        prime_amount= EXCLUDED.prime_amount,
        reason      = EXCLUDED.reason,
        computed_at = now(),
        run_id      = EXCLUDED.run_id
    """
    with session_scope() as s:
        s.execute(text(sql), {"rate": rate, "active": list(ACTIVE_TRANSPORTS), "run_id": run_id})
        nb = s.execute(
            text("SELECT COUNT(*) FROM marts.eligibility_prime WHERE is_eligible")
        ).scalar_one()
    return int(nb)


def compute_wellbeing(threshold: int, run_id: str) -> int:
    """Insère / remplace marts.eligibility_wellbeing. Retourne nb éligibles."""
    sql = """
    WITH counts AS (
        SELECT
            e.id_employee,
            COALESCE(COUNT(a.id_activity), 0) AS activity_count
        FROM staging.employees e
        LEFT JOIN staging.activities a
            ON a.id_employee = e.id_employee
           AND a.start_dt >= now() - INTERVAL '365 days'
        GROUP BY e.id_employee
    )
    INSERT INTO marts.eligibility_wellbeing
        (id_employee, is_eligible, activity_count, threshold, days_granted, reason, run_id)
    SELECT
        c.id_employee,
        (c.activity_count >= :threshold) AS is_eligible,
        c.activity_count,
        :threshold,
        CASE WHEN c.activity_count >= :threshold THEN :days ELSE 0 END,
        CASE
            WHEN c.activity_count >= :threshold
            THEN 'OK — ' || c.activity_count || ' activités sur 12 mois'
            ELSE 'KO — ' || c.activity_count || ' activités < seuil ' || :threshold
        END,
        :run_id
    FROM counts c
    ON CONFLICT (id_employee) DO UPDATE SET
        is_eligible    = EXCLUDED.is_eligible,
        activity_count = EXCLUDED.activity_count,
        threshold      = EXCLUDED.threshold,
        days_granted   = EXCLUDED.days_granted,
        reason         = EXCLUDED.reason,
        computed_at    = now(),
        run_id         = EXCLUDED.run_id
    """
    with session_scope() as s:
        s.execute(
            text(sql),
            {"threshold": threshold, "days": WELLBEING_DAYS_GRANTED, "run_id": run_id},
        )
        nb = s.execute(
            text("SELECT COUNT(*) FROM marts.eligibility_wellbeing WHERE is_eligible")
        ).scalar_one()
    return int(nb)


def run(prime_rate: float, wellbeing_threshold: int) -> dict:
    rid = current_run_id()

    with step("compute_prime") as ctx:
        nb_prime = compute_prime(prime_rate, rid)
        ctx.rows_out = nb_prime
        ctx.message = f"{nb_prime} salariés éligibles à la prime ({prime_rate:.2%})"

    with step("compute_wellbeing") as ctx:
        nb_wb = compute_wellbeing(wellbeing_threshold, rid)
        ctx.rows_out = nb_wb
        ctx.message = f"{nb_wb} salariés éligibles aux {WELLBEING_DAYS_GRANTED} jours bien-être"

    return {
        "prime_rate": prime_rate,
        "wellbeing_threshold": wellbeing_threshold,
        "nb_eligible_prime": nb_prime,
        "nb_eligible_wellbeing": nb_wb,
        "run_id": rid,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prime-rate", type=float, default=settings.prime_rate_default)
    parser.add_argument(
        "--wellbeing-threshold",
        type=int,
        default=settings.wellbeing_activity_threshold,
    )
    args = parser.parse_args()
    res = run(args.prime_rate, args.wellbeing_threshold)
    print(res)
