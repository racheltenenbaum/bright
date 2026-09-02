from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

def _normalize_db_url(url: str) -> str:
    """Railway provides mysql:// but SQLAlchemy needs mysql+pymysql:// to use
    PyMySQL. Must only rewrite the raw scheme — "mysql://".replace() would
    also corrupt an already-correct "mysql+pymysql://" URL, since "pymysql://"
    itself contains "mysql://" as a substring.
    """
    if url.startswith("mysql://"):
        return "mysql+pymysql://" + url[len("mysql://"):]
    return url


_db_url = _normalize_db_url(DATABASE_URL)

engine = create_engine(_db_url, pool_pre_ping=True)

# Each request gets its own DB session, which is closed when the request ends.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session, then closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
