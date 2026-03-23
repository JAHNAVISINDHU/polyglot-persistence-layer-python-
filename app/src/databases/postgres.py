import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_db,
        )
    return _pool


def execute(query: str, params=None):
    conn = get_pool().getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            conn.commit()
            try:
                return cur.fetchall()
            except Exception:
                return []
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        get_pool().putconn(conn)


def connect():
    p = get_pool()
    conn = p.getconn()
    p.putconn(conn)
    logger.info("PostgreSQL connection verified")


def close():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("PostgreSQL pool closed")
