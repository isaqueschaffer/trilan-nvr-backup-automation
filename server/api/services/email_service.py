import smtplib
import logging
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from config import settings

logger = logging.getLogger(__name__)

LIMIT_ATTACH_BYTES = 20 * 1024 * 1024  # 20 MB


def send_backup_report(
    client_name: str,
    date_str: str,
    nvr_results: List[dict],
    recipients: List[str],
    zip_path: Optional[Path] = None,
) -> bool:
    """Send backup report email. Returns True on success."""
    if not settings.SMTP_SERVER or not settings.SMTP_EMAIL:
        logger.warning("SMTP not configured — skipping email.")
        return False

    if not recipients:
        logger.warning("No recipients configured — skipping email.")
        return False

    icon_map = {"OK": "✅", "PARCIAL": "⚠️", "PARTIAL": "⚠️", "ERRO": "❌", "ERROR": "❌"}
    lines = "\n".join(
        f"  {icon_map.get(r['status'], '❓')} {r['nome']}: {r['status']}"
        for r in nvr_results
    )

    overall = "✅ SUCESSO"
    if any(r["status"] in ("ERRO", "ERROR") for r in nvr_results):
        overall = "❌ COM ERROS"
    elif any(r["status"] in ("PARCIAL", "PARTIAL") for r in nvr_results):
        overall = "⚠️ PARCIAL"

    msg = EmailMessage()
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"[{overall}] Backup NVR — {client_name} — {date_str}"

    body = (
        f"Backup automático de NVR\n"
        f"Cliente : {client_name}\n"
        f"Data    : {date_str}\n"
        f"Status  : {overall}\n\n"
        f"Resultado por NVR:\n{lines}\n\n"
    )

    attach = False
    if zip_path and zip_path.exists():
        size = zip_path.stat().st_size
        if size <= LIMIT_ATTACH_BYTES:
            attach = True
            body += "O arquivo ZIP protegido está em anexo."
        else:
            body += f"⚠️ ZIP excede 20MB e não foi anexado.\nArquivado no servidor: {zip_path.name}"

    msg.set_content(body)

    if attach and zip_path:
        msg.add_attachment(
            zip_path.read_bytes(),
            maintype="application",
            subtype="zip",
            filename=zip_path.name,
        )

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=60) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD or "")
            server.send_message(msg)
        logger.info(f"Email sent to {recipients}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send email: {exc}")
        return False
