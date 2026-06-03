"""
Contrôles d'intégrité exposés comme tâches Kestra distinctes.

Chaque check interroge la base après une étape du pipeline et lève une
AssertionError si un invariant n'est pas tenu → la tâche Kestra passe en
FAILED (visible rouge dans l'UI, et tracée dans audit.run_log via `step`).

Tâches `test_*` intercalées dans le flow, centralisées dans un module Python
plutôt qu'en scripts inline.

Usage :
    python -m src.validate.checks <nom_du_check>

Checks disponibles : voir le dict CHECKS en bas de fichier.
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from src.load.db import session_scope
from src.monitoring.metrics import step


def _scalar(sql: str) -> int:
    with session_scope() as s:
        return int(s.execute(text(sql)).scalar_one())


def check_employees_loaded() -> None:
    n = _scalar("SELECT COUNT(*) FROM staging.employees")
    assert n > 0, "staging.employees est vide — extract_rh a échoué"
    print(f"[TEST OK] staging.employees = {n} salariés")


def check_sports_practice_loaded() -> None:
    n = _scalar("SELECT COUNT(*) FROM staging.sports_practice")
    assert n > 0, "staging.sports_practice est vide — extract_sport a échoué"
    print(f"[TEST OK] staging.sports_practice = {n} lignes")


def check_activities_generated() -> None:
    n_raw = _scalar("SELECT COUNT(*) FROM raw.activities")
    assert n_raw >= 500, f"raw.activities = {n_raw} (< 500) — génération suspecte"
    n = _scalar("SELECT COUNT(*) FROM staging.activities")
    # L'aplatissement raw → staging doit être sans perte.
    assert n == n_raw, (
        f"aplatissement incomplet : staging.activities ({n}) != raw.activities ({n_raw})"
    )
    future = _scalar("SELECT COUNT(*) FROM staging.activities WHERE start_dt > now()")
    assert future == 0, f"{future} activités datées dans le futur"
    print(f"[TEST OK] raw={n_raw}, staging={n} (lossless), 0 date dans le futur")


def check_advantages_computed() -> None:
    nb_emp = _scalar("SELECT COUNT(*) FROM staging.employees")
    nb_prime = _scalar("SELECT COUNT(*) FROM marts.eligibility_prime")
    nb_wb = _scalar("SELECT COUNT(*) FROM marts.eligibility_wellbeing")
    assert nb_prime == nb_emp, (
        f"eligibility_prime ({nb_prime}) != employees ({nb_emp})"
    )
    assert nb_wb == nb_emp, (
        f"eligibility_wellbeing ({nb_wb}) != employees ({nb_emp})"
    )
    print(f"[TEST OK] éligibilités calculées pour {nb_emp} salariés "
          f"(prime + bien-être)")


CHECKS = {
    "employees_loaded": check_employees_loaded,
    "sports_practice_loaded": check_sports_practice_loaded,
    "activities_generated": check_activities_generated,
    "advantages_computed": check_advantages_computed,
}


def main(name: str) -> None:
    if name not in CHECKS:
        raise SystemExit(
            f"check inconnu : '{name}'. Disponibles : {', '.join(CHECKS)}"
        )
    # On enrobe dans `step` : le résultat (OK/FAIL) atterrit aussi dans
    # audit.run_log, cohérent avec le reste du monitoring du pipeline.
    with step(f"check_{name}"):
        CHECKS[name]()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python -m src.validate.checks <nom_du_check>")
    main(sys.argv[1])
