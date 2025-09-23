#!/usr/bin/env python3
"""
PostgreSQL-based logging system for RAG System
Replaces the old SQLite-based LogAnalyzer
"""

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
import psutil
import gc
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class LogLevel(Enum):
    """Log levels for PostgreSQL logging"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OperationType(Enum):
    """Types of operations that can be logged"""
    RAG_QUERY = "rag_query"
    QUIZ_GENERATION = "quiz_generation"
    VIDEO_GENERATION = "video_generation"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    SYSTEM_MAINTENANCE = "system_maintenance"
    DATABASE_OPERATION = "database_operation"
    API_CALL = "api_call"
    SUMMARY_GENERATION="summary_generation"
    STUDY_PLAN_GENERATION="study_plan"
    FLASHCARD_GENERATION="flashcard_generation"
    TEST_GENERATION="test_generation"
    OPEN_QUESTION="open_question"


class PostgresLogger:
    """PostgreSQL-based logging system for RAG System"""

    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize PostgreSQL logger

        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        # Initialize file logger for fallback
        self.file_logger = self._setup_file_logger()

        # Test database connection
        self._test_connection()

    def _setup_file_logger(self) -> logging.Logger:
        """Setup file logger as fallback"""
        logger = logging.getLogger('PostgresLogger')
        logger.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler(
            f"logs/postgres_logger_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Avoid duplicate handlers if module imported multiple times
        if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
            logger.addHandler(file_handler)
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            logger.addHandler(console_handler)

        return logger

    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            yield conn
        except Exception as e:
            self.file_logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _test_connection(self):
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    self.file_logger.info("PostgreSQL connection successful")
        except Exception as e:
            self.file_logger.error(f"PostgreSQL connection failed: {e}")
            self.file_logger.warning("Falling back to file logging only")

    def log_operation(
        self,
        operation_type: Union[str, OperationType],
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Log an operation to PostgreSQL

        Args:
            operation_type: Type of operation
            user_id: User ID (optional)
            details: Operation details as JSON
            status: Operation status (success, error, warning)
            error_message: Error message if failed
            duration_ms: Operation duration in milliseconds
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            bool: True if logged successfully, False otherwise
        """
        try:
            # Convert enum to string if needed
            if isinstance(operation_type, OperationType):
                operation_type = operation_type.value

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Handle user_id - if it's not a valid UUID, set to NULL
                    pg_user_id = None
                    if user_id:
                        try:
                            uuid.UUID(user_id)
                            pg_user_id = user_id
                        except ValueError:
                            self.file_logger.warning(f"Invalid UUID format for user_id: {user_id}, setting to NULL")
                            pg_user_id = None

                    cursor.execute(
                        """
                        INSERT INTO operation_logs (
                            id, user_id, operation_type, operation_details, status,
                            error_message, duration_ms, created_at, ip_address, user_agent
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            pg_user_id,
                            operation_type,
                            Json(details) if details is not None else None,
                            status,
                            error_message,
                            duration_ms,
                            datetime.now(timezone.utc),
                            ip_address,
                            user_agent
                        )
                    )
                    conn.commit()
                    return True

        except Exception as e:
            self.file_logger.error(f"Failed to log operation to PostgreSQL: {e}")
            # Fallback to file logging
            self._log_to_file("operation", {
                "operation_type": operation_type,
                "user_id": user_id,
                "details": details,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return False

    def log_user_interaction(
        self,
        user_id: Optional[str],
        action: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Log user interaction

        Args:
            user_id: User ID
            action: Action performed
            details: Interaction details
            session_id: Session ID

        Returns:
            bool: True if logged successfully
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO user_interactions (
                            id, user_id, action, details, created_at, session_id
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            user_id,
                            action,
                            Json(details) if details is not None else None,
                            datetime.now(timezone.utc),
                            session_id
                        )
                    )
                    conn.commit()
                    return True

        except Exception as e:
            self.file_logger.error(f"Failed to log user interaction: {e}")
            return False

    def log_performance_metrics(self, metrics: Dict[str, Any]) -> bool:
        """
        Log performance metrics

        Args:
            metrics: Dictionary of metric_name: value pairs

        Returns:
            bool: True if logged successfully
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for metric_name, metric_value in metrics.items():
                        # Skip non-numeric values
                        if isinstance(metric_value, (int, float)) and not isinstance(metric_value, bool):
                            cursor.execute(
                                """
                                INSERT INTO performance_stats (
                                    id, metric_name, metric_value, metric_unit, date, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    str(uuid.uuid4()),
                                    metric_name,
                                    float(metric_value),
                                    self._get_metric_unit(metric_name),
                                    datetime.now(timezone.utc).date(),
                                    datetime.now(timezone.utc)
                                )
                            )
                        else:
                            self.file_logger.debug(f"Skipping non-numeric metric: {metric_name} = {metric_value}")

                    conn.commit()
                    return True

        except Exception as e:
            self.file_logger.error(f"Failed to log performance metrics: {e}")
            return False

    def _get_metric_unit(self, metric_name: str) -> str:
        """Get unit for metric based on name"""
        units = {
            'cpu_percent': '%',
            'memory_percent': '%',
            'memory_used_mb': 'MB',
            'disk_usage_percent': '%',
            'active_connections': 'count',
            'response_time_ms': 'ms',
            'throughput_requests_per_sec': 'req/s'
        }
        return units.get(metric_name, '')

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_total_mb': memory.total / (1024 * 1024),
                'disk_usage_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            self.file_logger.error(f"Error getting system metrics: {e}")
            return {}

    def log_system_metrics(self) -> bool:
        """Log current system metrics"""
        metrics = self.get_system_metrics()
        if metrics:
            return self.log_performance_metrics(metrics)
        return False

    def update_operation_stats(self, operation_type: str, success: bool, duration_ms: int) -> bool:
        """
        Update operation statistics

        Args:
            operation_type: Type of operation
            success: Whether operation was successful
            duration_ms: Operation duration

        Returns:
            bool: True if updated successfully
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if stats exist for today
                    cursor.execute(
                        """
                        SELECT id, total_count, success_count, error_count, avg_duration_ms
                        FROM operation_stats
                        WHERE operation_type = %s AND date = %s
                        """,
                        (operation_type, datetime.now(timezone.utc).date())
                    )

                    existing = cursor.fetchone()

                    if existing:
                        # Update existing stats
                        stats_id, total_count, success_count, error_count, avg_duration = existing

                        new_total = total_count + 1
                        new_success = success_count + (1 if success else 0)
                        new_error = error_count + (0 if success else 1)

                        # Calculate new average duration
                        new_avg = ((avg_duration * total_count) + duration_ms) / new_total

                        cursor.execute(
                            """
                            UPDATE operation_stats SET
                                total_count = %s,
                                success_count = %s,
                                error_count = %s,
                                avg_duration_ms = %s,
                                min_duration_ms = LEAST(COALESCE(min_duration_ms, %s), %s),
                                max_duration_ms = GREATEST(COALESCE(max_duration_ms, %s), %s),
                                updated_at = %s
                            WHERE id = %s
                            """,
                            (
                                new_total, new_success, new_error, new_avg,
                                duration_ms, duration_ms,  # for LEAST
                                duration_ms, duration_ms,  # for GREATEST
                                datetime.now(timezone.utc), stats_id
                            )
                        )
                    else:
                        # Create new stats record
                        cursor.execute(
                            """
                            INSERT INTO operation_stats (
                                id, operation_type, total_count, success_count, error_count,
                                avg_duration_ms, min_duration_ms, max_duration_ms, date, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                str(uuid.uuid4()),
                                operation_type,
                                1,
                                1 if success else 0,
                                0 if success else 1,
                                duration_ms,
                                duration_ms,
                                duration_ms,
                                datetime.now(timezone.utc).date(),
                                datetime.now(timezone.utc)
                            )
                        )

                    conn.commit()
                    return True

        except Exception as e:
            self.file_logger.error(f"Failed to update operation stats: {e}")
            return False

    def _log_to_file(self, log_type: str, data: Dict[str, Any]):
        """Fallback file logging"""
        log_file = self.logs_dir / f"fallback_{log_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now(timezone.utc).isoformat()} - {log_type.upper()} - {json.dumps(data)}\n")
        except Exception as e:
            self.file_logger.error(f"Failed to write fallback log: {e}")

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get system statistics for the last N days

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with statistics
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:

                    # Get operation statistics
                    cursor.execute(
                        """
                        SELECT
                            operation_type,
                            SUM(total_count) as total_operations,
                            SUM(success_count) as successful_operations,
                            SUM(error_count) as failed_operations,
                            AVG(avg_duration_ms) as avg_duration
                        FROM operation_stats
                        WHERE date >= %s
                        GROUP BY operation_type
                        ORDER BY total_operations DESC
                        """,
                        (datetime.now(timezone.utc).date() - timedelta(days=days),)
                    )

                    operation_stats = cursor.fetchall()

                    # Get recent activity
                    cursor.execute(
                        """
                        SELECT
                            DATE(created_at) as date,
                            COUNT(*) as daily_operations,
                            COUNT(CASE WHEN status = 'success' THEN 1 END) as successful,
                            COUNT(CASE WHEN status = 'error' THEN 1 END) as failed
                        FROM operation_logs
                        WHERE created_at >= %s
                        GROUP BY DATE(created_at)
                        ORDER BY date DESC
                        LIMIT 10
                        """,
                        (datetime.now(timezone.utc) - timedelta(days=days),)
                    )

                    recent_activity = cursor.fetchall()

                    # Get user statistics
                    cursor.execute(
                        """
                        SELECT
                            COUNT(DISTINCT user_id) as unique_users,
                            COUNT(*) as total_interactions
                        FROM user_interactions
                        WHERE created_at >= %s
                        """,
                        (datetime.now(timezone.utc) - timedelta(days=days),)
                    )

                    user_stats = cursor.fetchone()

                    return {
                        'operation_stats': [dict(stat) for stat in operation_stats],
                        'recent_activity': [dict(activity) for activity in recent_activity],
                        'user_stats': dict(user_stats) if user_stats else {},
                        'period_days': days,
                        'generated_at': datetime.now(timezone.utc).isoformat()
                    }

        except Exception as e:
            self.file_logger.error(f"Failed to get statistics: {e}")
            return {}

    def cleanup_old_logs(self, days_to_keep: int = 90) -> bool:
        """
        Clean up old logs from PostgreSQL

        Args:
            days_to_keep: Number of days of logs to keep

        Returns:
            bool: True if cleanup successful
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Clean up old operation logs
                    cursor.execute(
                        """
                        DELETE FROM operation_logs
                        WHERE created_at < %s
                        """,
                        (cutoff_date,)
                    )

                    # Clean up old user interactions
                    cursor.execute(
                        """
                        DELETE FROM user_interactions
                        WHERE created_at < %s
                        """,
                        (cutoff_date,)
                    )

                    # Clean up old performance stats
                    cursor.execute(
                        """
                        DELETE FROM performance_stats
                        WHERE created_at < %s
                        """,
                        (cutoff_date,)
                    )

                    conn.commit()

                    self.file_logger.info(f"Cleaned up logs older than {days_to_keep} days")
                    return True

        except Exception as e:
            self.file_logger.error(f"Failed to cleanup old logs: {e}")
            return False


# Example usage and configuration
if __name__ == "__main__":
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'rag_system',
        'user': 'rag_user',
        'password': 'rag_password_secure_2024'
    }

    # Initialize logger
    logger = PostgresLogger(db_config)

    # Test logging
    logger.log_operation(
        operation_type=OperationType.RAG_QUERY,
        user_id=None,  # No user for this test
        details={"query": "test query", "model": "gemini-1.5-flash"},
        duration_ms=1500
    )

    # Log system metrics
    logger.log_system_metrics()

    # Get statistics
    stats = logger.get_statistics(days=7)
    print("Statistics:", json.dumps(stats, indent=2, default=str))
