import logging
import requests
from pathlib import Path
from datetime import datetime

TIMEOUT_SERVER = 120

def fetch_server_config(conf: dict) -> dict:
    headers = {"X-Client-ID": conf["client_id"], "X-API-Key": conf["api_key"]}
    r = requests.get(
        f"{conf['server_url']}/api/v1/agent/config",
        headers=headers,
        timeout=30,
        verify=False,
    )
    r.raise_for_status()
    return r.json()

def post_report(conf: dict, started_at: datetime, finished_at: datetime,
                resultados: list, trigger: str) -> str | None:
    headers = {"X-Client-ID": conf["client_id"], "X-API-Key": conf["api_key"]}
    payload = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": (
            "OK" if all(r["status"] == "OK" for r in resultados) else
            "ERROR" if all(r["status"] == "ERRO" for r in resultados) else "PARTIAL"
        ),
        # campo nvr_results mantido por compatibilidade com o servidor; inclui tipo do equipamento
        "nvr_results": [
            {
                "nome": r["nome"],
                "tipo": r.get("tipo") or "NVR",
                "status": r["status"],
                "cameras": r.get("cameras") or [],
            }
            for r in resultados
        ],
        "trigger": trigger,
    }
    try:
        r = requests.post(
            f"{conf['server_url']}/api/v1/agent/backup/report",
            json=payload, headers=headers, timeout=30, verify=False,
        )
        r.raise_for_status()
        backup_id = r.json()["backup_id"]
        logging.info(f"  Relatorio enviado. backup_id={backup_id}")
        return backup_id
    except Exception as e:
        logging.error(f"  Erro ao enviar relatorio: {e}")
        return None

def upload_zip(conf: dict, backup_id: str, zip_path: Path, device_type: str = "NVR") -> bool:
    headers = {"X-Client-ID": conf["client_id"], "X-API-Key": conf["api_key"]}
    try:
        with open(zip_path, "rb") as f:
            r = requests.post(
                f"{conf['server_url']}/api/v1/agent/backup/upload/{backup_id}",
                params={"device_type": device_type},
                headers=headers,
                files={"file": (zip_path.name, f, "application/zip")},
                timeout=TIMEOUT_SERVER,
                verify=False,
            )
        r.raise_for_status()
        logging.info(f"  ZIP ({device_type}) enviado ao servidor. Resposta: {r.json()}")
        return True
    except Exception as e:
        logging.error(f"  Erro ao enviar ZIP ({device_type}): {e}")
        return False
