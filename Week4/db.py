import os
from typing import Any, Sequence

import psycopg2
from psycopg2.extensions import connection as Connection
from psycopg2.extras import execute_values as pg_execute_values, RealDictCursor, RealDictRow
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG: dict[str, Any] = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", 5432),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "dbname":   os.getenv("DB_NAME", "rides-2"),
}


class Database:
    def __init__(self, config: dict[str, Any] | None = None, autocommit: bool = False):
        self.config: dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
        self.autocommit = autocommit
        self.conn: Connection | None = None

    def connect(self) -> "Database":
        self.conn = psycopg2.connect(
            host=self.config.get("host"),
            port=self.config.get("port"),
            user=self.config.get("user"),
            password=self.config.get("password"),
            dbname=self.config.get("dbname"),
        )
        self.conn.autocommit = self.autocommit
        return self

    def _connection(self) -> Connection:
        assert self.conn is not None, "call connect() first"
        return self.conn

    def execute(self, query: str, params: Sequence[Any] | None = None) -> None:
        with self._connection().cursor() as cur:
            cur.execute(query, params)

    def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[tuple]:
        with self._connection().cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetch_dicts(self, query: str, params: Sequence[Any] | None = None) -> list[RealDictRow]:
        with self._connection().cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute_values(self, query: str, rows: Sequence[Sequence[Any]], page_size: int = 1000) -> None:
        with self._connection().cursor() as cur:
            pg_execute_values(cur, query, rows, page_size=page_size)

    def insert_returning(
        self,
        query: str,
        rows: Sequence[Sequence[Any]],
        page_size: int = 1000,
    ) -> list[tuple[Any, Any]]:
        with self._connection().cursor() as cur:
            result = pg_execute_values(cur, query, rows, fetch=True, page_size=page_size)
        assert result is not None
        return result

    def commit(self) -> None:
        self._connection().commit()

    def rollback(self) -> None:
        self._connection().rollback()

    def close(self) -> None:
        self._connection().close()
