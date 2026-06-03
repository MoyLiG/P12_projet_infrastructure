"""
Extraction de la pratique sportive déclarée.

Note métier : la table source contient 1000 lignes pour 162 salariés, avec
beaucoup de NULL. On suppose : un salarié peut déclarer plusieurs sports →
plusieurs lignes (clé composite id_employee + sport). Les NULL sont écartés.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.load.db import get_engine, session_scope, truncate_tables
from src.monitoring.metrics import step


def extract_sport(xlsx_path: Path) -> None:
    with step("extract_sport_read"):
        df = pd.read_excel(xlsx_path, sheet_name=0)
        expected = {"ID salarié", "Pratique d'un sport"}
        if set(df.columns) != expected:
            raise ValueError(f"Colonnes inattendues : {set(df.columns)}")

    with step("extract_sport_load_raw") as ctx:
        raw_df = df.rename(
            columns={"ID salarié": "id_salarie", "Pratique d'un sport": "sport_pratique"}
        ).copy()
        raw_df["source_file"] = xlsx_path.name
        truncate_tables("raw.sports_xlsx")
        raw_df.to_sql(
            "sports_xlsx",
            schema="raw",
            con=get_engine(),
            if_exists="append",
            index=False,
            method="multi",
        )
        ctx.rows_in = len(df)
        ctx.rows_out = len(raw_df)

    with step("extract_sport_to_staging") as ctx:
        clean = (
            raw_df
            .dropna(subset=["sport_pratique"])
            .assign(id_employee=lambda d: d["id_salarie"].astype(int))
            .drop_duplicates(subset=["id_employee", "sport_pratique"])
        )

        # Filtrer : ne garder que les id_employee qui existent en staging.
        with session_scope() as s:
            known = {
                r[0]
                for r in s.execute(text("SELECT id_employee FROM staging.employees"))
            }
        clean = clean[clean["id_employee"].isin(known)]

        rows = [
            {"id_employee": int(r.id_employee), "sport_pratique": r.sport_pratique}
            for r in clean.itertuples(index=False)
        ]
        if rows:
            with session_scope() as s:
                s.execute(
                    text(
                        "INSERT INTO staging.sports_practice (id_employee, sport_pratique) "
                        "VALUES (:id_employee, :sport_pratique) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    rows,
                )
        ctx.rows_in = len(df)
        ctx.rows_out = len(rows)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/donnees_sportive.xlsx")
    extract_sport(path)
    print(f"OK — pratiques sportives extraites depuis {path}")
