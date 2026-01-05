from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from app.models import Settings, AttendanceSheet
import json

class AttendanceService:
    @staticmethod
    def record_heartbeat(db: Session, device_id: str):
        """Record a new heartbeat - now simply increments time_recorded by 1 minute"""
        now = datetime.now()
        today = now.date()
        
        # Get settings to get daily working hours
        settings = AttendanceService.get_settings(db)
        daily_working_hours = settings.daily_working_hours if settings else 8
        
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
                category=0,  # Default to workday
                time_recorded=1,  # Start with 1 minute for this heartbeat
                time_required=AttendanceService.calculate_time_required(0, daily_working_hours)
            )
            db.add(record)
        else:
            # Increment time_recorded by 1 minute for each heartbeat
            record.time_recorded += 1
        
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
        daily_working_hours: float = 8.0
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
        if daily_working_hours is not None:
            settings.daily_working_hours = daily_working_hours
            
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def get_holidays(db: Session, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get holidays and leaves as individual days"""
        # Get all holidays and leaves (categories 90, 11, 10)
        query = db.query(AttendanceSheet).filter(
            AttendanceSheet.category.in_([90, 11, 10])  # Holiday, Leave full day, Leave half day
        )
        
        if start_date:
            query = query.filter(AttendanceSheet.date >= start_date)
        if end_date:
            query = query.filter(AttendanceSheet.date <= end_date)
            
        # Order by date
        results = query.order_by(AttendanceSheet.date.asc()).all()
        
        # Return individual days
        return [
            {
                'date': record.date,
                'category': record.category,
                'description': record.description or ''
            }
            for record in results
        ]

    @staticmethod
    def calculate_time_required(category: int, daily_working_hours: float) -> int:
        """Calculate required time in minutes based on category and daily working hours"""
        daily_required_minutes = int(daily_working_hours * 60)
        
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
    def update_time_required_for_date(db: Session, device_id: str, date: date, daily_working_hours: float):
        """Update time_required for a specific attendance record"""
        record = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == device_id,
            AttendanceSheet.date == date
        ).first()
        
        if record:
            record.time_required = AttendanceService.calculate_time_required(record.category, daily_working_hours)
            db.commit()
    
    @staticmethod
    def update_time_required_for_all(db: Session, device_id: str, daily_working_hours: float, working_days: List[int]):
        """Update time_required for all attendance records for a device"""
        records = db.query(AttendanceSheet).filter(
            AttendanceSheet.device_id == device_id
        ).all()
        
        for record in records:
            record.time_required = AttendanceService.calculate_time_required(record.category, daily_working_hours)
        
        db.commit()
    
    @staticmethod
    def update_time_required_for_date_range(db: Session, device_id: str, start_date: date, end_date: date, 
                                          daily_working_hours: float, working_days: List[int]):
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
                    time_required=AttendanceService.calculate_time_required(category, daily_working_hours)
                )
                db.add(record)
            else:
                # Update existing record
                record.time_required = AttendanceService.calculate_time_required(record.category, daily_working_hours)
            
            current_date += delta
        
        db.commit()
    
    @staticmethod
    def add_holiday_range(db: Session, start_date: date, end_date: date, category: int, description: str) -> Optional[Dict[str, Any]]:
        """Add holidays/leaves for a date range with proper time_required calculation"""
        from datetime import timedelta
        
        # Get current settings to get the device_id and daily_working_hours
        settings = db.query(Settings).first()
        if not settings:
            raise ValueError("No settings found. Please configure settings first.")
        
        device_id = settings.device_id
        daily_working_hours = settings.daily_working_hours
        
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
        
        # Get working days for weekend calculation
        working_days_set = set()
        if settings.working_days:
            # Handle both JSON array format and comma-separated string format
            working_days_str = settings.working_days.strip()
            
            if working_days_str.startswith('[') and working_days_str.endswith(']'):
                # JSON array format: [6, 0, 1, 2, 3]
                try:
                    import json
                    working_days_array = json.loads(working_days_str)
                    working_days_set = set(working_days_array)
                except (json.JSONDecodeError, ValueError):
                    pass
            else:
                # Comma-separated string format: Mon,Tue,Wed,Thu,Fri
                day_mapping = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
                working_days_set = {day_mapping[day] for day in working_days_str.split(',') if day in day_mapping}
        
        added_days = []
        current_date = start_date
        
        while current_date <= end_date:
            # Check if it's a weekend
            day_of_week = current_date.weekday()  # 0=Monday, 6=Sunday
            is_weekend = day_of_week not in working_days_set
            
            # Check if it's already a holiday
            existing_holiday = db.query(AttendanceSheet).filter(
                AttendanceSheet.date == current_date,
                AttendanceSheet.category == 90  # Holiday category
            ).first()
            is_holiday = existing_holiday is not None
            
            # Skip weekends and existing holidays when adding leave
            if (is_weekend or is_holiday) and category in [10, 11]:  # Leave types
                current_date += timedelta(days=1)
                continue
            
            # Auto-generate description for leaves if not provided
            final_description = description
            if not description or not description.strip():
                if category == 11:
                    final_description = "Leave (full day)"
                elif category == 10:
                    final_description = "Leave (half day)"
            
            # Check if there's already an attendance record for this date
            existing = db.query(AttendanceSheet).filter(
                AttendanceSheet.date == current_date
            ).first()
            
            if existing:
                # Only update if the new category has higher priority
                # Holiday (90) > Leave full day (11) > Leave half day (10) > Workday (0) > Weekend (1)
                if category > existing.category or (category == 90 and existing.category != 90):
                    existing.category = category
                    existing.description = final_description
                    # Update device_id if it's different
                    if existing.device_id != device_id:
                        existing.device_id = device_id
                    
                    # Calculate time_required based on category
                    if category == 90:  # Holiday
                        existing.time_required = 0
                    elif category == 11:  # Leave (full day)
                        existing.time_required = 0
                    elif category == 10:  # Leave (half day)
                        existing.time_required = AttendanceService.calculate_time_required(category, daily_working_hours)
                    
                    added_days.append(current_date)
            else:
                # Create new record
                time_required = AttendanceService.calculate_time_required(category, daily_working_hours)
                
                new_record = AttendanceSheet(
                    device_id=device_id,
                    date=current_date,
                    time_recorded=0,
                    category=category,
                    description=final_description,
                    time_required=time_required
                )
                db.add(new_record)
                added_days.append(current_date)
            
            current_date += timedelta(days=1)
        
        db.commit()
        
        # Calculate total days in range and skipped days
        total_days = (end_date - start_date).days + 1
        skipped_days = total_days - len(added_days)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "category": category,
            "description": description,
            "total_days": total_days,
            "added_days": len(added_days),
            "skipped_days": skipped_days,
            "processed_dates": added_days
        }
    
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
                time_required=0  # No required time for holidays
            )
            db.add(holiday)
        
        db.commit()
        return {
            "date": date,
            "description": description
        }

    @staticmethod
    def delete_holiday(db: Session, date: date) -> bool:
        """Delete holiday/leave and convert to working day (if applicable)"""
        # Find any holiday/leave record for this date
        record = db.query(AttendanceSheet).filter(
            AttendanceSheet.date == date,
            AttendanceSheet.category.in_([90, 11, 10])  # Holiday, Leave full day, Leave half day
        ).first()
        
        if not record:
            return False
        
        # Get settings to determine working days
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
            new_category = 0  # Workday
            new_description = None
        else:
            new_category = 1  # Weekend
            new_description = "Weekend"
        
        # Update the record
        record.category = new_category
        record.description = new_description
        record.time_required = AttendanceService.calculate_time_required(new_category, settings.daily_working_hours)
        
        db.commit()
        return True
