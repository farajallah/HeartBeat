# HeartBeat Tracker - Render.com Deployment

This project is now configured for deployment on Render.com with the following changes:

## Files Added/Modified

### 1. `render.yaml` - Render Configuration
- Configures web service with Python 3.11
- Sets up PostgreSQL database
- Defines environment variables
- Configures health check endpoint

### 2. `requirements.txt` - Updated Dependencies
- Added `psycopg2-binary==2.9.9` for PostgreSQL support

### 3. `app/database.py` - Database Configuration
- Updated to support both SQLite (local) and PostgreSQL (production)
- Uses `DATABASE_URL` environment variable to determine database type

### 4. `.env.example` - Environment Variables Template
- Template for required environment variables
- Includes database URL configuration options

### 5. `run.py` - Production Configuration
- Changed default `RELOAD` to `false` for production
- Maintains compatibility with local development

### 6. `app/main.py` - Health Check Endpoint
- Added `/health` endpoint for Render monitoring

## Deployment Steps

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Configure for Render.com deployment"
   git push origin main
   ```

2. **Deploy on Render**
   - Go to render.com
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` file
   - The service will be deployed with PostgreSQL database

3. **Environment Variables**
   - Render will automatically set `DATABASE_URL` for PostgreSQL
   - `BEARER_TOKEN` will be auto-generated
   - Other variables are configured in `render.yaml`

## Local Development

For local development with SQLite:
```bash
cp .env.example .env
# Edit .env to use SQLite DATABASE_URL
python run.py
```

## Production URLs

After deployment, your app will be available at:
- Main App: `https://your-app-name.onrender.com`
- Dashboard: `https://your-app-name.onrender.com/dashboard`
- Health Check: `https://your-app-name.onrender.com/health`

## Database Migration

The app automatically creates tables on startup. The database configuration handles both SQLite and PostgreSQL seamlessly.
