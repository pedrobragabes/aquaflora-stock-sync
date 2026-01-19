"""
AquaFlora Stock Sync - Backup Module
Backup database and stats to cloud storage via rclone.
"""

import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages backups to cloud storage via rclone.
    
    Requires rclone to be installed and configured:
        curl https://rclone.org/install.sh | sudo bash
        rclone config  # Setup Google Drive as 'gdrive'
    """
    
    def __init__(
        self,
        rclone_remote: str = "gdrive:aquaflora-backup",
        retention_days: int = 7,
    ):
        """
        Initialize backup manager.
        
        Args:
            rclone_remote: rclone remote path (e.g., 'gdrive:folder')
            retention_days: Number of days to keep backups
        """
        self.rclone_remote = rclone_remote
        self.retention_days = retention_days
    
    def is_rclone_available(self) -> bool:
        """Check if rclone is installed and configured."""
        try:
            result = subprocess.run(
                ["rclone", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def backup_file(self, filepath: Path, subfolder: str = "") -> bool:
        """
        Backup a single file to cloud storage.
        
        Args:
            filepath: Path to file to backup
            subfolder: Optional subfolder in remote
            
        Returns:
            True if backup succeeded
        """
        if not filepath.exists():
            logger.warning(f"⚠️ Backup skipped: {filepath} does not exist")
            return False
        
        if not self.is_rclone_available():
            logger.error("❌ rclone not available. Install with: curl https://rclone.org/install.sh | sudo bash")
            return False
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
        
        # Build remote path
        remote_path = self.rclone_remote
        if subfolder:
            remote_path = f"{remote_path}/{subfolder}"
        
        try:
            logger.info(f"📦 Backing up {filepath.name} to {remote_path}/{backup_name}")
            
            result = subprocess.run(
                [
                    "rclone", "copyto",
                    str(filepath),
                    f"{remote_path}/{backup_name}",
                    "--progress",
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Backup successful: {backup_name}")
                return True
            else:
                logger.error(f"❌ Backup failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Backup timeout (>5 min)")
            return False
        except Exception as e:
            logger.error(f"❌ Backup error: {e}")
            return False
    
    def cleanup_old_backups(self, prefix: str = "") -> int:
        """
        Remove backups older than retention_days.
        
        Args:
            prefix: Filter files by prefix
            
        Returns:
            Number of files deleted
        """
        if not self.is_rclone_available():
            return 0
        
        try:
            result = subprocess.run(
                [
                    "rclone", "delete",
                    self.rclone_remote,
                    "--min-age", f"{self.retention_days}d",
                    "--dry-run" if logger.level <= logging.DEBUG else "",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result.returncode == 0:
                # Count deleted files from output
                deleted = result.stdout.count("Deleted:")
                if deleted > 0:
                    logger.info(f"🗑️ Cleaned up {deleted} old backups")
                return deleted
            
        except Exception as e:
            logger.warning(f"⚠️ Cleanup failed: {e}")
        
        return 0
    
    def run_full_backup(
        self,
        db_path: Path,
        stats_path: Optional[Path] = None,
    ) -> bool:
        """
        Run full backup of database and optional stats file.
        
        Args:
            db_path: Path to products.db
            stats_path: Optional path to last_run_stats.json
            
        Returns:
            True if all backups succeeded
        """
        logger.info("🚀 Starting backup to cloud storage...")
        
        success = True
        
        # Backup database
        if not self.backup_file(db_path, "database"):
            success = False
        
        # Backup stats if provided
        if stats_path and stats_path.exists():
            if not self.backup_file(stats_path, "stats"):
                success = False
        
        # Cleanup old backups
        self.cleanup_old_backups()
        
        if success:
            logger.info("✅ Backup completed successfully!")
        else:
            logger.warning("⚠️ Backup completed with errors")
        
        return success


def run_backup(
    db_path: Path,
    stats_path: Optional[Path] = None,
    rclone_remote: str = "gdrive:aquaflora-backup",
    retention_days: int = 7,
) -> bool:
    """
    Convenience function to run backup.
    
    Args:
        db_path: Path to products.db
        stats_path: Optional path to last_run_stats.json
        rclone_remote: rclone remote destination
        retention_days: Days to keep backups
        
    Returns:
        True if backup succeeded
    """
    manager = BackupManager(
        rclone_remote=rclone_remote,
        retention_days=retention_days,
    )
    return manager.run_full_backup(db_path, stats_path)
