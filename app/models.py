from datetime import date, datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Heartbeat(Base):
    __tablename__ = "heartbeat"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=False)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)


class DailyAttendance(Base):
    __tablename__ = "daily_attendance"
    
    date = Column(Date, primary_key=True)
    recorded_minutes = Column(Integer, nullable=False)


class Correction(Base):
    __tablename__ = "correction"
    
    date = Column(Date, primary_key=True)
    corrected_minutes = Column(Integer, nullable=False)
    reason = Column(Text)


class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    start_date = Column(Date)
    end_date = Column(Date)
    working_days = Column(String)  # JSON string of weekdays
    daily_required_minutes = Column(Integer)
    
    __table_args__ = (
        CheckConstraint('id = 1', name='settings_id_check'),
    )


class Holiday(Base):
    __tablename__ = "holiday"
    
    date = Column(Date, primary_key=True)
    description = Column(Text)
