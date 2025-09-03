#!/usr/bin/env python3
"""
Migration script to move from SQLite to PostgreSQL
"""

import sqlite3
import psycopg2
import os
import json
from datetime import datetime
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)

class SQLiteToPostgresMigrator:
    def __init__(self, sqlite_path, pg_config):
        self.sqlite_path = sqlite_path
        self.pg_config = pg_config
        self.sqlite_conn = None
        self.pg_conn = None
        
    def connect_sqlite(self):
        """Connect to SQLite database"""
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row
            logging.info(f"Connected to SQLite: {self.sqlite_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to SQLite: {e}")
            return False
    
    def connect_postgres(self):
        """Connect to PostgreSQL database"""
        try:
            self.pg_conn = psycopg2.connect(**self.pg_config)
            logging.info("Connected to PostgreSQL")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {e}")
            return False
    
    def get_sqlite_tables(self):
        """Get list of tables in SQLite database"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables
    
    def migrate_operation_stats(self):
        """Migrate operation_stats table"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT * FROM operation_stats")
            rows = cursor.fetchall()
            
            if not rows:
                logging.info("No operation_stats data to migrate")
                return
            
            pg_cursor = self.pg_conn.cursor()
            
            for row in rows:
                # Convert SQLite row to dict
                row_dict = dict(row)
                
                # Insert into PostgreSQL
                pg_cursor.execute("""
                    INSERT INTO operation_stats (
                        operation_type, total_count, success_count, error_count,
                        avg_duration_ms, min_duration_ms, max_duration_ms,
                        date, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (operation_type, date) DO UPDATE SET
                        total_count = EXCLUDED.total_count,
                        success_count = EXCLUDED.success_count,
                        error_count = EXCLUDED.error_count,
                        avg_duration_ms = EXCLUDED.avg_duration_ms,
                        min_duration_ms = EXCLUDED.min_duration_ms,
                        max_duration_ms = EXCLUDED.max_duration_ms,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    row_dict.get('operation_type'),
                    row_dict.get('total_count', 0),
                    row_dict.get('success_count', 0),
                    row_dict.get('error_count', 0),
                    row_dict.get('avg_duration_ms', 0.0),
                    row_dict.get('min_duration_ms'),
                    row_dict.get('max_duration_ms'),
                    row_dict.get('date', datetime.now().date()),
                    row_dict.get('created_at', datetime.now()),
                    row_dict.get('updated_at', datetime.now())
                ))
            
            self.pg_conn.commit()
            pg_cursor.close()
            cursor.close()
            logging.info(f"Migrated {len(rows)} operation_stats records")
            
        except Exception as e:
            logging.error(f"Error migrating operation_stats: {e}")
            self.pg_conn.rollback()
    
    def migrate_performance_stats(self):
        """Migrate performance_stats table"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT * FROM performance_stats")
            rows = cursor.fetchall()
            
            if not rows:
                logging.info("No performance_stats data to migrate")
                return
            
            pg_cursor = self.pg_conn.cursor()
            
            for row in rows:
                row_dict = dict(row)
                
                pg_cursor.execute("""
                    INSERT INTO performance_stats (
                        metric_name, metric_value, metric_unit, date, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (metric_name, date) DO UPDATE SET
                        metric_value = EXCLUDED.metric_value,
                        metric_unit = EXCLUDED.metric_unit
                """, (
                    row_dict.get('metric_name'),
                    row_dict.get('metric_value', 0.0),
                    row_dict.get('metric_unit'),
                    row_dict.get('date', datetime.now().date()),
                    row_dict.get('created_at', datetime.now())
                ))
            
            self.pg_conn.commit()
            pg_cursor.close()
            cursor.close()
            logging.info(f"Migrated {len(rows)} performance_stats records")
            
        except Exception as e:
            logging.error(f"Error migrating performance_stats: {e}")
            self.pg_conn.rollback()
    
    def migrate_usage_stats(self):
        """Migrate usage_stats table"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT * FROM usage_stats")
            rows = cursor.fetchall()
            
            if not rows:
                logging.info("No usage_stats data to migrate")
                return
            
            pg_cursor = self.pg_conn.cursor()
            
            for row in rows:
                row_dict = dict(row)
                
                pg_cursor.execute("""
                    INSERT INTO usage_stats (
                        user_id, date, total_connections, total_queries,
                        total_quiz_generations, total_video_generations,
                        total_duration_minutes, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, date) DO UPDATE SET
                        total_connections = EXCLUDED.total_connections,
                        total_queries = EXCLUDED.total_queries,
                        total_quiz_generations = EXCLUDED.total_quiz_generations,
                        total_video_generations = EXCLUDED.total_video_generations,
                        total_duration_minutes = EXCLUDED.total_duration_minutes,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    row_dict.get('user_id'),
                    row_dict.get('date', datetime.now().date()),
                    row_dict.get('total_connections', 0),
                    row_dict.get('total_queries', 0),
                    row_dict.get('total_quiz_generations', 0),
                    row_dict.get('total_video_generations', 0),
                    row_dict.get('total_duration_minutes', 0),
                    row_dict.get('created_at', datetime.now()),
                    row_dict.get('updated_at', datetime.now())
                ))
            
            self.pg_conn.commit()
            pg_cursor.close()
            cursor.close()
            logging.info(f"Migrated {len(rows)} usage_stats records")
            
        except Exception as e:
            logging.error(f"Error migrating usage_stats: {e}")
            self.pg_conn.rollback()
    
    def create_backup(self):
        """Create backup of SQLite database"""
        backup_path = f"{self.sqlite_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            import shutil
            shutil.copy2(self.sqlite_path, backup_path)
            logging.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logging.error(f"Failed to create backup: {e}")
            return None
    
    def migrate_all(self):
        """Migrate all data from SQLite to PostgreSQL"""
        try:
            # Create backup first
            backup_path = self.create_backup()
            if not backup_path:
                logging.warning("Proceeding without backup")
            
            # Connect to both databases
            if not self.connect_sqlite():
                return False
            
            if not self.connect_postgres():
                return False
            
            # Get list of tables
            tables = self.get_sqlite_tables()
            logging.info(f"Found tables: {tables}")
            
            # Migrate each table
            if 'operation_stats' in tables:
                self.migrate_operation_stats()
            
            if 'performance_stats' in tables:
                self.migrate_performance_stats()
            
            if 'usage_stats' in tables:
                self.migrate_usage_stats()
            
            logging.info("Migration completed successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Migration failed: {e}")
            return False
        
        finally:
            if self.sqlite_conn:
                self.sqlite_conn.close()
            if self.pg_conn:
                self.pg_conn.close()

def main():
    """Main migration function"""
    
    # PostgreSQL configuration
    pg_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', 5432),
        'database': os.getenv('DB_NAME', 'rag_system'),
        'user': os.getenv('DB_USER', 'rag_user'),
        'password': os.getenv('DB_PASSWORD', 'rag_password_secure_2024')
    }
    
    # SQLite database path
    sqlite_path = "statistics.db"
    
    if not os.path.exists(sqlite_path):
        logging.error(f"SQLite database not found: {sqlite_path}")
        return
    
    # Create migrator and run migration
    migrator = SQLiteToPostgresMigrator(sqlite_path, pg_config)
    
    print("=" * 60)
    print("SQLite to PostgreSQL Migration Tool")
    print("=" * 60)
    print(f"Source: {sqlite_path}")
    print(f"Target: {pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
    print("=" * 60)
    
    response = input("Do you want to proceed with migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Run migration
    success = migrator.migrate_all()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("You can now update your application to use PostgreSQL.")
    else:
        print("\n❌ Migration failed. Check migration.log for details.")

if __name__ == "__main__":
    main()
