#!/usr/bin/env python3
"""
Database initialization script for Render deployment
This script ensures the database is properly initialized on first run
"""

import os
import sys

def init_database():
    """Initialize database tables and default data"""
    print("🔄 Initializing database...")
    
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import database modules
        from app.database import create_tables, init_default_settings, ensure_time_required_populated
        from app.database import SessionLocal, DATABASE_URL
        from sqlalchemy import text
        
        # Create database session
        db = SessionLocal()
        
        # Create tables
        create_tables()
        print("✅ Database tables created")
        
        # Run migration for schema updates (if needed)
        if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
            try:
                # Check if daily_working_hours column exists
                result = db.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'settings' 
                    AND column_name = 'daily_working_hours'
                """))
                
                if not result.fetchone():
                    # Add column
                    db.execute(text("""
                        ALTER TABLE settings 
                        ADD COLUMN daily_working_hours FLOAT NOT NULL DEFAULT 8.0
                    """))
                    db.commit()
                    print("✅ daily_working_hours column added to PostgreSQL")
                else:
                    print("✅ daily_working_hours column already exists")
                    
            except Exception as e:
                print(f"⚠️  Migration warning: {e}")
                # Continue with initialization even if migration fails
        
        # Initialize default settings
        init_default_settings()
        print("✅ Default settings initialized")
        
        # Ensure time_required is populated
        ensure_time_required_populated(db)
        print("✅ Time required values populated")
        
        print("🎉 Database initialization completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    print("🚀 Starting database initialization...")
    success = init_database()
    
    if not success:
        print("❌ Initialization failed!")
        sys.exit(1)
    
    print("✅ Ready to start application!")
