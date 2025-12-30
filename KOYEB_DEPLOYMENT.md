# HeartBeat Tracker - Koyeb.com Deployment

This project is now configured for deployment on Koyeb.com with Docker containerization.

## Files Added/Modified

### 1. `Dockerfile` - Container Configuration
- Python 3.11 slim base image
- Multi-stage build for optimization
- Health check endpoint
- Non-root user security
- Proper port exposure

### 2. `koyeb.yaml` - Koyeb Configuration
- Web service configuration
- PostgreSQL database setup
- Environment variables with Koyeb syntax
- Health check configuration
- Routing setup

### 3. `.dockerignore` - Docker Build Optimization
- Excludes unnecessary files from Docker build
- Reduces image size and build time

### 4. `.env.koyeb` - Koyeb Environment Template
- Koyeb-specific environment variables
- Database URL configuration
- Security token setup

## Deployment Steps

### Option 1: Using Koyeb CLI
```bash
# Install Koyeb CLI
curl -s https://get.koyeb.com | sh

# Login to Koyeb
koyeb login

# Deploy from GitHub
koyeb app create heartbeat-tracker \
  --git-url=https://github.com/farajallah/HeartBeat.git \
  --git-branch=main \
  --build-context=. \
  --dockerfile=Dockerfile \
  --ports=8000:http \
  --env=HOST=0.0.0.0 \
  --env=PORT=8000 \
  --env=RELOAD=false
```

### Option 2: Using Koyeb Web Dashboard
1. Go to koyeb.com
2. Click "Create App"
3. Connect your GitHub repository
4. Select "Docker" as build type
5. Use the existing `Dockerfile`
6. Configure environment variables
7. Add PostgreSQL database service
8. Deploy

### Option 3: Using koyeb.yaml
```bash
# Deploy using the configuration file
koyeb app apply -f koyeb.yaml
```

## Environment Variables

Koyeb will automatically provide:
- `DATABASE_URL` - PostgreSQL connection string
- `BEARER_TOKEN` - Security token (generate your own)

Manual configuration needed:
- `HOST=0.0.0.0`
- `PORT=8000`
- `RELOAD=false`

## Database Configuration

The app automatically detects PostgreSQL in production:
- Uses `DATABASE_URL` environment variable
- Creates tables on startup
- Handles both SQLite (local) and PostgreSQL (production)

## Health Check

Koyeb monitors the `/health` endpoint:
- Returns `{"status": "healthy", "service": "heartbeat-tracker"}`
- Checked every 30 seconds
- 3 retries before marking as unhealthy

## Production URLs

After deployment:
- Main App: `https://your-app-name.koyeb.app`
- Dashboard: `https://your-app-name.koyeb.app/dashboard`
- Health: `https://your-app-name.koyeb.app/health`

## Local Development

For local development with SQLite:
```bash
cp .env.example .env
python run.py
```

For local development with Docker:
```bash
docker build -t heartbeat-tracker .
docker run -p 8000:8000 heartbeat-tracker
```

## Troubleshooting

1. **Build fails**: Check Dockerfile syntax and requirements.txt
2. **Database connection**: Verify DATABASE_URL environment variable
3. **Health check fails**: Ensure /health endpoint is accessible
4. **Port issues**: Make sure port 8000 is exposed and accessible

## Advantages of Koyeb over Render

- Better free tier with more resources
- Global edge network for faster performance
- Built-in CI/CD with GitHub integration
- Automatic HTTPS and custom domains
- Better monitoring and logging
