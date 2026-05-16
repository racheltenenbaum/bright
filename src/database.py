from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# Railway provides mysql:// but SQLAlchemy needs mysql+pymysql:// to use PyMySQL
_db_url = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

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
