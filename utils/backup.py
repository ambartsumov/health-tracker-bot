"""
Database backup utility for Health Bot.
Automatic backups with compression and retention policy.
"""

import os
import shutil
import gzip
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import sqlite3

from config import config, BACKUPS_DIR

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Database backup manager."""

    def __init__(
        self,
        db_path: str = None,
        backup_dir: Path = None,
        retention_days: int = 7,
        compress: bool = True
    ):
        """
        Initialize backup manager.

        Args:
            db_path: Path to database file
            backup_dir: Directory to store backups
            retention_days: Number of days to keep backups
            compress: Compress backups with gzip
        """
        self.db_path = Path(db_path) if db_path else Path(config.BASE_DIR) / "health_bot.db"
        self.backup_dir = backup_dir or BACKUPS_DIR
        self.retention_days = retention_days
        self.compress = compress

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """
        Create database backup.

        Args:
            backup_name: Optional custom backup name

        Returns:
            Path to backup file
        """
        try:
            # Generate backup filename
            if backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{backup_name}_{timestamp}"
            else:
                filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Copy database file
            temp_backup = self.backup_dir / f"{filename}.db"

            # Ensure database is not being written to
            # Use SQLite backup API for safe backup
            self._sqlite_backup(temp_backup)

            logger.info(f"Created backup: {temp_backup}")

            # Compress if enabled
            if self.compress:
                compressed = self._compress_backup(temp_backup)
                temp_backup.unlink()  # Remove uncompressed
                logger.info(f"Compressed backup: {compressed}")
                backup_path = compressed
            else:
                backup_path = temp_backup

            # Clean old backups
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise

    def _sqlite_backup(self, backup_path: Path):
        """Create backup using SQLite backup API (safe for live databases)."""
        try:
            # Connect to source database
            source = sqlite3.connect(self.db_path)
            # Connect to backup database
            backup = sqlite3.connect(backup_path)

            # Perform backup
            with backup:
                source.backup(backup)

            source.close()
            backup.close()

            logger.debug(f"SQLite backup created: {backup_path}")

        except Exception as e:
            logger.error(f"SQLite backup failed: {e}")
            # Fallback to simple copy
            shutil.copy2(self.db_path, backup_path)

    def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup file with gzip."""
        compressed_path = Path(str(backup_path) + '.gz')

        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        return compressed_path

    def cleanup_old_backups(self):
        """Remove backups older than retention period."""
        try:
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            removed = []

            for backup_file in self.backup_dir.glob("backup_*"):
                # Get file modification time
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                if mtime < cutoff:
                    backup_file.unlink()
                    removed.append(backup_file.name)

            if removed:
                logger.info(f"Cleaned up {len(removed)} old backups: {removed}")

        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

    def list_backups(self) -> List[dict]:
        """List all available backups."""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("backup_*")):
            stat = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'compressed': backup_file.suffix == '.gz'
            })

        return backups

    def restore_backup(self, backup_path: str, target_db: Optional[str] = None):
        """
        Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_db: Optional target database path (default: original db)
        """
        try:
            backup_file = Path(backup_path)
            target = Path(target_db) if target_db else self.db_path

            if not backup_file.exists():
                raise FileNotFoundError(f"Backup not found: {backup_file}")

            # Decompress if needed
            if backup_file.suffix == '.gz':
                logger.info("Decompressing backup...")
                temp_file = backup_file.with_suffix('')

                with gzip.open(backup_file, 'rb') as f_in:
                    with open(temp_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                backup_file = temp_file

            # Restore database
            shutil.copy2(backup_file, target)
            logger.info(f"Restored backup: {backup_file} -> {target}")

            # Clean up temp file
            if backup_file.suffix == '.db' and str(backup_file).endswith('.db'):
                pass  # Keep original

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise

    def get_latest_backup(self) -> Optional[Path]:
        """Get path to most recent backup."""
        backups = sorted(self.backup_dir.glob("backup_*"), reverse=True)
        return backups[0] if backups else None

    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity."""
        try:
            backup_file = Path(backup_path)

            # Decompress if needed
            if backup_file.suffix == '.gz':
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
                    temp_path = Path(tmp.name)

                    with gzip.open(backup_file, 'rb') as f_in:
                        with open(temp_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    backup_file = temp_path

            # Check integrity
            conn = sqlite3.connect(backup_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()

            # Clean up temp file
            if backup_file.suffix == '.db' and 'tmp' in str(backup_file):
                backup_file.unlink()

            if result == 'ok':
                logger.info(f"Backup verified: {backup_path}")
                return True
            else:
                logger.error(f"Backup integrity check failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False


# Global backup manager instance
backup_manager = DatabaseBackup()


# Convenience functions
def create_backup(name: Optional[str] = None) -> Path:
    """Create a database backup."""
    return backup_manager.create_backup(name)


def restore_backup(backup_path: str):
    """Restore from backup."""
    backup_manager.restore_backup(backup_path)


def list_backups() -> List[dict]:
    """List all backups."""
    return backup_manager.list_backups()


def cleanup_old_backups():
    """Clean up old backups."""
    backup_manager.cleanup_old_backups()


def get_latest_backup() -> Optional[Path]:
    """Get latest backup path."""
    return backup_manager.get_latest_backup()


# Scheduled backup task
async def scheduled_backup_task():
    """Daily backup task (call from scheduler)."""
    try:
        logger.info("Running scheduled backup...")
        backup_path = create_backup()
        logger.info(f"Scheduled backup created: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Scheduled backup failed: {e}")
        return None
