from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file first, then system environment
load_dotenv()

from app.database import get_db, create_tables, init_default_settings
from app.services.attendance import AttendanceService
from app.services.statistics import StatisticsService

# Initialize FastAPI app
app = FastAPI(title="Time Attendance Tracker", description="Lightweight time attendance and balance tracker")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Security token (read from .env first, then environment, or use default)
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "your-secret-token-here")


# Pydantic models for API
class HeartbeatRequest(BaseModel):
    device_id: str


class SettingsRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    working_days: List[int]
    daily_required_minutes: int


class HolidayRequest(BaseModel):
    date: date
    description: str


class CorrectionRequest(BaseModel):
    date: date
    corrected_minutes: int
    reason: str


# Security dependency
def verify_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    token = auth_header.split(" ")[1]
    if token != BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and default settings"""
    create_tables()
    init_default_settings()


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
    """Record a new heartbeat"""
    AttendanceService.record_heartbeat(db, request.device_id)
    return {"status": "success", "message": "Heartbeat recorded"}


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
        "daily_required_minutes": settings.daily_required_minutes
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
        daily_required_minutes=request.daily_required_minutes
    )
    
    working_days = json.loads(settings.working_days) if settings.working_days else []
    
    return {
        "start_date": settings.start_date,
        "end_date": settings.end_date,
        "working_days": working_days,
        "daily_required_minutes": settings.daily_required_minutes
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


@app.get("/api/corrections")
async def get_corrections(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Get corrections data"""
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format")
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format")
    
    corrections_data = StatisticsService.get_corrections_data(db, start_date_obj, end_date_obj)
    
    return [
        {
            "date": item["date"],
            "effective_minutes": item["effective_minutes"],
            "required_minutes": item["required_minutes"],
            "corrected_minutes": item["corrected_minutes"],
            "correction_reason": item["correction_reason"],
            "is_working_day": item["is_working_day"],
            "is_holiday": item["is_holiday"]
        }
        for item in corrections_data
    ]


@app.post("/api/corrections")
async def add_correction(
    request: CorrectionRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_token)
):
    """Add or update a correction"""
    correction = AttendanceService.add_correction(
        db, request.date, request.corrected_minutes, request.reason
    )
    
    return {
        "date": correction.date,
        "corrected_minutes": correction.corrected_minutes,
        "reason": correction.reason
    }


# Web Pages

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard page"""
    dashboard_data = StatisticsService.get_dashboard_data(db)
    chart_data = StatisticsService.get_chart_data(db)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_balance": dashboard_data["total_balance_hours"],
        "monthly_data": dashboard_data["monthly_data"],
        "chart_labels": json.dumps(chart_data["labels"]),
        "chart_worked": json.dumps(chart_data["worked"]),
        "chart_required": json.dumps(chart_data["required"]),
        "chart_balance": json.dumps(chart_data["balance"]),
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page"""
    settings = AttendanceService.get_settings(db)
    holidays = AttendanceService.get_holidays(db)
    
    working_days = []
    if settings and settings.working_days:
        try:
            working_days = json.loads(settings.working_days)
        except (json.JSONDecodeError, TypeError):
            working_days = [1, 2, 3, 4, 5]  # Default Monday-Friday
    
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "holidays": holidays,
        "working_days": working_days,
        "weekday_names": weekday_names,
    })


@app.post("/settings")
async def update_settings_form(
    request: Request,
    db: Session = Depends(get_db),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    daily_required_hours: Optional[str] = Form("8"),
    monday: Optional[str] = Form(None),
    tuesday: Optional[str] = Form(None),
    wednesday: Optional[str] = Form(None),
    thursday: Optional[str] = Form(None),
    friday: Optional[str] = Form(None),
    saturday: Optional[str] = Form(None),
    sunday: Optional[str] = Form(None),
):
    """Handle settings form submission"""
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
    
    # Parse working days
    working_days = []
    if monday: working_days.append(0)
    if tuesday: working_days.append(1)
    if wednesday: working_days.append(2)
    if thursday: working_days.append(3)
    if friday: working_days.append(4)
    if saturday: working_days.append(5)
    if sunday: working_days.append(6)
    
    # Parse daily required hours
    try:
        daily_required_minutes = int(float(daily_required_hours) * 60)
    except (ValueError, TypeError):
        daily_required_minutes = 8 * 60  # Default 8 hours
    
    # Update settings
    AttendanceService.update_settings(
        db,
        start_date=start_date_obj,
        end_date=end_date_obj,
        working_days=json.dumps(working_days),
        daily_required_minutes=daily_required_minutes
    )
    
    return RedirectResponse(url="/settings", status_code=303)


@app.post("/holidays")
async def add_holiday_form(
    request: Request,
    db: Session = Depends(get_db),
    holiday_date: str = Form(...),
    description: str = Form(...),
):
    """Handle holiday form submission"""
    try:
        date_obj = datetime.strptime(holiday_date, "%Y-%m-%d").date()
    except ValueError:
        # Handle error - for now, redirect back
        return RedirectResponse(url="/settings", status_code=303)
    
    AttendanceService.add_holiday(db, date_obj, description)
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


@app.get("/corrections", response_class=HTMLResponse)
async def corrections_page(
    request: Request,
    db: Session = Depends(get_db),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Corrections page"""
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    # Default to last 30 days if no dates provided
    if not start_date_obj and not end_date_obj:
        end_date_obj = date.today()
        start_date_obj = end_date_obj - timedelta(days=30)
    
    corrections_data = StatisticsService.get_corrections_data(db, start_date_obj, end_date_obj)
    
    return templates.TemplateResponse("corrections.html", {
        "request": request,
        "corrections_data": corrections_data,
        "start_date": start_date_obj,
        "end_date": end_date_obj,
    })


@app.post("/corrections")
async def update_correction_form(
    request: Request,
    db: Session = Depends(get_db),
    correction_date: str = Form(...),
    corrected_minutes: str = Form(...),
    reason: str = Form(""),
):
    """Handle correction form submission"""
    try:
        date_obj = datetime.strptime(correction_date, "%Y-%m-%d").date()
        minutes = int(corrected_minutes)
    except ValueError:
        return RedirectResponse(url="/corrections", status_code=303)
    
    AttendanceService.add_correction(db, date_obj, minutes, reason)
    return RedirectResponse(url="/corrections", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
