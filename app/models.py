from datetime import date
from sqlalchemy import Column, Integer, String, Date, Text, Float, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(10), unique=True, nullable=False)  # e.g., 'ABC-DEF'
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    working_days = Column(String(50), nullable=False)  # Comma-separated weekdays (e.g., 'Mon,Tue,Wed,Thu,Sat')
    daily_working_hours = Column(Float, nullable=False, default=8.0)  # Working hours per day (can be fractional)
    
    __table_args__ = (
        CheckConstraint('LENGTH(device_id) > 0', name='device_id_not_empty'),
        CheckConstraint('start_date <= end_date', name='valid_date_range'),
        CheckConstraint('daily_working_hours > 0', name='positive_working_hours'),
    )

class AttendanceSheet(Base):
    __tablename__ = 'attendance_sheet'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    # Note: check_in and check_out replaced with time_recorded
    time_recorded = Column(Integer, nullable=False, default=0)  # Actual time worked in minutes
    category = Column(Integer, nullable=False)  # 0: workday, 1: weekend, 10: leave (half day), 11: leave (full day), 90: holiday
    description = Column(Text, nullable=True)  # For holiday descriptions
    time_required = Column(Integer, nullable=False, default=0)  # Required time in minutes for the day
    
    __table_args__ = (
        UniqueConstraint('device_id', 'date', name='unique_attendance_per_date'),
        CheckConstraint('category IN (0, 1, 10, 11, 90)', name='valid_category'),
        CheckConstraint('time_required >= 0', name='non_negative_required_time'),
        CheckConstraint('time_recorded >= 0', name='non_negative_recorded_time'),
        Index('idx_attendance_date', 'date'),
        Index('idx_attendance_device_date', 'device_id', 'date'),
    )
