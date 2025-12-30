#!/usr/bin/env python3
"""
Convenient script to run the attendance tracker server
"""

import uvicorn
import os
from pathlib import Path

def main():
    """Run the FastAPI server"""
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  Warning: .env file not found")
        print("Copy .env.example to .env and configure BEARER_TOKEN")
        print()
    
    # Default configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"🚀 Starting Time Attendance Tracker")
    print(f"📍 Server: http://{host}:{port}")
    print(f"📊 Dashboard: http://{host}:{port}/dashboard")
    print(f"⚙️  Settings: http://{host}:{port}/settings")
    print(f"🔧 Corrections: http://{host}:{port}/corrections")
    print('')
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        access_log=True
    )

if __name__ == "__main__":
    main()
