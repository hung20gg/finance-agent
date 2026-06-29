from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg


def normalize_sql(sql_text: str) -> str:
    sql_text = sql_text.strip()
    sql_text = re.sub(r"`([^`]+)`", r'"\1"', sql_text)
    sql_text = re.sub(
        r"YEAR\s*\(\s*CURDATE\s*\(\s*\)\s*\)\s*",
        "2020",
        sql_text,
        flags=re.IGNORECASE,
    )
    return sql_text


def _default_postgres_url() -> Optional[str]:
    return os.getenv("POSTGRES_URL") or os.getenv("MAC_SQL_POSTGRES_URL")


def _default_postgres_schema() -> str:
    return os.getenv("MAC_SQL_POSTGRES_SCHEMA", "public")


@lru_cache(maxsize=8)
def load_db_config(config_path: str | None) -> Dict[str, Any]:
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


def is_sqlite_path(target: str) -> bool:
    return bool(target) and target.endswith(".sqlite") and os.path.exists(target)


def resolve_db_target(
    db_id: str,
    db_root_path: str | None = None,
    postgres_url: str | None = None,
    schema: str | None = None,
    db_config_path: str | None = None,
) -> Dict[str, str]:
    postgres_url = postgres_url or _default_postgres_url()
    schema = schema or _default_postgres_schema()
    config = load_db_config(db_config_path or os.getenv("MAC_SQL_DB_CONFIG_PATH"))

    if db_id in config:
        entry = config[db_id]
        if isinstance(entry, str):
            return {"driver": "postgres", "db_id": db_id, "postgres_url": entry, "schema": schema}
        if entry.get("driver") == "sqlite":
            return {"driver": "sqlite", "db_id": db_id, "path": entry["path"]}
        return {
            "driver": "postgres",
            "db_id": db_id,
            "postgres_url": entry.get("postgres_url", postgres_url),
            "schema": entry.get("schema", schema),
        }

    if db_root_path:
        sqlite_path = os.path.join(db_root_path, db_id, db_id + ".sqlite")
        if os.path.exists(sqlite_path):
            return {"driver": "sqlite", "db_id": db_id, "path": sqlite_path}

    if is_sqlite_path(db_id):
        return {"driver": "sqlite", "db_id": db_id, "path": db_id}

    if not postgres_url:
        raise ValueError(
            f"Could not resolve database target for {db_id}. "
            "Set POSTGRES_URL or provide --db-config-path."
        )
    return {"driver": "postgres", "db_id": db_id, "postgres_url": postgres_url, "schema": schema}


def get_execution_targets(
    db_id_or_path: str,
    db_root_path: str | None = None,
    postgres_url: str | None = None,
    schema: str | None = None,
    db_config_path: str | None = None,
) -> List[Dict[str, str]]:
    target = resolve_db_target(
        db_id=db_id_or_path,
        db_root_path=db_root_path,
        postgres_url=postgres_url,
        schema=schema,
        db_config_path=db_config_path,
    )
    if target["driver"] == "sqlite":
        db_dir = os.path.dirname(target["path"])
        db_paths = [
            os.path.join(db_dir, basename)
            for basename in os.listdir(db_dir)
            if basename.endswith(".sqlite")
        ]
        return [{"driver": "sqlite", "db_id": target["db_id"], "path": path} for path in db_paths]
    return [target]


def _connect_postgres(target: Dict[str, str]):
    return psycopg.connect(target["postgres_url"])


def execute_query(
    query: str,
    target: Dict[str, str],
    timeout_seconds: float = 30.0,
) -> List[Tuple[Any, ...]]:
    query = normalize_sql(query)
    if target["driver"] == "sqlite":
        import sqlite3

        conn = sqlite3.connect(target["path"])
        conn.text_factory = lambda b: b.decode(errors="ignore")
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()

    timeout_ms = max(1, int(timeout_seconds * 1000))
    with _connect_postgres(target) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {timeout_ms}")
            cur.execute(f'SET search_path TO "{target["schema"]}"')
            cur.execute(query)
            return cur.fetchall()


def time_query(
    query: str,
    target: Dict[str, str],
    timeout_seconds: float = 30.0,
) -> float:
    started = time.perf_counter()
    execute_query(query, target, timeout_seconds=timeout_seconds)
    return time.perf_counter() - started


def get_schema_dict(target: Dict[str, str]) -> Dict[str, List[str]]:
    if target["driver"] == "sqlite":
        import sqlite3

        schema = {}
        conn = sqlite3.connect(target["path"])
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [str(table[0].lower()) for table in cursor.fetchall()]
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            schema[table] = [str(col[1].lower()) for col in cursor.fetchall()]
        conn.close()
        return schema

    query = """
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = %s
    ORDER BY table_name, ordinal_position
    """
    schema: Dict[str, List[str]] = {}
    with _connect_postgres(target) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (target["schema"],))
            for table_name, column_name in cur.fetchall():
                schema.setdefault(str(table_name).lower(), []).append(str(column_name).lower())
    return schema
