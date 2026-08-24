import smtplib
import logging
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from config import settings
from models import Setting

logger = logging.getLogger(__name__)

LIMIT_ATTACH_BYTES = 5 * 1024 * 1024  # 5 MB


def _build_backup_section(nvr_results: List[dict], overall: str) -> str:
    """Section 1 — Backup dos NVRs."""
    icon_map = {"OK": "✅", "PARCIAL": "⚠️", "PARTIAL": "⚠️", "ERRO": "❌", "ERROR": "❌", "SEM_ARQUIVOS": "ℹ️"}

    lines = "\n".join(
        f"  {icon_map.get(r['status'], '❓')} {r['nome']}: "
        f"{'OK' if r['status'] == 'OK' else 'Gravações OK (Backup de config. não suportado)' if r['status'] == 'SEM_ARQUIVOS' else 'FALHA — ' + r['status']}"
        for r in nvr_results
    )

    return (
        f"1. Backup dos NVRs\n"
        f"{'─' * 40}\n"
        f"Backup automático de NVR\n"
        f"Total de NVRs: {len(nvr_results)}\n"
        f"Status: {overall}\n\n"
        f"Resultado por NVR:\n{lines}\n"
    )


def _build_camera_section(nvr_results: List[dict]) -> str:
    """Section 2 — Verificação de Câmeras e Gravações."""
    total_nvrs = len(nvr_results)
    total_cameras = 0
    cameras_online = 0
    cameras_offline = 0
    cameras_online_sem_gravacao = 0
    problemas_por_nvr: dict[str, list[str]] = {}

    for r in nvr_results:
        cameras = r.get("cameras") or []
        nvr_nome = r["nome"]
        problemas: list[str] = []

        for cam in cameras:
            total_cameras += 1
            online = cam.get("online")
            total_dias = cam.get("total_dias", 0)
            mapa = cam.get("mapa", "")
            cam_nome = cam.get("nome", f"Canal {cam.get('canal', '?')}")

            # Verifica se gravou hoje baseado no mapa (último caractere).
            # Se o mapa não vier, cai para fallback (total_dias > 0)
            gravou_hoje = (mapa[-1] == "█") if mapa else (total_dias > 0)

            if online is False:
                cameras_offline += 1
                problemas.append(f"  ❌ {cam_nome}: Offline")
            elif online is True:
                cameras_online += 1
                if not gravou_hoje:
                    cameras_online_sem_gravacao += 1
                    problemas.append(f"  ⚠️ {cam_nome}: Online, mas sem gravação recente (hoje)")
            else:
                # online is None — status desconhecido, conta como offline
                cameras_offline += 1
                problemas.append(f"  ❌ {cam_nome}: Offline (status desconhecido)")

        if problemas:
            problemas_por_nvr[nvr_nome] = problemas

    section = (
        f"\n2. Verificação de Câmeras e Gravações\n"
        f"{'─' * 40}\n"
        f"Verificação das câmeras de todos os NVRs\n"
        f"Total de NVRs: {total_nvrs}\n"
        f"Total de câmeras: {total_cameras}\n"
        f"Câmeras online: {cameras_online}\n"
        f"Câmeras offline: {cameras_offline}\n"
        f"Câmeras online sem gravação: {cameras_online_sem_gravacao}\n"
    )

    if problemas_por_nvr:
        section += f"\nCâmeras com problemas:\n"
        for nvr_nome, probs in problemas_por_nvr.items():
            section += f"\n  {nvr_nome}:\n"
            section += "\n".join(probs) + "\n"
    else:
        section += f"\n✅ Todas as câmeras estão online e gravando.\n"

    return section


def _build_result_section(nvr_results: List[dict]) -> str:
    """Section 3 — Resultado do Serviço."""
    has_cameras = any(r.get("cameras") for r in nvr_results)

    backup_ok = all(r["status"] in ("OK",) for r in nvr_results)
    has_motorola = any(r["status"] == "SEM_ARQUIVOS" for r in nvr_results)
    
    if backup_ok:
        backup_icon = "✅ Concluído"
    elif has_motorola and all(r["status"] in ("OK", "SEM_ARQUIVOS") for r in nvr_results):
        backup_icon = "ℹ️ Concluído (NVR Motorola não suporta backup de arquivo)"
    else:
        backup_icon = "⚠️ Concluído com ressalvas"

    if has_cameras:
        all_cameras = [cam for r in nvr_results for cam in (r.get("cameras") or [])]
        any_offline = any(cam.get("online") is False for cam in all_cameras)
        any_no_rec = False
        for cam in all_cameras:
            if cam.get("online") is True:
                mapa = cam.get("mapa", "")
                gravou_hoje = (mapa[-1] == "█") if mapa else (cam.get("total_dias", 0) > 0)
                if not gravou_hoje:
                    any_no_rec = True
                    break

        cam_icon = "⚠️ Concluída com problemas" if any_offline else "✅ Concluída"
        rec_icon = "⚠️ Concluída com problemas" if (any_offline or any_no_rec) else "✅ Concluída"
    else:
        cam_icon = "ℹ️ Sem dados de câmeras"
        rec_icon = "ℹ️ Sem dados de gravações"

    return (
        f"\n3. Resultado do Serviço\n"
        f"{'─' * 40}\n"
        f"Backup dos NVRs: {backup_icon}\n"
        f"Verificação das câmeras: {cam_icon}\n"
        f"Verificação das gravações: {rec_icon}\n"
    )


