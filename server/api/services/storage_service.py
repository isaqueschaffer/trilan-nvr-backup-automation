import shutil
from pathlib import Path
from uuid import UUID
from config import settings


def get_backup_dir(client_id: UUID, date_str: str) -> Path:
    """Return (and create) the storage directory for a client backup."""
    path = Path(settings.BACKUP_STORAGE_PATH) / str(client_id) / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_zip(client_id: UUID, date_str: str, filename: str, data: bytes) -> Path:
    """Save a ZIP file and return its path."""
    target_dir = get_backup_dir(client_id, date_str)
    target = target_dir / filename
    target.write_bytes(data)
    return target


def get_zip_path(client_id: UUID, zip_filename: str) -> Path | None:
    """Find the stored ZIP for a given client and filename."""
    base = Path(settings.BACKUP_STORAGE_PATH) / str(client_id)
    for candidate in base.rglob(zip_filename):
        if candidate.is_file():
            return candidate
    return None


def delete_old_backups(client_id: UUID, keep_days: int) -> int:
    """Delete backup directories older than keep_days. Returns count deleted."""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    base = Path(settings.BACKUP_STORAGE_PATH) / str(client_id)
    deleted = 0
    if base.exists():
        for date_dir in base.iterdir():
            try:
                dt = datetime.strptime(date_dir.name, "%d-%m-%Y")
                if dt < cutoff:
                    shutil.rmtree(date_dir)
                    deleted += 1
            except ValueError:
                pass
    return deleted
