from src.database import _normalize_db_url, get_db


def test_normalize_db_url_converts_raw_mysql_scheme():
    assert _normalize_db_url("mysql://user:pass@host/db") == "mysql+pymysql://user:pass@host/db"


def test_normalize_db_url_leaves_pymysql_scheme_unchanged():
    url = "mysql+pymysql://user:pass@host/db"
    assert _normalize_db_url(url) == url


def test_normalize_db_url_leaves_other_schemes_unchanged():
    assert _normalize_db_url("sqlite:///test.db") == "sqlite:///test.db"


def test_get_db_yields_session_and_closes_it():
    gen = get_db()
    db = next(gen)
    assert db is not None
    gen.close()  # triggers the generator's finally: db.close()
