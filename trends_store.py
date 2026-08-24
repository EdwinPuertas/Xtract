"""Persistencia de la serie de tiempo de tendencias.

Guarda un resumen (KPIs + análisis de texto agregado) de cada corrida
programada de recolección de posts (ver `trends_job.py`), para poder ver su
evolución en la vista `/trends`.

Usa una base de datos Postgres externa (Neon, Supabase, Vercel Postgres,
etc.) porque el despliegue en Vercel no tiene disco persistente entre
invocaciones serverless: no hay dónde más guardar el histórico.
"""

import json
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL,
    query TEXT NOT NULL,
    post_count INTEGER NOT NULL,
    analyzed_count INTEGER NOT NULL,
    kpis JSONB NOT NULL,
    nlp JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS trend_runs_run_at_idx ON trend_runs (run_at);
"""


def _connection_string() -> str:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError(
            "Falta DATABASE_URL. Configura la cadena de conexión de tu base de datos "
            "Postgres (Neon, Supabase, Vercel Postgres, etc.) para usar /trends."
        )
    return dsn


def get_connection():
    return psycopg2.connect(_connection_string())


def ensure_schema() -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA)
    finally:
        conn.close()


def save_run(
    query: str,
    post_count: int,
    analyzed_count: int,
    kpis: dict,
    nlp: dict,
    run_at: datetime | None = None,
) -> int:
    run_at = run_at or datetime.now(timezone.utc)
    ensure_schema()
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trend_runs (run_at, query, post_count, analyzed_count, kpis, nlp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_at, query, post_count, analyzed_count, json.dumps(kpis), json.dumps(nlp)),
                )
                run_id = cur.fetchone()[0]
        return run_id
    finally:
        conn.close()


def get_recent_runs(limit: int = 60) -> list[dict]:
    """Devuelve hasta `limit` corridas, de la más antigua a la más reciente
    (orden natural para graficar una serie de tiempo de izquierda a derecha)."""
    ensure_schema()
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM (
                        SELECT id, run_at, query, post_count, analyzed_count, kpis, nlp
                        FROM trend_runs
                        ORDER BY run_at DESC
                        LIMIT %s
                    ) recientes
                    ORDER BY run_at ASC
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
