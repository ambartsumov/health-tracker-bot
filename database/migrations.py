"""
Database migrations for Health Bot.
Run this script to initialize or update the database schema.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import db_manager
from database.models import Base, get_engine, inspect
from config import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run database migrations."""
    logger.info("Starting database migrations...")
    
    try:
        # Initialize database (create tables if they don't exist)
        db_manager.initialize()
        logger.info("✅ Database tables created successfully")
        
        # Verify tables
        engine = get_engine(config.database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"📊 Tables in database: {', '.join(tables)}")
        
        logger.info("✅ Migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def reset_database():
    """Reset database (drop all tables and recreate)."""
    logger.warning("⚠️  WARNING: This will delete all data!")
    
    try:
        engine = get_engine(config.database_url)
        Base.metadata.drop_all(bind=engine)
        logger.info("🗑️  All tables dropped")
        
        db_manager.initialize()
        logger.info("✅ Database recreated successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Reset failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "reset":
            confirm = input("Are you sure you want to reset the database? (yes/no): ")
            if confirm.lower() == "yes":
                reset_database()
            else:
                logger.info("Database reset cancelled")
        elif sys.argv[1] == "migrate":
            run_migrations()
        else:
            print("Usage: python migrations.py [migrate|reset]")
    else:
        run_migrations()
