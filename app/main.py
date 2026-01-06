from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file first, then system environment
load_dotenv()

from app.database import get_db, create_tables, init_default_settings, initialize_attendance_records
from app.models import Settings, AttendanceSheet
from app.services.attendance_service import AttendanceService

# Request Models
class HeartbeatRequest(BaseModel):
    """Pydantic model for heartbeat request data"""
    device_id: str
    timezone: Optional[str] = None
    timestamp: Optional[datetime] = None


class SettingsRequest(BaseModel):
    """Pydantic model for settings update request data"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    working_days: List[int]
    daily_working_hours: float = 8.0


class HolidayRequest(BaseModel):
    """Pydantic model for holiday request data"""
    date: date
    description: str

# Initialize FastAPI app
app = FastAPI(title="HeartBeat Tracker", description="Simple time attendance tracker")

# Security
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the API token from the Authorization header."""
    token = credentials.credentials
    expected_token = os.getenv("BEARER_TOKEN", "your-secret-token")
    
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

# Mount static files (only if directory exists)
if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Helper functions
def get_working_days_set(working_days_str: str) -> set:
    """Convert working days string to a set of day numbers"""
    if not working_days_str:
        return set()
    
    # Try to parse as JSON array first (e.g., "[0,1,2,3,4]")
    try:
        import json
        parsed = json.loads(working_days_str)
        if isinstance(parsed, list):
            return set(parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fall back to comma-separated format (e.g., "Mon,Tue,Wed")
    return set(day.strip() for day in working_days_str.split(','))

def format_minutes(minutes: int) -> str:
    """Convert minutes to HH:MM format"""
    if minutes is None:
        return "00:00"
    sign = ""
    if minutes < 0:
        sign = "-"
        minutes = abs(minutes)
    hours = minutes // 60
    mins = minutes % 60
    return f"{sign}{hours:02d}:{mins:02d}"

def format_balance_minutes(minutes: int, daily_required_minutes: int) -> str:
    """Convert minutes to days:hours:minutes format where 1 day = working hours"""
    if minutes is None or daily_required_minutes is None or daily_required_minutes == 0:
        return "0d 00:00"
    
    sign = ""
    if minutes < 0:
        sign = "-"
        minutes = abs(minutes)
    
    # Convert working hours to minutes for calculation
    working_hours_per_day = daily_required_minutes / 60
    
    # Calculate days, hours, and minutes
    days = int(minutes // int(daily_required_minutes))
    remaining_minutes = minutes % int(daily_required_minutes)
    hours = int(remaining_minutes // 60)
    mins = remaining_minutes % 60
    
    # Format based on the value
    if days > 0:
        if hours > 0 or mins > 0:
            return f"{sign}{days}d {hours:02d}:{mins:02d}"
        else:
            return f"{sign}{days}d"
    elif hours > 0:
        return f"{sign}{hours:02d}:{mins:02d}"
    else:
        return f"{sign}{mins:02d}m"

def calculate_balance(recorded: int, required: int) -> int:
    """Calculate balance (recorded - required)"""
    return recorded - required if recorded is not None and required is not None else 0


def get_weekday_name(weekday: int) -> str:
    """Get weekday name from weekday number (0=Monday, 6=Sunday)"""
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return weekdays[weekday] if 0 <= weekday < 7 else ""


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and default settings on startup"""
    create_tables()
    init_default_settings()
    
    # Ensure all attendance records have time_required populated
    from app.database import SessionLocal, ensure_time_required_populated
    db = SessionLocal()
    try:
        ensure_time_required_populated(db)
    finally:
        db.close()

def get_monthly_summaries(db: Session, start_date: date, end_date: date, settings: Settings):
    """Calculate monthly summaries for the calendar view"""
    from datetime import timedelta
    from app.services.attendance_service import AttendanceService
    
    monthly_data = []
    current_month = start_date.replace(day=1)
    today = date.today()
    
    while current_month <= end_date:
        # Determine if this is a future month
        is_future_month = current_month > date(today.year, today.month, 1)
        is_current_month = current_month == date(today.year, today.month, 1)
        
        # Get first and last day of the month
        first_day = current_month.replace(day=1)
        if current_month.month == 12:
            next_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            next_month = current_month.replace(month=current_month.month + 1)
        last_day = next_month - timedelta(days=1)
        
        # For future months, show grey with dashes
        if is_future_month:
            monthly_data.append({
                "month": current_month.strftime('%Y-%m'),
                "month_name": current_month.strftime('%B %Y'),
                "recorded": 0,
                "required": 0,
                "recorded_formatted": "-",
                "required_formatted": "-",
                "balance": 0,
                "balance_formatted": "-",
                "is_complete": True,
                "is_future": True,
                "daily_data": []
            })
        else:
            # Get all records for this month
            records = db.query(AttendanceSheet).filter(
                AttendanceSheet.date.between(first_day, last_day)
            ).all()
            
            # Get working days for this month
            working_days_set = set()
            if settings.working_days:
                working_days_str = settings.working_days.strip()
                if working_days_str.startswith('[') and working_days_str.endswith(']'):
                    try:
                        import json
                        working_days_array = json.loads(working_days_str)
                        working_days_set = set(working_days_array)
                    except (json.JSONDecodeError, ValueError):
                        pass
                else:
                    day_mapping = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
                    working_days_set = {day_mapping[day] for day in working_days_str.split(',') if day in day_mapping}
            
            # Generate daily data for calendar
            daily_data = []
            total_required = 0
            total_recorded = 0
            
            current_day = first_day
            while current_day <= last_day:
                day_of_week = current_day.weekday()
                is_weekend = day_of_week not in working_days_set
                is_today = current_day == today
                is_future = current_day > today
                
                # For current month, only process days up to today for calculations
                if is_current_month and is_future:
                    # Add future days in current month but make them look like future months
                    day_record = None
                    for record in records:
                        if record.date == current_day:
                            day_record = record
                            break
                    
                    # Determine day type and color for future days (grey like future months)
                    if day_record:
                        category = day_record.category
                        if category == 90:  # Holiday
                            color_class = "bg-gray-400"
                            day_type = "holiday"
                        elif category == 11:  # Leave full day
                            color_class = "bg-gray-300"
                            day_type = "leave_full"
                        elif category == 10:  # Leave half day
                            color_class = "bg-gray-200"
                            day_type = "leave_half"
                        elif category == 1:  # Weekend
                            color_class = "bg-gray-500"
                            day_type = "weekend"
                        else:  # Workday
                            color_class = "bg-white"
                            day_type = "workday"
                    else:
                        # No record - determine based on date
                        if is_weekend:
                            color_class = "bg-gray-500"
                            day_type = "weekend"
                        else:
                            color_class = "bg-white"
                            day_type = "workday"
                    
                    daily_data.append({
                        "date": current_day,
                        "day": current_day.day,
                        "color_class": color_class,
                        "day_type": day_type,
                        "time_required": 0,
                        "time_recorded": 0,
                        "balance": 0,
                        "is_today": is_today,
                        "is_future": is_future
                    })
                else:
                    # Process past days and today for calculations
                    # Find record for this day
                    day_record = None
                    for record in records:
                        if record.date == current_day:
                            day_record = record
                            break
                    
                    # Determine day type and color
                    if day_record:
                        category = day_record.category
                        time_required = day_record.time_required
                        time_recorded = day_record.time_recorded
                        balance = time_recorded - time_required
                        
                        if category == 90:  # Holiday
                            color_class = "bg-gray-400"
                            day_type = "holiday"
                        elif category == 11:  # Leave full day
                            color_class = "bg-gray-300"
                            day_type = "leave_full"
                        elif category == 10:  # Leave half day
                            color_class = "bg-gray-200"
                            day_type = "leave_half"
                        elif category == 1:  # Weekend
                            color_class = "bg-gray-500"
                            day_type = "weekend"
                        else:  # Workday
                            if is_today:
                                color_class = "bg-blue-500"
                            elif is_future:
                                color_class = "bg-white"
                            elif balance >= 0:  # Changed from balance > 0 to balance >= 0
                                color_class = "bg-green-500"
                            elif balance < 0:
                                color_class = "bg-orange-500"
                            else:
                                color_class = "bg-white"
                            day_type = "workday"
                    else:
                        # No record - determine based on date
                        if is_weekend:
                            color_class = "bg-gray-500"
                            day_type = "weekend"
                            time_required = 0
                        else:
                            time_required = AttendanceService.calculate_time_required(0, settings.daily_working_hours)
                            if is_today:
                                color_class = "bg-blue-500"
                            elif is_future:
                                color_class = "bg-white"
                            else:
                                color_class = "bg-white"
                            day_type = "workday"
                        
                        time_recorded = 0
                        balance = time_recorded - time_required
                    
                    daily_data.append({
                        "date": current_day,
                        "day": current_day.day,
                        "color_class": color_class,
                        "day_type": day_type,
                        "time_required": time_required,
                        "time_recorded": time_recorded,
                        "balance": balance,
                        "is_today": is_today,
                        "is_future": is_future
                    })
                    
                    total_required += time_required
                    total_recorded += time_recorded
                
                current_day += timedelta(days=1)
            
            # Calculate monthly balance
            balance = total_recorded - total_required
            daily_minutes = int(settings.daily_working_hours * 60)
            
            monthly_data.append({
                "month": current_month.strftime('%Y-%m'),
                "month_name": current_month.strftime('%B %Y'),
                "recorded": total_recorded,
                "required": total_required,
                "recorded_formatted": format_balance_minutes(total_recorded, daily_minutes),
                "required_formatted": format_balance_minutes(total_required, daily_minutes),
                "balance": balance,
                "balance_formatted": format_balance_minutes(balance, daily_minutes),
                "is_complete": total_recorded >= total_required if total_required > 0 else True,
                "is_future": False,
                "daily_data": daily_data
            })
        
        # Move to next month
        if current_month.month == 12:
            current_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            current_month = current_month.replace(month=current_month.month + 1)
    
    return monthly_data

# Web Pages
@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard page with attendance summary"""
    # Get settings
    settings = db.query(Settings).first()
    if not settings:
        init_default_settings()
        settings = db.query(Settings).first()
    
    # Get current date range from settings or use current month
    today = date.today()
    start_date = settings.start_date or today.replace(day=1)
    # For balance calculation, limit to today (exclude future dates)
    balance_end_date = min(settings.end_date or (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), today)
    # For monthly display, show all months up to settings end date (including future)
    display_end_date = settings.end_date or (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    
    # Calculate statistics
    working_days = get_working_days_set(settings.working_days)
    
    # Calculate total required minutes for period up to today (balance calculation)
    # Get attendance records for balance calculation period (up to today)
    balance_records = db.query(AttendanceSheet).filter(
        AttendanceSheet.device_id == settings.device_id,
        AttendanceSheet.date.between(start_date, balance_end_date)
    ).all()
    
    # Create a dictionary of records by date for quick lookup
    balance_records_by_date = {record.date: record for record in balance_records}
    
    # Calculate total required minutes from time_required column
    total_required = 0
    total_recorded = 0
    
    for record in balance_records:
        # Use time_required from the record directly
        total_required += record.time_required
        
        # Use time_recorded directly (already in minutes)
        total_recorded += record.time_recorded
    
    # Calculate balance
    balance = total_recorded - total_required
    
    # Format for display
    stats = {
        "period": f"{start_date.strftime('%b %d, %Y')} to {display_end_date.strftime('%b %d, %Y')}",
        "balance": format_balance_minutes(balance, int(settings.daily_working_hours * 60)),
        "balance_class": "text-green-600" if balance >= 0 else "text-orange-500"
    }
    
    # Get monthly summaries for calendar view (show all months up to settings end date)
    monthly_summaries = get_monthly_summaries(db, start_date, display_end_date, settings)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "monthly_summaries": monthly_summaries,
        "settings": settings
    })


# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {"status": "healthy", "service": "heartbeat-tracker"}

@app.post("/api/heartbeat")
async def record_heartbeat(
    request: HeartbeatRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Record a new heartbeat - now simply increments time_recorded by 1 minute"""
    # Use the simplified attendance service
    record = AttendanceService.record_heartbeat(db, request.device_id)
    
    return {"status": "success", "message": "Heartbeat recorded", "action": "time_recorded"}


@app.get("/api/settings")
async def get_settings(
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Get current settings"""
    settings = AttendanceService.get_settings(db)
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    
    working_days = json.loads(settings.working_days) if settings.working_days else []
    
    return {
        "start_date": settings.start_date,
        "end_date": settings.end_date,
        "working_days": working_days,
        "daily_working_hours": settings.daily_working_hours,
        "daily_required_minutes": settings.daily_working_hours * 60
    }


@app.post("/api/settings")
async def update_settings(
    request: SettingsRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Update settings"""
    settings = AttendanceService.update_settings(
        db,
        start_date=request.start_date,
        end_date=request.end_date,
        working_days=json.dumps(request.working_days),
        daily_working_hours=request.daily_working_hours
    )
    
    # Recalculate time_required for all attendance records
    working_days = json.loads(settings.working_days) if settings.working_days else []
    AttendanceService.update_time_required_for_all(
        db, 
        settings.device_id, 
        settings.daily_working_hours,
        working_days
    )
    
    return {
        "start_date": settings.start_date,
        "end_date": settings.end_date,
        "working_days": working_days,
        "daily_working_hours": settings.daily_working_hours,
        "daily_required_minutes": settings.daily_working_hours * 60
    }


@app.get("/api/holidays")
async def get_holidays(
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Get all holidays"""
    holidays = AttendanceService.get_holidays(db)
    return [
        {
            "date": holiday.date,
            "description": holiday.description
        }
        for holiday in holidays
    ]


@app.post("/api/holidays")
async def add_holiday(
    request: HolidayRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Add a new holiday"""
    holiday = AttendanceService.add_holiday(db, request.date, request.description)
    return {
        "date": holiday.date,
        "description": holiday.description
    }


@app.delete("/api/holidays/{holiday_date}")
async def delete_holiday(
    holiday_date: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Delete a holiday"""
    try:
        date_obj = datetime.strptime(holiday_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    success = AttendanceService.delete_holiday(db, date_obj)
    if not success:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    return {"status": "success", "message": "Holiday deleted"}


# Web Pages

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/dashboard")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page"""
    settings = AttendanceService.get_settings_cached(db)
    holidays = AttendanceService.get_holidays(db)
    
    working_days = []
    if settings and settings.working_days:
        try:
            working_days = json.loads(settings.working_days)
        except (json.JSONDecodeError, TypeError):
            working_days = [0, 1, 2, 3, 4]  # Default Mon-Fri (Sat & Sun are weekends)
    
    # Week starting from Monday with correct Python weekday numbers
    weekday_names = [
        {"name": "Saturday", "weekday": 5},
        {"name": "Sunday", "weekday": 6},
        {"name": "Monday", "weekday": 0},
        {"name": "Tuesday", "weekday": 1},
        {"name": "Wednesday", "weekday": 2},
        {"name": "Thursday", "weekday": 3},
        {"name": "Friday", "weekday": 4},
    ]
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "holidays": holidays,
        "working_days": working_days,
        "weekday_names": weekday_names,
        "today": date.today().strftime("%Y-%m-%d"),
    })


@app.post("/settings")
async def update_settings_form(
    request: Request,
    db: Session = Depends(get_db),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    daily_working_hours: Optional[str] = Form("8"),
    saturday: Optional[str] = Form(None),
    sunday: Optional[str] = Form(None),
    monday: Optional[str] = Form(None),
    tuesday: Optional[str] = Form(None),
    wednesday: Optional[str] = Form(None),
    thursday: Optional[str] = Form(None),
    friday: Optional[str] = Form(None),
):
    """Handle settings form submission and initialize attendance records"""
    # Parse dates
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass  # Keep as None if invalid
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            pass  # Keep as None if invalid
    
    # Parse working days (correct Python weekday numbers: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
    working_days = []
    if saturday: working_days.append(5)
    if sunday: working_days.append(6)
    if monday: working_days.append(0)
    if tuesday: working_days.append(1)
    if wednesday: working_days.append(2)
    if thursday: working_days.append(3)
    if friday: working_days.append(4)
    
    # Parse daily working hours
    try:
        daily_working_hours_float = float(daily_working_hours)
    except (ValueError, TypeError):
        daily_working_hours_float = 8.0  # Default 8 hours
    
    # Get current settings to check if dates are being updated
    current_settings = AttendanceService.get_settings(db)
    dates_changed = (current_settings and 
                    (current_settings.start_date != start_date_obj or 
                     current_settings.end_date != end_date_obj or
                     set(json.loads(current_settings.working_days)) != set(working_days)))
    
    # Update settings
    AttendanceService.update_settings(
        db,
        start_date=start_date_obj,
        end_date=end_date_obj,
        working_days=json.dumps(working_days),
        daily_working_hours=daily_working_hours_float
    )
    
    # Update attendance records after settings are saved
    if start_date_obj and end_date_obj:
        # Clean up any orphaned records (records with device_id not in settings)
        if current_settings:
            # Delete records with device_id that doesn't exist in settings
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
        
        # Get all existing records in the period
        existing_records = db.query(AttendanceSheet).filter(
            AttendanceSheet.date.between(start_date_obj, end_date_obj)
        ).all()
        
        # Create a dictionary of existing records by date for quick lookup
        existing_by_date = {record.date: record for record in existing_records}
        
        # Get all holidays for the period
        holidays_list = AttendanceService.get_holidays(db, start_date_obj, end_date_obj)
        # Convert to dictionary for easy lookup
        holidays = {h['date']: h for h in holidays_list}
        
        # Prepare batch operations
        records_to_add = []
        records_to_update = []
        current_date = start_date_obj
        device_id = current_settings.device_id if current_settings else "default"
        
        while current_date <= end_date_obj:
            day_of_week = current_date.weekday()
            
            # Determine category based on priority: Holiday > Weekend > Workday
            if current_date in holidays:
                holiday_data = holidays[current_date]
                category = holiday_data['category']  # Use actual category (90, 11, or 10)
                description = holiday_data.get('description', 'Holiday')
            elif day_of_week not in working_days:
                category = 1  # Weekend
                description = None
            else:
                category = 0  # Workday
                description = None
            
            if current_date in existing_by_date:
                # Update existing record - preserve category, time_recorded
                existing_record = existing_by_date[current_date]
                existing_record.device_id = device_id
                # Only update time_required based on existing category
                existing_record.time_required = AttendanceService.calculate_time_required(existing_record.category, daily_working_hours_float)
                # Add to update list as dictionary (only update time_required)
                records_to_update.append({
                    'id': existing_record.id,
                    'device_id': device_id,
                    'time_required': existing_record.time_required
                })
            else:
                # Create new record
                records_to_add.append({
                    "date": current_date,
                    "category": category,
                    "device_id": device_id,
                    "description": description,
                    "time_required": AttendanceService.calculate_time_required(category, daily_working_hours_float)
                })
            
            current_date += timedelta(days=1)
        
        # Perform batch operations
        try:
            # Bulk insert new records
            if records_to_add:
                db.bulk_insert_mappings(AttendanceSheet, records_to_add)
            
            # Bulk update existing records
            if records_to_update:
                db.bulk_update_mappings(AttendanceSheet, records_to_update)
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error updating attendance records: {e}")
            # Try one by one if batch operations fail
            for record in records_to_add:
                try:
                    db.add(AttendanceSheet(**record))
                    db.commit()
                except Exception as e2:
                    db.rollback()
                    print(f"Failed to insert record for {record['date']}: {e2}")
            
            for record in records_to_update:
                try:
                    db.merge(record)
                    db.commit()
                except Exception as e2:
                    db.rollback()
                    print(f"Failed to update record for {record.date}: {e2}")
    
    return RedirectResponse(url="/settings", status_code=303)

# ... (rest of the code remains the same)
@app.post("/holidays")
async def add_holiday_form(
    request: Request,
    db: Session = Depends(get_db),
    type: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    description: str = Form(""),
):
    """Handle holiday/leave form submission"""
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        # Validate date range
        if end_date_obj < start_date_obj:
            return RedirectResponse(url="/settings", status_code=303)
        
        # Validate description requirement for holidays
        if type == 90 and not description.strip():
            return RedirectResponse(url="/settings", status_code=303)
        
        AttendanceService.add_holiday_range(db, start_date_obj, end_date_obj, type, description)
        return RedirectResponse(url="/settings", status_code=303)
    except ValueError as e:
        # Handle error - for now, redirect back
        return RedirectResponse(url="/settings", status_code=303)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url="/settings", status_code=303)


@app.post("/holidays/{holiday_date}/delete")
async def delete_holiday_form(
    holiday_date: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle holiday deletion"""
    try:
        date_obj = datetime.strptime(holiday_date, "%Y-%m-%d").date()
        AttendanceService.delete_holiday(db, date_obj)
    except ValueError:
        pass  # Ignore invalid dates
    
    return RedirectResponse(url="/settings", status_code=303)


# Initialize database on startup
create_tables()
init_default_settings()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
