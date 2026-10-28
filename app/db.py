"""One Postgres connection pool, shared by the LangGraph checkpointer (short-term memory)
and the LangGraph store (long-term memory)."""
import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lily:lily@localhost:5433/lily")

# These three settings are what PostgresSaver and PostgresStore require of their connections.
pool = ConnectionPool(
    DATABASE_URL,
    max_size=int(os.getenv("DB_POOL_SIZE", "10")),
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    open=True,
)
