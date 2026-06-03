"""
Suite Great Expectations sur les données du POC.

API GE 1.x ("Fluent API") avec un contexte éphémère — pas de Data Context
persistant : la suite est définie ici, le rapport JSON est écrit dans
data/ge_docs/. Cohérent avec l'esprit "code as source of truth".

Le module est appelé par Kestra entre l'étape generate_activities et
compute_advantages. **En cas d'expectation non satisfaite, on lève une
exception** → Kestra marque l'exécution FAILED et envoie l'alerte mail.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import great_expectations as gx
import pandas as pd
from great_expectations import expectations as gxe
from sqlalchemy import text

from src.load.db import session_scope
from src.monitoring.metrics import step


GE_DOCS_DIR = Path("data/ge_docs")


def _load_employees() -> pd.DataFrame:
    with session_scope() as s:
        return pd.read_sql(
            text(
                "SELECT id_employee, salaire_brut, jours_cp, moyen_deplacement, "
                "       distance_domicile_m, is_declaration_suspect "
                "FROM staging.employees"
            ),
            s.connection(),
        )


def _load_activities() -> pd.DataFrame:
    with session_scope() as s:
        return pd.read_sql(
            text(
                "SELECT id_activity, id_employee, start_dt, end_dt, "
                "       sport_type, distance_m, moving_time_s, "
                "       EXTRACT(EPOCH FROM (end_dt - start_dt))::int AS elapsed_s "
                "FROM staging.activities"
            ),
            s.connection(),
        )


def _validate(df: pd.DataFrame, suite_name: str, expectations: list) -> dict:
    """Construit une suite GE éphémère et valide le DataFrame."""
    context = gx.get_context(mode="ephemeral")
    ds = context.data_sources.add_pandas(name=f"src_{suite_name}")
    asset = ds.add_dataframe_asset(name=suite_name)
    batch_def = asset.add_batch_definition_whole_dataframe(f"{suite_name}_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=suite_name)
    for exp in expectations:
        suite.add_expectation(exp)
    context.suites.add(suite)

    result = batch.validate(suite)
    return result.to_json_dict()


EMPLOYEES_EXPECTATIONS = [
    gxe.ExpectColumnValuesToNotBeNull(column="id_employee"),
    gxe.ExpectColumnValuesToBeUnique(column="id_employee"),
    gxe.ExpectColumnValuesToBeBetween(column="salaire_brut", min_value=10000, max_value=300000),
    gxe.ExpectColumnValuesToBeBetween(column="jours_cp", min_value=0, max_value=60),
    gxe.ExpectColumnValuesToBeInSet(
        column="moyen_deplacement",
        value_set=[
            "Marche/running",
            "Vélo/Trottinette/Autres",
            "Transports en commun",
            "véhicule thermique/électrique",
        ],
    ),
]


ACTIVITIES_EXPECTATIONS = [
    gxe.ExpectColumnValuesToNotBeNull(column="id_employee"),
    gxe.ExpectColumnValuesToBeBetween(
        column="distance_m", min_value=0, max_value=200_000, strict_max=False
    ),
    gxe.ExpectColumnValuesToNotBeNull(column="start_dt"),
    gxe.ExpectColumnValuesToNotBeNull(column="end_dt"),
    # moving_time (temps en mouvement) toujours <= elapsed (temps écoulé) :
    # invariant fondamental du modèle Strava qu'on simule.
    gxe.ExpectColumnValuesToBeBetween(
        column="moving_time_s", min_value=0, max_value=86_400, strict_max=False
    ),
    gxe.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="elapsed_s", column_B="moving_time_s", or_equal=True
    ),
    # Pas de date dans le futur — pour la cohérence du POC sur 12 mois passés.
    gxe.ExpectColumnMaxToBeBetween(
        column="start_dt",
        min_value=datetime(2024, 1, 1, tzinfo=timezone.utc),
        max_value=datetime.now(tz=timezone.utc),
    ),
]


def run_all(extra_out: Path | None = None) -> dict:
    """Exécute les deux suites et écrit un rapport JSON. Raise si KO.

    `extra_out` : chemin supplémentaire où copier le rapport (utilisé par le
    flow Kestra pour l'exposer en outputFile téléchargeable). Le rapport est
    écrit AVANT le raise éventuel, donc disponible même si une suite échoue.
    """
    GE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    with step("ge_employees") as ctx:
        df_emp = _load_employees()
        result_emp = _validate(df_emp, "employees", EMPLOYEES_EXPECTATIONS)
        ctx.rows_in = ctx.rows_out = len(df_emp)
        if not result_emp.get("success", False):
            ctx.status = "FAIL"
            ctx.message = "Expectations employees non satisfaites"

    with step("ge_activities") as ctx:
        df_act = _load_activities()
        result_act = _validate(df_act, "activities", ACTIVITIES_EXPECTATIONS)
        ctx.rows_in = ctx.rows_out = len(df_act)
        if not result_act.get("success", False):
            ctx.status = "FAIL"
            ctx.message = "Expectations activities non satisfaites"

    report = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "employees": result_emp,
        "activities": result_act,
    }
    payload = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    out = GE_DOCS_DIR / f"validation_{datetime.now(tz=timezone.utc):%Y%m%d_%H%M%S}.json"
    out.write_text(payload, encoding="utf-8")
    if extra_out is not None:
        extra_out.write_text(payload, encoding="utf-8")

    if not (result_emp.get("success") and result_act.get("success")):
        raise AssertionError(
            f"Suite GE en échec — détail : {out}"
        )
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Chemin supplémentaire où copier le rapport JSON (ex. pour "
             "l'exposer en outputFile Kestra).",
    )
    args = parser.parse_args()
    report = run_all(extra_out=args.out)
    print(f"OK — qualité validée. Rapport JSON dans {GE_DOCS_DIR}")
