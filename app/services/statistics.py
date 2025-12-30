from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.services.attendance import AttendanceService


class StatisticsService:
    
    @staticmethod
    def get_dashboard_data(db: Session) -> Dict:
        """Get data for dashboard page"""
        # Get total balance
        total_balance = AttendanceService.get_total_balance(db)
        
        # Get last 12 months of data
        current_date = date.today()
        monthly_data = []
        
        for i in range(12):
            # Calculate month (going backwards from current)
            month_date = current_date.replace(day=1) - timedelta(days=i*30)
            month_date = month_date.replace(day=1)
            
            month_summary = AttendanceService.get_monthly_summary(
                db, month_date.year, month_date.month
            )
            
            monthly_data.append({
                'year': month_date.year,
                'month': month_date.month,
                'worked_hours': month_summary['total_effective_minutes'] / 60,
                'required_hours': month_summary['total_required_minutes'] / 60,
                'balance_hours': month_summary['total_balance_minutes'] / 60,
            })
        
        # Reverse to get chronological order
        monthly_data.reverse()
        
        return {
            'total_balance_hours': total_balance / 60,
            'monthly_data': monthly_data
        }
    
    @staticmethod
    def get_corrections_data(db: Session, start_date: date = None, end_date: date = None) -> List[Dict]:
        """Get data for corrections page"""
        if not start_date:
            # Default to last 30 days
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
        
        if not end_date:
            end_date = date.today()
        
        # Get date range data
        date_range_data = AttendanceService.get_date_range_data(db, start_date, end_date)
        
        # Add correction info
        from app.models import Correction
        corrections = {c.date: c for c in db.query(Correction).filter(
            Correction.date >= start_date,
            Correction.date <= end_date
        ).all()}
        
        for day_data in date_range_data:
            correction = corrections.get(day_data['date'])
            if correction:
                day_data['corrected_minutes'] = correction.corrected_minutes
                day_data['correction_reason'] = correction.reason
            else:
                day_data['corrected_minutes'] = None
                day_data['correction_reason'] = None
        
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
        """Get data for Chart.js visualization"""
        current_date = date.today()
        chart_data = []
        
        for i in range(months):
            # Calculate month (going backwards from current)
            month_date = current_date.replace(day=1) - timedelta(days=i*30)
            month_date = month_date.replace(day=1)
            
            month_summary = AttendanceService.get_monthly_summary(
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