def send_backup_report(
    client_name: str,
    date_str: str,
    nvr_results: List[dict],
    recipients: List[str],
    db: Session,
    zip_path: Optional[Path] = None,
    backup_id: Optional[str] = None,
    base_url: Optional[str] = None,
    public_url: Optional[str] = None,
) -> bool:
    """Send backup report email. Returns True on success."""
    smtp_server_setting = db.query(Setting).filter_by(key="smtp_server").first()
    smtp_email_setting = db.query(Setting).filter_by(key="smtp_email").first()
    smtp_port_setting = db.query(Setting).filter_by(key="smtp_port").first()
    smtp_password_setting = db.query(Setting).filter_by(key="smtp_password").first()

    smtp_server = smtp_server_setting.value if smtp_server_setting and smtp_server_setting.value else settings.SMTP_SERVER
    smtp_email = smtp_email_setting.value if smtp_email_setting and smtp_email_setting.value else settings.SMTP_EMAIL
    
    try:
        smtp_port = int(smtp_port_setting.value) if smtp_port_setting and smtp_port_setting.value else settings.SMTP_PORT
    except ValueError:
        smtp_port = settings.SMTP_PORT
        
    smtp_password = smtp_password_setting.value if smtp_password_setting and smtp_password_setting.value else settings.SMTP_PASSWORD

    if not smtp_server or not smtp_email:
        logger.warning("SMTP not configured — skipping email.")
        return False

    if not recipients:
        logger.warning("No recipients configured — skipping email.")
        return False

    # ── Overall backup status ──
    overall = "✅ SUCESSO"
    if any(r["status"] in ("ERRO", "ERROR") for r in nvr_results):
        overall = "❌ COM ERROS"
    elif any(r["status"] in ("PARCIAL", "PARTIAL") for r in nvr_results):
        overall = "⚠️ PARCIAL"

    # ── Date/time formatting ──
    now = datetime.now()
    date_hora_str = now.strftime("%d/%m/%Y – %H:%M")

    # ── Build email ──
    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"Relatório de Backup e Verificação de CFTV — {client_name} — {date_str}"

    # ── Header ──
    body = (
        f"{'═' * 50}\n"
        f"  Relatório de Backup e Verificação de CFTV\n"
        f"{'═' * 50}\n\n"
        f"Cliente: {client_name}\n"
        f"Data e hora: {date_hora_str}\n\n"
        f"Serviço executado:\n"
        f"Backup das configurações dos NVRs e verificação do status das câmeras e das gravações.\n\n"
    )

    # ── Section 1: Backup ──
    body += _build_backup_section(nvr_results, overall)

    # ── Download links / attachment ──
    attach = False
    if zip_path and zip_path.exists():
        size = zip_path.stat().st_size
        if size <= LIMIT_ATTACH_BYTES:
            attach = True
            body += "\n📎 O arquivo ZIP protegido está em anexo.\n"
        else:
            body += f"\n⚠️ O ZIP excede o limite de anexo (5 MB) e não pôde ser anexado.\n"

    if backup_id:
        body += f"\n🔗 LINKS PARA BAIXAR O BACKUP DIRETAMENTE:\n"
        if public_url:
            link_public = f"{public_url.rstrip('/')}/api/v1/backups/public-download/{backup_id}"
            body += f"  Acesso: {link_public}\n"
        if base_url:
            link_ddns = f"{base_url.rstrip('/')}/api/v1/backups/public-download/{backup_id}"
            body += f"  Acesso: {link_ddns}\n"
        body += f"\n  O link não requer senha do painel e pode ser acessado de qualquer navegador.\n"
    elif zip_path and not attach:
        body += f"\n  Arquivado no servidor: {zip_path.name}\n"

    # ── Section 2: Câmeras e Gravações ──
    body += _build_camera_section(nvr_results)

    # ── Section 3: Resultado do Serviço ──
    body += _build_result_section(nvr_results)

    # ── Footer ──
    body += (
        f"\n{'═' * 50}\n"
        f"  Relatório gerado automaticamente — Trilan CFTV\n"
        f"{'═' * 50}\n"
    )

    msg.set_content(body)

    if attach and zip_path:
        msg.add_attachment(
            zip_path.read_bytes(),
            maintype="application",
            subtype="zip",
            filename=zip_path.name,
        )

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=60) as server:
            server.starttls()
            server.login(smtp_email, smtp_password or "")
            server.send_message(msg)
        logger.info(f"Email sent to {recipients}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send email: {exc}")
        return False
