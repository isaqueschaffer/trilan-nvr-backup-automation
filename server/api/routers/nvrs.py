from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_admin_token
from database import get_db
from models import Client, NVR
from schemas import NVRCreate, NVRUpdate, NVRResponse
from services.crypto_service import encrypt

router = APIRouter(prefix="/api/v1/clients/{client_id}/nvrs", tags=["nvrs"])


def _get_client_or_404(client_id: UUID, db: Session) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("", response_model=List[NVRResponse], dependencies=[Depends(verify_admin_token)])
def list_nvrs(client_id: UUID, db: Session = Depends(get_db)):
    _get_client_or_404(client_id, db)
    return db.query(NVR).filter(NVR.client_id == client_id).all()


@router.post("", response_model=NVRResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(verify_admin_token)])
def create_nvr(client_id: UUID, body: NVRCreate, db: Session = Depends(get_db)):
    _get_client_or_404(client_id, db)
    nvr = NVR(
        client_id=client_id,
        name=body.name,
        ip=body.ip,
        username=body.username,
        password=encrypt(body.password),
    )
    db.add(nvr)
    db.commit()
    db.refresh(nvr)
    return nvr


@router.put("/{nvr_id}", response_model=NVRResponse, dependencies=[Depends(verify_admin_token)])
def update_nvr(client_id: UUID, nvr_id: UUID, body: NVRUpdate, db: Session = Depends(get_db)):
    nvr = db.query(NVR).filter(NVR.id == nvr_id, NVR.client_id == client_id).first()
    if not nvr:
        raise HTTPException(status_code=404, detail="NVR not found")
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "password" and value:
            nvr.password = encrypt(value)
        else:
            setattr(nvr, field, value)
    db.commit()
    db.refresh(nvr)
    return nvr


@router.delete("/{nvr_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(verify_admin_token)])
def delete_nvr(client_id: UUID, nvr_id: UUID, db: Session = Depends(get_db)):
    nvr = db.query(NVR).filter(NVR.id == nvr_id, NVR.client_id == client_id).first()
    if not nvr:
        raise HTTPException(status_code=404, detail="NVR not found")
    db.delete(nvr)
    db.commit()
