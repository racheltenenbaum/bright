import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database import _normalize_db_url
from src.models import Base

# Several migrations are raw MySQL (AUTO_INCREMENT, ALGORITHM=INSTANT, ...),
# so the chain can only be checked against a real MySQL server. CI provides
# one (.github/workflows/tests.yml); locally, point this at any throwaway
# MySQL server, e.g. MIGRATION_TEST_MYSQL_URL=mysql://root@127.0.0.1:3307
MYSQL_SERVER_URL = os.getenv("MIGRATION_TEST_MYSQL_URL")


@pytest.mark.skipif(not MYSQL_SERVER_URL, reason="MIGRATION_TEST_MYSQL_URL not set")
def test_upgrade_head_builds_every_table_on_an_empty_database():
    # A staging (or any fresh) database starts empty and is built only by
    # `alembic upgrade head` on deploy, so the migration chain on its own must
    # create every table and column the models use — not just patch ones
    # production happened to already have.
    server_url = _normalize_db_url(MYSQL_SERVER_URL).rstrip("/")
    db_name = f"bright_migrations_{uuid.uuid4().hex[:8]}"
    server = create_engine(server_url)
    with server.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    db_url = f"{server_url}/{db_name}"
    try:
        # Separate process: alembic.ini's logging config would otherwise
        # reset logging for the rest of the test session (breaking caplog).
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env={**os.environ, "DATABASE_URL": db_url},
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        missing_tables = set(Base.metadata.tables) - tables
        assert not missing_tables, f"tables never created by migrations: {sorted(missing_tables)}"

        missing_columns = [
            f"{table.name}.{col.name}"
            for table in Base.metadata.sorted_tables
            for col in table.columns
            if col.name not in {c["name"] for c in inspector.get_columns(table.name)}
        ]
        assert not missing_columns, f"columns never created by migrations: {missing_columns}"
        engine.dispose()
    finally:
        with server.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        server.dispose()
