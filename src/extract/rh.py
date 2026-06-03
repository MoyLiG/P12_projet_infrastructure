"""
Extraction RH : Données+RH.xlsx → raw.employees_xlsx + staging.employees.

Étapes :
1. Read XLSX (162 lignes attendues).
2. Insert tel quel dans raw (audit trail).
3. Typage strict + calcul nom_hash + insert dans staging.

`moyen_deplacement` est normalisé (l'enum côté DB est figé).

Usage :
    python -m src.extract.rh data/raw/Données+RH.xlsx
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.config import settings
from src.load.db import session_scope, truncate_tables
from src.monitoring.metrics import step


# Mapping libellé XLSX -> nom de colonne SQL.
COLUMN_MAP = {
    "ID salarié": "id_salarie",
    "Nom": "nom",
    "Prénom": "prenom",
    "Date de naissance": "date_naissance",
    "BU": "bu",
    "Date d'embauche": "date_embauche",
    "Salaire brut": "salaire_brut",
    "Type de contrat": "type_contrat",
    "Nombre de jours de CP": "jours_cp",
    "Adresse du domicile": "adresse_domicile",
    "Moyen de déplacement": "moyen_deplacement",
}

# Le champ source contient parfois des variations de casse / espaces. On
# normalise vers les 4 libellés exacts attendus par la contrainte CHECK SQL.
TRANSPORT_NORMALIZE = {
    "marche/running": "Marche/running",
    "vélo/trottinette/autres": "Vélo/Trottinette/Autres",
    "velo/trottinette/autres": "Vélo/Trottinette/Autres",
    "transports en commun": "Transports en commun",
    "véhicule thermique/électrique": "véhicule thermique/électrique",
    "vehicule thermique/electrique": "véhicule thermique/électrique",
}


def hash_pii(value: str) -> str:
    """SHA-256 salé d'une chaîne PII. Sel chargé depuis settings."""
    salt = settings.pii_hash_salt.get_secret_value().encode("utf-8")
    return hashlib.sha256(salt + value.encode("utf-8")).hexdigest()


def _normalize_transport(value: str) -> str:
    key = (value or "").strip().lower()
    return TRANSPORT_NORMALIZE.get(key, value)


def extract_rh(xlsx_path: Path) -> None:
    """Pipeline d'extraction RH complet."""

    with step("extract_rh_read"):
        df_raw = pd.read_excel(xlsx_path, sheet_name=0)
        if list(df_raw.columns) != list(COLUMN_MAP.keys()):
            raise ValueError(
                f"Colonnes XLSX inattendues : {list(df_raw.columns)}"
            )

    # --- Insert dans raw (copie 1:1) -----------------------------------
    with step("extract_rh_load_raw") as ctx:
        df_for_raw = df_raw.rename(columns=COLUMN_MAP).copy()
        df_for_raw["source_file"] = xlsx_path.name
        truncate_tables("raw.employees_xlsx")
        df_for_raw.to_sql(
            "employees_xlsx",
            schema="raw",
            con=__engine(),
            if_exists="append",
            index=False,
            method="multi",
        )
        ctx.rows_in = len(df_raw)
        ctx.rows_out = len(df_for_raw)

    # --- Typage + insert dans staging ----------------------------------
    with step("extract_rh_to_staging") as ctx:
        df = df_raw.rename(columns=COLUMN_MAP).copy()
        df["id_salarie"] = df["id_salarie"].astype("int64")
        df["date_naissance"] = pd.to_datetime(df["date_naissance"]).dt.date
        df["date_embauche"] = pd.to_datetime(df["date_embauche"]).dt.date
        df["salaire_brut"] = df["salaire_brut"].astype(float).round(2)
        df["jours_cp"] = df["jours_cp"].astype(int)
        df["moyen_deplacement"] = df["moyen_deplacement"].map(_normalize_transport)
        df["nom_hash"] = (df["nom"] + df["prenom"]).map(hash_pii)

        rows = [
            {
                "id_employee": int(r.id_salarie),
                "nom": r.nom,
                "prenom": r.prenom,
                "nom_hash": r.nom_hash,
                "date_naissance": r.date_naissance,
                "bu": r.bu,
                "date_embauche": r.date_embauche,
                "salaire_brut": float(r.salaire_brut),
                "type_contrat": r.type_contrat,
                "jours_cp": int(r.jours_cp),
                "adresse_domicile": r.adresse_domicile,
                "moyen_deplacement": r.moyen_deplacement,
            }
            for r in df.itertuples(index=False)
        ]

        with session_scope() as s:
            # Truncate cascadé : on perd activities/eligibility, c'est voulu
            # (le pipeline les recalcule ensuite). En prod on ferait un UPSERT.
            s.execute(
                text(
                    "TRUNCATE staging.employees, staging.activities, "
                    "staging.sports_practice, marts.eligibility_prime, "
                    "marts.eligibility_wellbeing CASCADE"
                )
            )
            s.execute(
                text(
                    """
                    INSERT INTO staging.employees (
                        id_employee, nom, prenom, nom_hash, date_naissance, bu,
                        date_embauche, salaire_brut, type_contrat, jours_cp,
                        adresse_domicile, moyen_deplacement
                    ) VALUES (
                        :id_employee, :nom, :prenom, :nom_hash, :date_naissance, :bu,
                        :date_embauche, :salaire_brut, :type_contrat, :jours_cp,
                        :adresse_domicile, :moyen_deplacement
                    )
                    """
                ),
                rows,
            )
        ctx.rows_in = len(df_raw)
        ctx.rows_out = len(rows)


def __engine():
    # Import paresseux pour éviter une dépendance circulaire avec config.
    from src.load.db import get_engine
    return get_engine()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/donnees_rh.xlsx")
    extract_rh(path)
    print(f"OK — RH extraite depuis {path}")
