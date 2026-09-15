from typing import Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import verify_admin_token
from database import get_db
from models import Setting
from schemas import SettingsResponse

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

ALLOWED_KEYS = {"smtp_server", "smtp_port", "smtp_email", "smtp_password", "retention_days", "admin_password_hash"}


@router.get("", response_model=SettingsResponse, dependencies=[Depends(verify_admin_token)])
def get_settings(db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return SettingsResponse(
        smtp_server=rows.get("smtp_server"),
        smtp_port=rows.get("smtp_port"),
        smtp_email=rows.get("smtp_email"),
        retention_days=rows.get("retention_days"),
    )


@router.put("", response_model=SettingsResponse, dependencies=[Depends(verify_admin_token)])
def update_settings(body: Dict[str, str], db: Session = Depends(get_db)):
    for key, value in body.items():
        if key not in ALLOWED_KEYS:
            continue
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return SettingsResponse(
        smtp_server=rows.get("smtp_server"),
        smtp_port=rows.get("smtp_port"),
        smtp_email=rows.get("smtp_email"),
        retention_days=rows.get("retention_days"),
    )
