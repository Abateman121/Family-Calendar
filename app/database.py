from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os
import logging

logger = logging.getLogger('app')

# Database URL - SQLite file in data directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
SQLITE_DB_PATH = os.path.join(DATA_DIR, "family.db")
DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
    poolclass=NullPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Run migrations to bring the database up to date."""
    from alembic import config, command
    logger.info("Loading Alembic config")
    # Get the path to the alembic.ini file
    alembic_cfg = config.Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    logger.info("Alembic config loaded")
    logger.info("Running upgrade to head")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Upgrade completed successfully")
    except Exception as e:
        logger.error(f"Error during upgrade: {e}")
        logger.error(f"Exception type: {type(e)}")
        raise