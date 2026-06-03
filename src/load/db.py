"""
Utilitaires d'accès à PostgreSQL.

Un seul `Engine` partagé par process (lru_cache). Tous les inserts passent par
SQLAlchemy → paramétrés, anti-injection, gestion des types côté driver.
"""
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Engine SQLAlchemy partagé. pool_pre_ping pour survivre aux DB restart."""
    return create_engine(
        settings.db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager classique : commit / rollback / close auto."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def truncate_tables(*qualified_names: str) -> None:
    """TRUNCATE atomique d'une liste de tables `schema.table`."""
    if not qualified_names:
        return
    targets = ", ".join(qualified_names)
    with session_scope() as s:
        # Pas de RESTART IDENTITY : nécessiterait l'ownership des séquences.
        # Les ID sont des surrogates, leur continuité n'a pas d'importance.
        s.execute(text(f"TRUNCATE {targets} CASCADE"))
