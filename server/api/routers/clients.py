from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_admin_token, generate_api_key
from database import get_db
from models import Client
from schemas import ClientCreate, ClientUpdate, ClientResponse, ClientWithKey
from services.crypto_service import encrypt

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


def _to_response(client: Client) -> ClientResponse:
    data = ClientResponse.model_validate(client)
    data.nvr_count = len(client.nvrs)
    return data


@router.get("", response_model=List[ClientResponse], dependencies=[Depends(verify_admin_token)])
def list_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return [_to_response(c) for c in clients]


@router.post("", response_model=ClientWithKey, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(verify_admin_token)])
def create_client(body: ClientCreate, db: Session = Depends(get_db)):
    raw_key, key_hash = generate_api_key()
    client = Client(
        name=body.name,
        api_key_hash=key_hash,
        api_key_prefix=raw_key[:16],
        backup_hour=body.backup_hour,
        backup_minute=body.backup_minute,
        zip_password=encrypt(body.zip_password) if body.zip_password else None,
        email_to=body.email_to,
        active=body.active,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    resp = ClientWithKey.model_validate(client)
    resp.nvr_count = 0
    resp.api_key = raw_key  # returned only once
    return resp


@router.get("/{client_id}", response_model=ClientResponse, dependencies=[Depends(verify_admin_token)])
def get_client(client_id: UUID, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _to_response(client)


@router.put("/{client_id}", response_model=ClientResponse, dependencies=[Depends(verify_admin_token)])
def update_client(client_id: UUID, body: ClientUpdate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "zip_password" and value:
            setattr(client, field, encrypt(value))
        else:
            setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return _to_response(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(verify_admin_token)])
def delete_client(client_id: UUID, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()


@router.post("/{client_id}/rotate-key", response_model=ClientWithKey,
             dependencies=[Depends(verify_admin_token)])
def rotate_api_key(client_id: UUID, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    raw_key, key_hash = generate_api_key()
    client.api_key_hash = key_hash
    client.api_key_prefix = raw_key[:16]
    db.commit()
    db.refresh(client)
    resp = ClientWithKey.model_validate(client)
    resp.nvr_count = len(client.nvrs)
    resp.api_key = raw_key
    return resp
