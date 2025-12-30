from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models import Heartbeat, DailyAttendance, Correction, Settings, Holiday
import json


class AttendanceService:
    
    @staticmethod
    def record_heartbeat(db: Session, device_id: str) -> None:
        """Record a new heartbeat"""
        heartbeat = Heartbeat(device_id=device_id)
        db.add(heartbeat)
        db.commit()
        
        # Update daily attendance cache
        AttendanceService._update_daily_attendance(db, heartbeat.ts.date())
    
    @staticmethod
    def _update_daily_attendance(db: Session, target_date: date) -> None:
        """Update or create daily attendance record for given date"""
        # Count heartbeats for this date
        heartbeat_count = db.query(Heartbeat).filter(
            func.date(Heartbeat.ts) == target_date
        ).count()
        
        # Get or create daily attendance record
        daily_attendance = db.query(DailyAttendance).filter(
            DailyAttendance.date == target_date
        ).first()
        
        if daily_attendance:
            daily_attendance.recorded_minutes = heartbeat_count
        else:
            daily_attendance = DailyAttendance(
                date=target_date,
                recorded_minutes=heartbeat_count
            )
            db.add(daily_attendance)
        
        db.commit()
    
    @staticmethod
    def recalculate_all_attendance(db: Session) -> None:
        """Recalculate all daily attendance from raw heartbeats"""
        # Get all dates with heartbeats
        dates_with_heartbeats = db.query(
            func.date(Heartbeat.ts).label('date')
        ).distinct().all()
        
        for row in dates_with_heartbeats:
            AttendanceService._update_daily_attendance(db, row.date)
    
    @staticmethod
    def get_settings(db: Session) -> Optional[Settings]:
        """Get application settings"""
        return db.query(Settings).filter(Settings.id == 1).first()
    
    @staticmethod
    def update_settings(db: Session, **kwargs) -> Settings:
        """Update application settings"""
        settings = AttendanceService.get_settings(db)
        if not settings:
            settings = Settings(id=1)
            db.add(settings)
        
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        db.commit()
        db.refresh(settings)
        
        # Recalculate attendance after settings change
        AttendanceService.recalculate_all_attendance(db)
        
        return settings
    
    @staticmethod
    def get_working_days(db: Session) -> List[int]:
        """Get list of working days (0=Monday, 6=Sunday)"""
        settings = AttendanceService.get_settings(db)
        if not settings or not settings.working_days:
            return [1, 2, 3, 4, 5]  # Default Monday-Friday
        
        try:
            return json.loads(settings.working_days)
        except (json.JSONDecodeError, TypeError):
            return [1, 2, 3, 4, 5]
    
    @staticmethod
    def is_working_day(db: Session, check_date: date) -> bool:
        """Check if given date is a working day"""
        weekday = check_date.weekday()  # 0=Monday, 6=Sunday
        working_days = AttendanceService.get_working_days(db)
        return weekday in working_days
    
    @staticmethod
    def is_holiday(db: Session, check_date: date) -> bool:
        """Check if given date is a holiday"""
        holiday = db.query(Holiday).filter(Holiday.date == check_date).first()
        return holiday is not None
    
    @staticmethod
    def is_in_reporting_period(db: Session, check_date: date) -> bool:
        """Check if date is within reporting period"""
        settings = AttendanceService.get_settings(db)
        if not settings:
            return True  # No period restriction if no settings
        
        # Convert string dates to date objects if needed
        start_date = None
        end_date = None
        
        if settings.start_date:
            if isinstance(settings.start_date, str):
                try:
                    from datetime import datetime
                    start_date = datetime.strptime(settings.start_date, "%Y-%m-%d").date()
                except ValueError:
                    start_date = None
            else:
                start_date = settings.start_date
        
        if settings.end_date:
            if isinstance(settings.end_date, str):
                try:
                    from datetime import datetime
                    end_date = datetime.strptime(settings.end_date, "%Y-%m-%d").date()
                except ValueError:
                    end_date = None
            else:
                end_date = settings.end_date
        
        if start_date and check_date < start_date:
            return False
        if end_date and check_date > end_date:
            return False
        
        return True
    
    @staticmethod
    def get_required_minutes(db: Session, check_date: date) -> int:
        """Get required minutes for given date"""
        # Check if date is outside reporting period
        if not AttendanceService.is_in_reporting_period(db, check_date):
            return 0
        
        # Check if date is a holiday
        if AttendanceService.is_holiday(db, check_date):
            return 0
        
        # Check if date is a working day
        if not AttendanceService.is_working_day(db, check_date):
            return 0
        
        # Get daily required minutes from settings
        settings = AttendanceService.get_settings(db)
        if settings and settings.daily_required_minutes:
            return settings.daily_required_minutes
        
        return 8 * 60  # Default 8 hours = 480 minutes
    
    @staticmethod
    def get_effective_minutes(db: Session, check_date: date) -> int:
        """Get effective worked minutes for given date"""
        # Check for correction first
        correction = db.query(Correction).filter(Correction.date == check_date).first()
        if correction:
            return correction.corrected_minutes
        
        # Get recorded minutes from daily attendance
        attendance = db.query(DailyAttendance).filter(
            DailyAttendance.date == check_date
        ).first()
        
        if attendance:
            return attendance.recorded_minutes
        
        return 0
    
    @staticmethod
    def get_daily_balance(db: Session, check_date: date) -> int:
        """Calculate daily balance (effective - required)"""
        effective = AttendanceService.get_effective_minutes(db, check_date)
        required = AttendanceService.get_required_minutes(db, check_date)
        return effective - required
    
    @staticmethod
    def get_date_range_data(db: Session, start_date: date, end_date: date) -> List[Dict]:
        """Get attendance data for date range"""
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            effective = AttendanceService.get_effective_minutes(db, current_date)
            required = AttendanceService.get_required_minutes(db, current_date)
            balance = effective - required
            
            data.append({
                'date': current_date,
                'effective_minutes': effective,
                'required_minutes': required,
                'balance_minutes': balance,
                'is_working_day': AttendanceService.is_working_day(db, current_date),
                'is_holiday': AttendanceService.is_holiday(db, current_date),
            })
            
            current_date += timedelta(days=1)
        
        return data
    
    @staticmethod
    def get_monthly_summary(db: Session, year: int, month: int) -> Dict:
        """Get monthly attendance summary"""
        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get data for the month
        monthly_data = AttendanceService.get_date_range_data(db, first_day, last_day)
        
        # Calculate totals
        total_effective = sum(item['effective_minutes'] for item in monthly_data)
        total_required = sum(item['required_minutes'] for item in monthly_data)
        total_balance = total_effective - total_required
        
        return {
            'year': year,
            'month': month,
            'total_effective_minutes': total_effective,
            'total_required_minutes': total_required,
            'total_balance_minutes': total_balance,
            'days': monthly_data
        }
    
    @staticmethod
    def get_total_balance(db: Session) -> int:
        """Get total balance across all dates"""
        # Get all dates with any activity
        all_dates = db.query(
            func.date(Heartbeat.ts).label('date')
        ).union(
            db.query(Correction.date)
        ).distinct().all()
        
        total_balance = 0
        for row in all_dates:
            # Convert string date to date object if needed
            if isinstance(row.date, str):
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(row.date, "%Y-%m-%d").date()
                except ValueError:
                    continue  # Skip invalid dates
            else:
                date_obj = row.date
            
            total_balance += AttendanceService.get_daily_balance(db, date_obj)
        
        return total_balance
    
    @staticmethod
    def add_correction(db: Session, correction_date: date, corrected_minutes: int, reason: str) -> Correction:
        """Add or update correction for given date"""
        correction = db.query(Correction).filter(Correction.date == correction_date).first()
        
        if correction:
            correction.corrected_minutes = corrected_minutes
            correction.reason = reason
        else:
            correction = Correction(
                date=correction_date,
                corrected_minutes=corrected_minutes,
                reason=reason
            )
            db.add(correction)
        
        db.commit()
        db.refresh(correction)
        return correction
    
    @staticmethod
    def get_holidays(db: Session) -> List[Holiday]:
        """Get all holidays"""
        return db.query(Holiday).order_by(Holiday.date).all()
    
    @staticmethod
    def add_holiday(db: Session, holiday_date: date, description: str) -> Holiday:
        """Add a holiday"""
        holiday = Holiday(date=holiday_date, description=description)
        db.add(holiday)
        db.commit()
        db.refresh(holiday)
        
        # Recalculate attendance after holiday addition
        AttendanceService.recalculate_all_attendance(db)
        
        return holiday
    
    @staticmethod
    def delete_holiday(db: Session, holiday_date: date) -> bool:
        """Delete a holiday"""
        holiday = db.query(Holiday).filter(Holiday.date == holiday_date).first()
        if holiday:
            db.delete(holiday)
            db.commit()
            
            # Recalculate attendance after holiday deletion
            AttendanceService.recalculate_all_attendance(db)
            return True
        return False
