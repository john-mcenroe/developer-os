import os
import psycopg2
from psycopg2 import pool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "host=localhost port=5433 dbname=landos user=postgres password=postgres"
)

_pool: pool.SimpleConnectionPool | None = None


def get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 10, DATABASE_URL)
    return _pool


def get_conn():
    return get_pool().getconn()


def put_conn(conn):
    get_pool().putconn(conn)
