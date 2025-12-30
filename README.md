# Lightweight Time Attendance & Balance Tracker

A simple, deterministic time attendance system with local heartbeat agent and web dashboard.

## Features

- **Local heartbeat agent** that logs work time every minute
- **FastAPI web server** with SQLite database
- **Web dashboard** with charts and statistics
- **Settings management** for working days and holidays
- **Correction system** for manual adjustments
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
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`

### 4. Set Up Heartbeat Agent

The heartbeat agent should be run via OS scheduler every minute:

#### Linux/macOS (cron)

```bash
# Edit crontab
crontab -e

# Add line to run every minute
* * * * * cd /path/to/heartbeat && python app/agent/heartbeat.py
```

#### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" and repeat every 1 minute
4. Action: Start program
   - Program: `python`
   - Arguments: `app\agent\heartbeat.py`
   - Start in: `w:\heartbeat`

## Architecture

### Database Schema

- **heartbeat**: Raw heartbeat records (immutable)
- **daily_attendance**: Cached daily minutes (derived)
- **correction**: Manual corrections (override recorded)
- **settings**: System configuration
- **holiday**: Holiday definitions

### Core Rules

1. **All recorded minutes are valid** - No working hour restrictions
2. **Raw heartbeats are immutable** - Never modified or deleted
3. **Corrections override derived values** - Don't alter raw data
4. **Expected minutes are policy-based only** - For balance calculation

### API Endpoints

- `POST /api/heartbeat` - Record heartbeat (requires auth)
- `GET/POST /api/settings` - Manage settings
- `GET/POST/DELETE /api/holidays` - Manage holidays
- `GET/POST /api/corrections` - Manage corrections

### Web Pages

- `/dashboard` - Main dashboard with charts and balance
- `/settings` - Configure working days, holidays, and requirements
- `/corrections` - View and edit daily corrections

## Usage

### Dashboard

View total balance, monthly summaries, and attendance charts.

### Settings

- Set reporting period (start/end dates)
- Configure working days (checkboxes)
- Set daily required hours
- Add/remove holidays

### Corrections

- View recorded vs required minutes per day
- Add corrections to override recorded attendance
- Filter by date range

## Development

### Project Structure

```
app/
 ├── main.py              # FastAPI application
 ├── database.py          # Database connection and setup
 ├── models.py            # SQLAlchemy models
 ├── services/
 │    ├── attendance.py   # Attendance calculation logic
 │    └── statistics.py   # Statistics and chart data
 ├── templates/           # Jinja2 HTML templates
 ├── static/             # CSS and JavaScript
 └── agent/
      └── heartbeat.py    # Local heartbeat agent
```

### Running Tests

```bash
# Test heartbeat agent
python app/agent/heartbeat.py --test

# Test connection
python app/agent/heartbeat.py --test
```

### Database

The system uses SQLite with a single file `attendance.db`. Database is created automatically on first run.

## Security

- Static Bearer token authentication for API endpoints
- Token configured via `BEARER_TOKEN` environment variable
- Web interface doesn't require authentication (local use assumed)

## Troubleshooting

### Agent Not Working

1. Check `BEARER_TOKEN` is set correctly
2. Verify server is running at configured URL
3. Check agent logs: `~/.heartbeat_agent.log`

### Database Issues

1. Delete `attendance.db` to reset
2. Restart server to recreate tables

### Performance

- System designed for single-user local use
- SQLite handles expected load easily
- Heartbeats are lightweight (1 record per minute)

## License

MIT License - feel free to modify and distribute.
