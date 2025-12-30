import os
import sqlite3
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.models import Base

# Load environment variables from .env file first, then system environment
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

# Determine database type and configure engine accordingly
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
            "timeout": 20
        },
        echo=False
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let the caller handle it


def init_default_settings():
    """Initialize default settings if not exists"""
    from app.models import Settings
    import json
    
    db = SessionLocal()
    try:
        # Check if settings already exist
        settings = db.query(Settings).filter(Settings.id == 1).first()
        if not settings:
            # Create default settings
            default_settings = Settings(
                id=1,
                start_date=None,
                end_date=None,
                working_days=json.dumps([1, 2, 3, 4, 5]),  # Monday-Friday
                daily_required_minutes=8 * 60  # 8 hours = 480 minutes
            )
            db.add(default_settings)
            db.commit()
    finally:
        db.close()
