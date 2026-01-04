from datetime import date, datetime, timedelta, time
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.services.attendance_service import AttendanceService
from app.models import AttendanceSheet
import json


class StatisticsService:
    
    @staticmethod
    def format_balance(balance_minutes: int, daily_required_minutes: int = 450) -> str:
        """Format balance as days/hours/minutes or hours/minutes"""
        if balance_minutes == 0:
            return "0:00 hours"
        
        # Convert to positive for calculation, keep sign for display
        is_negative = balance_minutes < 0
        abs_minutes = abs(balance_minutes)
        
        # Check if balance exceeds daily required hours
        if abs_minutes > daily_required_minutes:
            # Show as days, hours:minutes
            days = abs_minutes // (24 * 60)
            remaining_minutes = abs_minutes % (24 * 60)
            hours = remaining_minutes // 60
            minutes = remaining_minutes % 60
            
            if days > 0:
                result = f"{days} days and {hours}:{minutes:02d}"
            else:
                result = f"{hours}:{minutes:02d} hours"
        else:
            # Show as hours:minutes
            hours = abs_minutes // 60
            minutes = abs_minutes % 60
            result = f"{hours}:{minutes:02d} hours"
        
        # Add sign back
        if is_negative:
            result = f"-{result}"
        elif balance_minutes > 0:
            result = f"+{result}"
        
        return result
    
    @staticmethod
    def calculate_worked_minutes(check_in: time, check_out: time) -> int:
        """Calculate worked minutes from check-in and check-out times"""
        if not check_in or not check_out:
            return 0
        
        # Convert to minutes from midnight
        check_in_minutes = check_in.hour * 60 + check_in.minute
        check_out_minutes = check_out.hour * 60 + check_out.minute
        
        worked_minutes = check_out_minutes - check_in_minutes
        return max(0, worked_minutes)  # Don't allow negative minutes
    
    @staticmethod
    def get_dashboard_data(db: Session, include_charts: bool = True) -> Dict:
        """Get data for dashboard page using new AttendanceSheet model"""
        # Get settings to determine date range and daily required
        settings = AttendanceService.get_settings_cached(db)
        monthly_data = []
        total_balance = 0
        daily_required = 450  # default
        
        if settings:
            daily_required = settings.daily_required_minutes if settings.daily_required_minutes else 450
            
            # Use date range from settings
            start_date = settings.start_date
            end_date = settings.end_date
            
            if start_date and end_date:
                # Calculate total balance for whole period
                current_date = start_date
                
                while current_date <= end_date:
                    # Get attendance record for this date
                    attendance = db.query(AttendanceSheet).filter(
                        AttendanceSheet.date == current_date
                    ).first()
                    
                    # Calculate worked minutes
                    if attendance and attendance.check_in and attendance.check_out:
                        worked_minutes = StatisticsService.calculate_worked_minutes(
                            attendance.check_in, attendance.check_out
                        )
                    else:
                        worked_minutes = 0
                    
                    # Calculate required minutes
                    weekday = current_date.weekday()
                    working_days = [0, 1, 2, 3, 4]  # Monday-Friday (default)
                    if settings.working_days:
                        try:
                            import json
                            working_days = json.loads(settings.working_days)
                        except:
                            working_days = [0, 1, 2, 3, 4]
                    
                    is_working_day = weekday in working_days
                    is_holiday = attendance and attendance.category == 90  # 90 is holiday category
                    
                    if is_working_day and not is_holiday:
                        required_minutes = daily_required
                    else:
                        required_minutes = 0
                    
                    # Calculate balance
                    balance = worked_minutes - required_minutes
                    total_balance += balance
                    
                    current_date += timedelta(days=1)
                
                # Generate monthly data for the specified date range
                current_date = start_date.replace(day=1)
                
                while current_date <= end_date:
                    # Stop if we've gone beyond the end date
                    if current_date > end_date:
                        break
                    
                    # Calculate month summary
                    month_start = current_date
                    if current_date.month == 12:
                        month_end = date(current_date.year + 1, 1, 1) - timedelta(days=1)
                    else:
                        month_end = date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
                    
                    # Limit to overall end date
                    month_end = min(month_end, end_date)
                    
                    # Get all attendance records for this month
                    month_records = db.query(AttendanceSheet).filter(
                        AttendanceSheet.date >= month_start,
                        AttendanceSheet.date <= month_end
                    ).all()
                    
                    month_worked = 0
                    month_required = 0
                    
                    for record in month_records:
                        # Calculate worked minutes for this record
                        if record.check_in and record.check_out:
                            worked = StatisticsService.calculate_worked_minutes(
                                record.check_in, record.check_out
                            )
                            month_worked += worked
                        
                        # Calculate required minutes for this record
                        weekday = record.date.weekday()
                        is_working_day = weekday in working_days
                        is_holiday = record.category == 90
                        
                        if is_working_day and not is_holiday:
                            month_required += daily_required
                    
                    month_balance = month_worked - month_required
                    
                    monthly_data.append({
                        'year': current_date.year,
                        'month': current_date.month,
                        'month_name': current_date.strftime("%B %Y"),
                        'worked_hours': month_worked / 60,
                        'required_hours': month_required / 60,
                        'balance_hours': month_balance / 60,
                        'balance_formatted': StatisticsService.format_balance(
                            month_balance, daily_required
                        )
                    })
                    
                    # Move to next month
                    if current_date.month == 12:
                        current_date = date(current_date.year + 1, 1, 1)
                    else:
                        current_date = date(current_date.year, current_date.month + 1, 1)
        
        return {
            'total_balance_minutes': total_balance,
            'total_balance_formatted': StatisticsService.format_balance(total_balance, daily_required),
            'monthly_data': monthly_data,
            'has_date_range': bool(settings and settings.start_date and settings.end_date),
            'daily_required_minutes': daily_required
        }
    
    @staticmethod
    def get_corrections_data(db: Session, start_date: date = None, end_date: date = None) -> List[Dict]:
        """Get data for corrections page using batch queries"""
        if not start_date:
            # Default to last 30 days
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
        
        if not end_date:
            end_date = date.today()
        
        # Use optimized batch query method
        date_range_data = AttendanceService.get_date_range_data_batch(db, start_date, end_date)
        
        return date_range_data
    
    @staticmethod
    def format_minutes_to_hours(minutes: int) -> str:
        """Format minutes to hours display"""
        if minutes >= 0:
            hours = minutes // 60
            mins = minutes % 60
            return f"+{hours}h {mins}m"
        else:
            minutes = abs(minutes)
            hours = minutes // 60
            mins = minutes % 60
            return f"-{hours}h {mins}m"
    
    @staticmethod
    def get_chart_data(db: Session, months: int = 12) -> Dict:
        """Get data for Chart.js visualization using batch queries"""
        current_date = date.today()
        chart_data = []
        
        for i in range(months):
            # Calculate month (going backwards from current)
            month_date = current_date.replace(day=1) - timedelta(days=i*30)
            month_date = month_date.replace(day=1)
            
            # Use batch method for better performance
            month_summary = AttendanceService.get_monthly_summary_batch(
                db, month_date.year, month_date.month
            )
            
            chart_data.append({
                'label': f"{month_date.year}-{month_date.month:02d}",
                'worked': month_summary['total_effective_minutes'] / 60,
                'required': month_summary['total_required_minutes'] / 60,
                'balance': month_summary['total_balance_minutes'] / 60,
            })
        
        # Reverse to get chronological order
        chart_data.reverse()
        
        return {
            'labels': [item['label'] for item in chart_data],
            'worked': [item['worked'] for item in chart_data],
            'required': [item['required'] for item in chart_data],
            'balance': [item['balance'] for item in chart_data],
        }
