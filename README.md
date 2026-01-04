# HeartBeat - Time Attendance & Balance Tracker

A simple, deterministic time attendance system with local heartbeat agent and web dashboard.

## Features

- **Local heartbeat agent** that tracks check-in/check-out times
- **FastAPI web server** with SQLite database
- **Clean web dashboard** with balance overview and monthly summaries
- **Settings management** for working days, holidays, and daily requirements
- **Intelligent balance calculation** based on `time_required` and actual work time
- **Holiday/Leave management** with automatic time calculation
- **Minimal dependencies** and simple deployment

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your BEARER_TOKEN
```

### 3. Start the Server

```bash
python run.py
```

The server will be available at `http://localhost:8888`

### 4. Set Up Heartbeat Agent

The heartbeat agent should be run via OS scheduler every minute:

#### Linux/macOS (cron)

```bash
# Edit crontab
crontab -e

# Add line to run every minute
* * * * * cd /path/to/HeartBeat && python app/agent/heartbeat.py
```

#### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" and repeat every 1 minute
4. Action: Start program
   - Program: `python`
   - Arguments: `app\agent\heartbeat.py`
   - Start in: `path\to\HeartBeat`

## Architecture

### Database Schema

- **attendance_sheet**: Main attendance records with check-in/out times
- **settings**: System configuration (working days, daily requirements)
- **holiday**: Holiday definitions

### Core Features

1. **Smart Time Calculation**: Uses `time_required` column for accurate balance
2. **Category-Based Logic**: Workdays, weekends, holidays, leaves handled automatically
3. **Preserved Data**: Settings updates don't affect existing check-in/out records
4. **Clean Balance**: Only shows balance in dashboard, detailed data in monthly view

### API Endpoints

- `POST /api/heartbeat` - Record heartbeat (requires auth)
- `GET/POST /api/settings` - Manage settings
- `GET/POST/DELETE /api/holidays` - Manage holidays

### Web Pages

- `/dashboard` - Main dashboard with balance and monthly overview
- `/settings` - Configure working days, holidays, and requirements

## Usage

### Dashboard

- **Upper Section**: Shows current balance only (green/orange based on status)
- **Lower Section**: Monthly summaries with detailed breakdown
- **Balance Calculation**: `balance = (check_out - check_in) - time_required`

### Settings

- Set reporting period (start/end dates)
- Configure working days (Mon-Fri by default)
- Set daily required hours (e.g., 7.5 hours = 450 minutes)
- Add/remove holidays (automatically sets `time_required = 0`)
- **Important**: Settings updates preserve existing check-in/out data

### Time Categories

- **Category 0**: Workday → `time_required = daily_required_minutes`
- **Category 1**: Weekend → `time_required = 0`
- **Category 10**: Half-day leave → `time_required = daily_required_minutes // 2`
- **Category 11**: Full-day leave → `time_required = 0`
- **Category 90**: Holiday → `time_required = 0`

## Development

### Project Structure

```
app/
 ├── main.py              # FastAPI application
 ├── database.py          # Database connection and setup
 ├── models.py            # SQLAlchemy models
 ├── services/
 │    └── attendance_service.py   # Attendance calculation logic
 ├── templates/           # Jinja2 HTML templates
 ├── static/             # CSS and JavaScript
 └── agent/
      └── heartbeat.py    # Local heartbeat agent
```

### Testing

```bash
# Test heartbeat agent
python app/agent/heartbeat.py --once

# Test database operations
python -c "from app.database import create_tables; create_tables()"
```

### Database

The system uses SQLite with a single file `attendance.db`. Database is created automatically on first run.

## Security

- Static Bearer token authentication for API endpoints
- Token configured via `BEARER_TOKEN` environment variable
- Web interface doesn't require authentication (local use assumed)

## Recent Improvements

### Balance Calculation Overhaul
- Simplified to use only `time_required` and check-in/out difference
- Removed complex category-based calculations from dashboard
- Consistent color scheme (green for positive, orange for negative)

### Settings Preservation
- Settings updates no longer overwrite existing attendance data
- Only `time_required` is recalculated when settings change
- Check-in/out times and categories are preserved

### Database Constraints
- Added `time_required` column with non-negative constraint
- Fixed check-in/check-out constraint violations
- Proper handling of same-time check-in/check-out scenarios

## Troubleshooting

### Agent Not Working

1. Check `BEARER_TOKEN` is set correctly
2. Verify server is running at configured URL
3. Test manually: `python app/agent/heartbeat.py --once`

### Database Issues

1. Delete `attendance.db` to reset
2. Restart server to recreate tables

### Performance

- System designed for single-user local use
- SQLite handles expected load easily
- Heartbeats are lightweight (1 record per minute)

## License

MIT License - feel free to modify and distribute.
