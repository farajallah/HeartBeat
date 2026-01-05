import os
from datetime import datetime, date, timedelta
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.models import Base, Settings, AttendanceSheet

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
        connect_args={"check_same_thread": False, "timeout": 20},
        echo=False
    )
else:
    # PostgreSQL configuration
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables if they don't exist"""
    # Check if tables already exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # Only create tables if they don't exist
    if not existing_tables or 'settings' not in existing_tables:
        # Create tables one by one to ensure proper order
        Base.metadata.create_all(bind=engine, tables=[Settings.__table__], checkfirst=True)
        Base.metadata.create_all(bind=engine, tables=[AttendanceSheet.__table__], checkfirst=True)
        
        # Create any remaining tables that weren't explicitly listed
        Base.metadata.create_all(bind=engine, checkfirst=True)
    else:
        # Tables exist, just check if we need to update schemas
        Base.metadata.create_all(bind=engine, checkfirst=True)


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let the caller handle it


def init_default_settings():
    """Initialize default settings if not exists"""
    from datetime import date, timedelta
    
    db = SessionLocal()
    try:
        # Check if settings already exist
        settings = db.query(Settings).first()
        if not settings:
            # Default working days: Saturday to Wednesday (5-day work week)
            default_working_days = "Sat,Sun,Mon,Tue,Wed"
            
            # Default date range: current month
            today = date.today()
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)  # Get to the end of the month
            end_date = next_month - timedelta(days=next_month.day - 1) - timedelta(days=1)
            
            # Create default settings
            default_settings = Settings(
                device_id="DEFAULT",
                start_date=start_date,
                end_date=end_date,
                working_days=default_working_days,
                daily_working_hours=8.0  # Default 8 hours
            )
            db.add(default_settings)
            db.commit()
            
            # Initialize attendance records for the current month
            initialize_attendance_records(db, default_settings)
            
    finally:
        db.close()


def ensure_time_required_populated(db: Session):
    """Ensure all attendance records have time_required populated"""
    from app.services.attendance_service import AttendanceService
    
    # Get settings
    settings = db.query(Settings).first()
    if not settings:
        return
    
    # Find records with missing time_required
    records_missing_time_required = db.query(AttendanceSheet).filter(
        AttendanceSheet.time_required.is_(None)
    ).all()
    
    if records_missing_time_required:
        print(f"📋 Populating time_required for {len(records_missing_time_required)} records...")
        
        # Parse working days
        working_days = []
        if settings.working_days:
            try:
                import json
                working_days = json.loads(settings.working_days)
            except:
                working_days = [0, 1, 2, 3, 4]  # Default Mon-Fri
        
        # Update each record
        for record in records_missing_time_required:
            record.time_required = AttendanceService.calculate_time_required(
                record.category, settings.daily_working_hours
            )
        
        db.commit()
        print("✅ time_required populated for all records")


def initialize_attendance_records(db: Session, settings: Settings):
    """Initialize attendance records for the date range in settings"""
    # Get all dates in the range
    current_date = settings.start_date
    delta = timedelta(days=1)
    
    while current_date <= settings.end_date:
        # Determine category: 0=workday, 1=weekend, 90=holiday (can be updated later)
        weekday = current_date.weekday()
        
        # Handle working_days in both formats: comma-separated integers or day names
        if settings.working_days:
            try:
                # Try parsing as integers first (new format)
                working_days = [int(x) for x in settings.working_days.split(',')]
            except ValueError:
                # Fall back to day names (old format)
                day_name_to_weekday = {
                    'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6,
                    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
                }
                working_days = [day_name_to_weekday.get(x.strip(), 0) for x in settings.working_days.split(',')]
        else:
            working_days = [0,1,2,3,4]  # Default Mon-Fri
        
        category = 0 if weekday in working_days else 1
        
        # Check if record already exists
        existing = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == settings.device_id,
            AttendanceSheet.date == current_date
        ).first()
        
        if not existing:
            # Create new attendance record
            record = AttendanceSheet(
                device_id=settings.device_id,
                date=current_date,
                category=category,
                time_required=AttendanceService.calculate_time_required(category, settings.daily_working_hours),
                time_recorded=0  # Start with 0 minutes recorded
            )
            db.add(record)
        else:
            # Update existing record to ensure time_required is set
            if existing.time_required is None:
                existing.time_required = AttendanceService.calculate_time_required(existing.category, settings.daily_working_hours)
    
        current_date += delta
    
    db.commit()
