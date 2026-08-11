from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date

from auth import verify_admin_token
from database import get_db
from models import Backup, Client
from schemas import BackupResponse, PaginatedBackups
from services.storage_service import get_zip_path

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])


def _to_response(b: Backup) -> BackupResponse:
    r = BackupResponse.model_validate(b)
    r.client_name = b.client.name if b.client else None
    return r


@router.get("", response_model=PaginatedBackups, dependencies=[Depends(verify_admin_token)])
def list_backups(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    client_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Backup).options(joinedload(Backup.client))

    if client_id:
        q = q.filter(Backup.client_id == client_id)
    if status_filter:
        q = q.filter(Backup.status == status_filter.upper())
    if date_from:
        q = q.filter(cast(Backup.started_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Backup.started_at, Date) <= date_to)

    total = q.count()
    items = q.order_by(Backup.started_at.desc()).offset((page - 1) * size).limit(size).all()
    pages = (total + size - 1) // size or 1

    return PaginatedBackups(
        items=[_to_response(b) for b in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{backup_id}", response_model=BackupResponse, dependencies=[Depends(verify_admin_token)])
def get_backup(backup_id: UUID, db: Session = Depends(get_db)):
    b = db.query(Backup).options(joinedload(Backup.client)).filter(Backup.id == backup_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Backup not found")
    return _to_response(b)


@router.get("/{backup_id}/download", dependencies=[Depends(verify_admin_token)])
def download_backup_zip(backup_id: UUID, db: Session = Depends(get_db)):
    b = db.query(Backup).filter(Backup.id == backup_id).first()
    if not b or not b.zip_filename:
        raise HTTPException(status_code=404, detail="ZIP not available")
    path = get_zip_path(b.client_id, b.zip_filename)
    if not path:
        raise HTTPException(status_code=404, detail="ZIP file not found on disk")
    return FileResponse(path=str(path), filename=b.zip_filename, media_type="application/zip")
