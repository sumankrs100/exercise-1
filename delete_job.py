import os
import time
import logging
import datetime
from pathlib import Path
from typing import List, Optional, Union


class FileCleanupService:
    """
    A service to clean up files older than a specified time period from a given directory,
    including its subdirectories.
    """

    def __init__(
        self,
        base_path: Union[str, Path],
        retention_days: int = 30,
        log_level: int = logging.INFO,
        dry_run: bool = False,
        file_extensions: Optional[List[str]] = None
    ):
        """
        Initialize the FileCleanupService.

        Args:
            base_path: The base directory path to clean up.
            retention_days: Number of days to keep files (default: 30).
            log_level: Logging level (default: logging.INFO).
            dry_run: If True, will only log actions without actually deleting files (default: False).
            file_extensions: List of file extensions to delete (default: None, which means all files).
        """
        self.base_path = Path(base_path)
        self.retention_days = retention_days
        self.dry_run = dry_run
        self.file_extensions = file_extensions
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        
        # Create console handler if not already configured
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.info(f"FileCleanupService initialized with base path: {self.base_path}")
        self.logger.info(f"Retention period: {self.retention_days} days")
        self.logger.info(f"Dry run: {self.dry_run}")
        
    def _is_file_expired(self, file_path: Path) -> bool:
        """
        Check if a file is older than the retention period.
        
        Args:
            file_path: Path to the file to check.
            
        Returns:
            bool: True if file is older than retention_days, False otherwise.
        """
        try:
            file_mtime = os.path.getmtime(file_path)
            file_age_days = (time.time() - file_mtime) / (60 * 60 * 24)
            return file_age_days > self.retention_days
        except (FileNotFoundError, PermissionError) as e:
            self.logger.error(f"Error accessing file {file_path}: {e}")
            return False
    
    def _should_delete_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be deleted based on its age and extension.
        
        Args:
            file_path: Path to the file to check.
            
        Returns:
            bool: True if file should be deleted, False otherwise.
        """
        # Check if we're filtering by extension
        if self.file_extensions:
            if file_path.suffix.lower() not in [f".{ext.lower()}" if not ext.startswith('.') else ext.lower() 
                                              for ext in self.file_extensions]:
                return False
        
        # Check if file is old enough to delete
        return self._is_file_expired(file_path)
    
    def delete_file(self, file_path: Path) -> bool:
        """
        Delete a single file.
        
        Args:
            file_path: Path to the file to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would delete file: {file_path}")
                return True
            else:
                os.remove(file_path)
                self.logger.info(f"Deleted file: {file_path}")
                return True
        except (FileNotFoundError, PermissionError, OSError) as e:
            self.logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def run_cleanup(self) -> dict:
        """
        Execute the file cleanup job.
        
        This method walks through the base directory and all subdirectories,
        deleting files that match the criteria.
        
        Returns:
            dict: Statistics about the cleanup operation.
        """
        if not self.base_path.exists():
            self.logger.error(f"Base path does not exist: {self.base_path}")
            return {"success": False, "error": "Base path does not exist", "files_deleted": 0}
        
        start_time = time.time()
        files_deleted = 0
        files_failed = 0
        
        self.logger.info(f"Starting cleanup job at {datetime.datetime.now()}")
        self.logger.info(f"Scanning for files older than {self.retention_days} days")
        
        try:
            # Walk through the directory structure
            for root, dirs, files in os.walk(self.base_path):
                current_dir = Path(root)
                
                for filename in files:
                    file_path = current_dir / filename
                    
                    if self._should_delete_file(file_path):
                        if self.delete_file(file_path):
                            files_deleted += 1
                        else:
                            files_failed += 1
        
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return {
                "success": False,
                "error": str(e),
                "files_deleted": files_deleted,
                "files_failed": files_failed
            }
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Prepare and return statistics
        stats = {
            "success": True,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "files_deleted": files_deleted,
            "files_failed": files_failed,
            "base_path": str(self.base_path),
            "retention_days": self.retention_days,
            "dry_run": self.dry_run
        }
        
        self.logger.info(f"Cleanup job completed in {duration:.2f} seconds")
        self.logger.info(f"Files deleted: {files_deleted}")
        self.logger.info(f"Files that failed to delete: {files_failed}")
        
        return stats


# Example usage
if __name__ == "__main__":
    # Example: Delete all log files older than 7 days
    cleanup_service = FileCleanupService(
        base_path="/path/to/logs",
        retention_days=7,
        file_extensions=["log", "txt"],
        dry_run=True  # Set to False to actually delete files
    )
    
    # Run the cleanup
    results = cleanup_service.run_cleanup()
    print(f"Cleanup results: {results}")
