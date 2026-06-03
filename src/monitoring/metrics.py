"""
Monitoring du pipeline.

Chaque étape Python du pipeline écrit une ligne dans `audit.run_log` :
- run_id : identifiant Kestra (ou UUID local si lancé hors Kestra)
- step_name : 'extract_rh', 'generate_activities', 'compute_prime', ...
- rows_in / rows_out : volumétrie
- duration_ms
- status : OK / WARN / FAIL
- message : détail éventuel

Utilisable comme context manager :

    with step("extract_rh", run_id) as ctx:
        df = ...
        ctx.rows_in = len(raw_df)
        ctx.rows_out = len(df)
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from sqlalchemy import text

from src.load.db import session_scope


def current_run_id() -> str:
    """Récupère le run_id Kestra (passé via env) ou en génère un local."""
    return os.environ.get("KESTRA_EXECUTION_ID") or f"local-{uuid.uuid4().hex[:8]}"


@dataclass
class StepContext:
    step_name: str
    run_id: str
    rows_in: Optional[int] = None
    rows_out: Optional[int] = None
    message: Optional[str] = None
    status: str = "OK"   # OK / WARN / FAIL


@contextmanager
def step(step_name: str, run_id: Optional[str] = None) -> Iterator[StepContext]:
    """Mesure durée + statut d'une étape, écrit dans audit.run_log."""
    rid = run_id or current_run_id()
    ctx = StepContext(step_name=step_name, run_id=rid)
    t0 = time.perf_counter()
    try:
        yield ctx
    except Exception as e:
        ctx.status = "FAIL"
        ctx.message = f"{type(e).__name__}: {e}"
        raise
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        with session_scope() as s:
            s.execute(
                text(
                    """
                    INSERT INTO audit.run_log
                        (run_id, step_name, status, rows_in, rows_out, duration_ms, message)
                    VALUES
                        (:run_id, :step_name, :status, :rows_in, :rows_out, :duration_ms, :message)
                    """
                ),
                {
                    "run_id": ctx.run_id,
                    "step_name": ctx.step_name,
                    "status": ctx.status,
                    "rows_in": ctx.rows_in,
                    "rows_out": ctx.rows_out,
                    "duration_ms": duration_ms,
                    "message": ctx.message,
                },
            )
