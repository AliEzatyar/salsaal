from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import QueuePool
from os import environ

# Ensure DATABASE_URL is defined before the check
DATABASE_URL = environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,  # default was 5
    max_overflow=40,  # allow 40 extra under burst load
    pool_timeout=10,  # seconds before giving up (reduce from 30)
    pool_recycle=3600,  # 30 minutes keeping connection
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
metadata = MetaData()
