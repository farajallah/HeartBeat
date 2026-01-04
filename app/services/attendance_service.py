from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from app.models import Settings, AttendanceSheet
import json

class AttendanceService:
    @staticmethod
    def record_heartbeat(db: Session, device_id: str):
        """Record a new heartbeat"""
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        
        # Get or create today's attendance record
        record = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == device_id,
            AttendanceSheet.date == today
        ).first()
        
        if not record:
            # Create new record if it doesn't exist
            record = AttendanceSheet(
                device_id=device_id,
                date=today,
                category=0  # Default to workday
            )
            db.add(record)
        
        # Update check-in/check-out times
        if not record.check_in:
            record.check_in = current_time
        else:
            record.check_out = current_time
        
        db.commit()
        return record

    @staticmethod
    def get_settings(db: Session) -> Optional[Settings]:
        """Get current settings"""
        return db.query(Settings).first()
        
    @classmethod
    def get_settings_cached(cls, db: Session) -> Optional[Settings]:
        """Get settings with caching"""
        return cls.get_settings(db)

    @staticmethod
    def update_settings(
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        working_days: Optional[str] = None,
        daily_required_minutes: Optional[int] = None
    ) -> Optional[Settings]:
        """Update settings"""
        settings = db.query(Settings).first()
        if not settings:
            return None
            
        if start_date is not None:
            settings.start_date = start_date
        if end_date is not None:
            settings.end_date = end_date
        if working_days is not None:
            settings.working_days = working_days
        if daily_required_minutes is not None:
            settings.daily_required_minutes = daily_required_minutes
            
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def get_holidays(db: Session, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get holidays within a date range"""
        query = db.query(AttendanceSheet).filter(AttendanceSheet.category == 90)  # 90 is holiday category
        
        if start_date:
            query = query.filter(AttendanceSheet.date >= start_date)
        if end_date:
            query = query.filter(AttendanceSheet.date <= end_date)
            
        return [
            {
                "date": holiday.date,
                "description": holiday.description or "Holiday"
            }
            for holiday in query.all()
        ]

    @staticmethod
    def calculate_time_required(category: int, daily_required_minutes: int) -> int:
        """Calculate required time in minutes based on category"""
        if category == 0:
            # Regular workday - full required time
            return daily_required_minutes
        elif category == 1:
            # Weekend - no required time
            return 0
        elif category == 10:
            # Leave (half day) - half required time
            return daily_required_minutes // 2
        elif category == 11:
            # Leave (full day) - no required time
            return 0
        elif category == 90:
            # Holiday - no required time
            return 0
        else:
            # Unknown category - assume workday
            return daily_required_minutes
    
    @staticmethod
    def update_time_required_for_date(db: Session, device_id: str, date: date, daily_required_minutes: int):
        """Update time_required for a specific attendance record"""
        record = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == device_id,
            AttendanceSheet.date == date
        ).first()
        
        if record:
            record.time_required = AttendanceService.calculate_time_required(
                record.category, daily_required_minutes
            )
            db.commit()
    
    @staticmethod
    def update_time_required_for_all(db: Session, device_id: str, daily_required_minutes: int, working_days: List[int]):
        """Update time_required for all attendance records for a device"""
        records = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == device_id
        ).all()
        
        for record in records:
            record.time_required = AttendanceService.calculate_time_required(
                record.category, daily_required_minutes
            )
        
        db.commit()
    
    @staticmethod
    def update_time_required_for_date_range(db: Session, device_id: str, start_date: date, end_date: date, 
                                          daily_required_minutes: int, working_days: List[int]):
        """Update time_required for a date range, creating records if needed"""
        current_date = start_date
        delta = timedelta(days=1)
        
        while current_date <= end_date:
            # Check if record exists
            record = db.query(AttendanceSheet).filter(
                AttendanceSheet.device_id == device_id,
                AttendanceSheet.date == current_date
            ).first()
            
            if not record:
                # Create new record
                weekday = current_date.weekday()
                category = 0 if weekday in working_days else 1
                
                record = AttendanceSheet(
                    device_id=device_id,
                    date=current_date,
                    category=category,
                    time_required=AttendanceService.calculate_time_required(category, daily_required_minutes)
                )
                db.add(record)
            else:
                # Update existing record
                record.time_required = AttendanceService.calculate_time_required(
                    record.category, daily_required_minutes
                )
            
            current_date += delta
        
        db.commit()
    
    @staticmethod
    def add_holiday(db: Session, date: date, description: str) -> Optional[Dict[str, Any]]:
        """Add a new holiday by marking the day as holiday in attendance sheet"""
        # Get current settings to get the device_id
        settings = db.query(Settings).first()
        if not settings:
            raise ValueError("No settings found. Please configure settings first.")
        
        device_id = settings.device_id
        
        # Clean up any existing records with invalid device_id
        orphaned_records = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id.notin_(
                db.query(Settings.device_id)
            )
        ).all()
        
        if orphaned_records:
            print(f"Cleaning up {len(orphaned_records)} orphaned attendance records")
            for record in orphaned_records:
                db.delete(record)
            db.commit()
        
        # Check if there's already an attendance record for this date (regardless of device_id)
        existing = db.query(AttendanceSheet).filter(
            AttendanceSheet.date == date
        ).first()
        
        if existing:
            # Update existing record to mark as holiday
            existing.category = 90  # Holiday
            existing.description = description
            existing.updated_at = datetime.utcnow()
            # Update device_id if it's different
            if existing.device_id != device_id:
                existing.device_id = device_id
            # Set time_required to 0 for holidays
            existing.time_required = 0
        else:
            # Create new attendance record for the holiday
            holiday = AttendanceSheet(
                device_id=device_id,
                date=date,
                category=90,  # Holiday
                description=description,
                time_required=0,  # No required time for holidays
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(holiday)
        
        db.commit()
        return {
            "date": date,
            "description": description
        }

    @staticmethod
    def delete_holiday(db: Session, date: date) -> bool:
        """Convert holiday to working day (if applicable)"""
        holiday = db.query(AttendanceSheet).filter(
            AttendanceSheet.date == date,
            AttendanceSheet.category == 90
        ).first()
        
        if not holiday:
            return False
        
        # Get settings to determine working days and daily required minutes
        settings = db.query(Settings).first()
        if not settings:
            return False
        
        # Parse working days
        working_days = []
        if settings.working_days:
            try:
                import json
                working_days = json.loads(settings.working_days)
            except:
                working_days = [0, 1, 2, 3, 4]  # Default Mon-Fri
        
        # Check if the date is a working day
        weekday = date.weekday()
        is_working_day = weekday in working_days
        
        # Determine new category based on day type
        if is_working_day:
            # It's a working day - convert to regular workday
            new_category = 0
            new_time_required = settings.daily_required_minutes
        else:
            # It's a weekend - keep as weekend
            new_category = 1
            new_time_required = 0
        
        # Update the record
        holiday.category = new_category
        holiday.description = None  # Remove holiday description
        holiday.time_required = new_time_required
        holiday.updated_at = datetime.utcnow()
        
        db.commit()
        return True
