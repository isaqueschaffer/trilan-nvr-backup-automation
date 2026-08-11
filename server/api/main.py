from datetime import date, timedelta, datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date

from database import Base, engine, get_db
from models import Client, Backup
from schemas import StatsResponse
from auth import verify_admin_token
from routers import auth_router, clients, nvrs, backups, agent, settings_router

# ─── Create tables on startup ──────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Trilan NVR Backup API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(clients.router)
app.include_router(nvrs.router)
app.include_router(backups.router)
app.include_router(agent.router)
app.include_router(settings_router.router)


# ─── Stats endpoint ────────────────────────────────────────────────────────
@app.get("/api/v1/stats", response_model=StatsResponse, dependencies=[Depends(verify_admin_token)])
def get_stats(db: Session = Depends(get_db)):
    today = date.today()
    total = db.query(func.count(Client.id)).scalar() or 0
    active = db.query(func.count(Client.id)).filter(Client.active == True).scalar() or 0

    backups_today_q = db.query(Backup).filter(
        cast(Backup.started_at, Date) == today
    )
    b_today = backups_today_q.count()
    b_ok = backups_today_q.filter(Backup.status == "OK").count()
    b_err = backups_today_q.filter(Backup.status == "ERROR").count()

    return StatsResponse(
        total_clients=total,
        active_clients=active,
        backups_today=b_today,
        backups_ok=b_ok,
        backups_error=b_err,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Trilan NVR Backup API"}
