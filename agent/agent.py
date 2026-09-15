"""
Trilan NVR Backup — Agent Core Entry Point
Refactored to separate concerns into Domain/Application layers.
"""
from src.application.backup_job import run_backup

if __name__ == "__main__":
    run_backup("manual")
