#!/usr/bin/env python3
"""
Database initialization script for Render deployment
This script ensures the database is properly initialized on first run
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_database():
    """Initialize database tables and default data"""
    print("🔄 Initializing database...")
    
    from app.database import create_tables, init_default_settings, ensure_time_required_populated
    from app.database import SessionLocal, DATABASE_URL
    
    db = SessionLocal()
    try:
        # Create tables
        create_tables()
        print("✅ Database tables created")
        
        # Run migration for schema updates (if needed)
        if DATABASE_URL.startswith("postgresql"):
            try:
                # Check if we need to migrate from old schema
                result = db.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'attendance_sheet' 
                    AND column_name = 'check_in'
                """))
                
                if result.fetchone():
                    print("🔄 Migrating from old schema to simplified schema...")
                    
                    # Backup existing data
                    result = db.execute(text("""
                        SELECT id, device_id, date, check_in, check_out, category, description, time_required
                        FROM attendance_sheet
                    """))
                    existing_data = result.fetchall()
                    
                    # Drop and recreate attendance_sheet table
                    db.execute(text("DROP TABLE attendance_sheet"))
                    
                    # Create new table with simplified schema
                    db.execute(text("""
                        CREATE TABLE attendance_sheet (
                            id SERIAL PRIMARY KEY,
                            device_id VARCHAR(100) NOT NULL,
                            date DATE NOT NULL,
                            time_recorded INTEGER NOT NULL DEFAULT 0,
                            category INTEGER NOT NULL,
                            description TEXT,
                            time_required INTEGER NOT NULL DEFAULT 0,
                            UNIQUE (device_id, date),
                            CHECK (category IN (0, 1, 10, 11, 90)),
                            CHECK (time_required >= 0),
                            CHECK (time_recorded >= 0)
                        )
                    """))
                    
                    # Migrate data
                    for row in existing_data:
                        record_id, device_id, date_val, check_in, check_out, category, description, time_required = row
                        
                        # Calculate time_recorded from check_in/check_out
                        time_recorded = 0
                        if check_in and check_out:
                            try:
                                # Parse time strings
                                check_in_parts = str(check_in).split(':')
                                check_out_parts = str(check_out).split(':')
                                
                                check_in_mins = int(check_in_parts[0]) * 60 + int(check_in_parts[1])
                                check_out_mins = int(check_out_parts[0]) * 60 + int(check_out_parts[1])
                                
                                if check_out_mins <= check_in_mins:
                                    check_out_mins += 24 * 60
                                
                                time_recorded = check_out_mins - check_in_mins
                            except:
                                time_recorded = 0
                        
                        # Insert migrated data
                        db.execute(text("""
                            INSERT INTO attendance_sheet (device_id, date, time_recorded, category, description, time_required)
                            VALUES (:device_id, :date, :time_recorded, :category, :description, :time_required)
                        """), {
                            'device_id': device_id,
                            'date': date_val,
                            'time_recorded': time_recorded,
                            'category': category,
                            'description': description,
                            'time_required': time_required
                        })
                    
                    db.commit()
                    print("✅ Schema migration completed")
                
                # Check if daily_working_hours column exists
                result = db.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'settings' 
                    AND column_name = 'daily_working_hours'
                """))
                
                if not result.fetchone():
                    # Add the column
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
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting database initialization...")
    success = init_database()
    
    if not success:
        print("❌ Initialization failed!")
        exit(1)
    
    print("✅ Ready to start application!")
