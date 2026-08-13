"""
Trilan NVR Backup — Agent Core
Adapted from backup_nvr.py for client-server architecture.

1. Reads agent.conf  →  SERVER_URL, CLIENT_ID, API_KEY
2. Fetches config from server  →  NVR list, schedule, zip password
3. Backs up each NVR locally (NVRs are on the client's local network)
4. Posts report JSON to server
5. Uploads ZIP to server (server sends email)
"""
import sys
import json
import time
import shutil
import logging
import hashlib
import configparser
from base64 import b64encode
from datetime import datetime
from pathlib import Path

import requests
from requests.auth import HTTPDigestAuth
import pyzipper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
DIR_AGENT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONF_FILE = DIR_AGENT / "agent.conf"
TEMP_DIR = DIR_AGENT / "tmp_backup"
AES_KEY_HEX = bytes.fromhex("bf8a6df8640f38f3812c19d2aaca7743")  # Hikvision WebSDK key
TIMEOUT_NVR = 60
TIMEOUT_SERVER = 120


# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
def setup_logging():
    log_dir = DIR_AGENT / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger("agent")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        fh = logging.FileHandler(log_dir / "agent.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        if sys.stdout is not None:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(ch)


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
def load_conf() -> dict:
    if not CONF_FILE.exists():
        sys.exit(f"ERRO: {CONF_FILE} nao encontrado. Copie agent.conf.example e configure.")
    cfg = configparser.ConfigParser()
    cfg.read(CONF_FILE, encoding="utf-8")
    return {
        "server_url": cfg["server"]["url"].rstrip("/"),
        "client_id": cfg["auth"]["client_id"],
        "api_key": cfg["auth"]["api_key"],
    }


def fetch_server_config(conf: dict) -> dict:
    headers = {"X-Client-ID": conf["client_id"], "X-API-Key": conf["api_key"]}
    r = requests.get(
        f"{conf['server_url']}/api/v1/agent/config",
        headers=headers,
        timeout=30,
        verify=False,  # self-signed cert support
    )
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────
# HIKVISION CRYPTO
# ─────────────────────────────────────────────────────────────
def gerar_secretkey(senha: str) -> tuple[str, str]:
    timestamp = str(int(time.time() * 1000))
    iv_hex = hashlib.md5(timestamp.encode()).hexdigest()
    senha_esc = senha.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    texto = b64encode(senha_esc.encode())
    cipher = AES.new(AES_KEY_HEX, AES.MODE_CBC, bytes.fromhex(iv_hex))
    return cipher.encrypt(pad(texto, AES.block_size)).hex(), iv_hex


# ─────────────────────────────────────────────────────────────
# BACKUP LOGIC (runs locally, NVRs are on local network)
# ─────────────────────────────────────────────────────────────
def data_hoje() -> str:
    return datetime.now().strftime("%d-%m-%Y")


def baixar_arquivo(sessao, url, destino: Path, min_bytes=0, valida_xml=False) -> bool:
    try:
        with sessao.get(url, stream=True, timeout=TIMEOUT_NVR) as r:
            if r.status_code not in (200, 401):
                logging.error(f"HTTP {r.status_code}: {url}")
                return False
            with open(destino, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
        dados = destino.read_bytes()
        if len(dados) < min_bytes:
            raise ValueError("Arquivo muito pequeno (falha de autenticacao).")
        if valida_xml and b"<ResponseStatus" in dados[:500]:
            raise ValueError("Resposta de erro XML recebida.")
        sha256 = hashlib.sha256(dados).hexdigest()
        logging.info(f"  Salvo: {destino.name} ({len(dados)/1024:.1f} KB) SHA-256: {sha256[:16]}...")
        return True
    except Exception as e:
        logging.error(f"  Erro download {destino.name}: {e}")
        destino.unlink(missing_ok=True)
        return False


def processar_nvr(nvr: dict, zip_password: str, pasta_data: Path) -> dict:
    nome, ip, user, pwd = nvr["name"], nvr["ip"], nvr["username"], nvr["password"]
    logging.info(f"\n{'='*50}\n{nome} (IP: {ip})\n{'='*50}")

    pasta_nvr = pasta_data / nome.replace(" ", "_")
    pasta_nvr.mkdir(parents=True, exist_ok=True)

    sessao = requests.Session()
    sessao.auth = HTTPDigestAuth(user, pwd)
    sessao.verify = False

    try:
        sessao.get(f"http://{ip}/ISAPI/System/status", timeout=10).raise_for_status()
        logging.info("  NVR acessivel.")
    except Exception:
        logging.error("  NVR INACESSIVEL.")
        return {"nome": nome, "status": "ERRO"}

    sucessos = 0

    # Config NVR (.bin)
    sk, iv = gerar_secretkey(zip_password)
    url_bin = f"http://{ip}/ISAPI/System/configurationData?secretkey={sk}&security=1&iv={iv}"
    arq_bin = pasta_nvr / f"CONFIG_NVR_{data_hoje()}.bin"
    if baixar_arquivo(sessao, url_bin, arq_bin, min_bytes=100_000, valida_xml=True):
        logging.info("  Backup NVR OK.")
        sucessos += 1

    # Config IPCAM (.xls)
    url_xls = f"http://{ip}/ISAPI/ContentMgmt/InputProxy/ipcConfig"
    arq_xls = pasta_nvr / f"CONFIG_IPCAM_{data_hoje()}.xls"
    if baixar_arquivo(sessao, url_xls, arq_xls):
        logging.info("  Backup IPCAM OK.")
        sucessos += 1

    status = "OK" if sucessos == 2 else "PARCIAL" if sucessos == 1 else "ERRO"
    return {"nome": nome, "status": status}


def criar_zip(pasta: Path, cliente: str, senha: str) -> Path | None:
    zip_path = pasta / f"BACKUP_{cliente.upper().replace(' ','_')}_{data_hoje()}.zip"
    try:
        with pyzipper.AESZipFile(zip_path, "w", compression=pyzipper.ZIP_DEFLATED,
                                  encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(senha.encode())
            for arq in pasta.rglob("*"):
                if arq.is_file() and arq.name != zip_path.name:
                    zf.write(arq, arq.relative_to(pasta))
        with pyzipper.AESZipFile(zip_path, "r") as zf:
            zf.setpassword(senha.encode())
            if zf.testzip() is not None:
                raise ValueError("ZIP corrompido.")
        logging.info(f"  ZIP criado: {zip_path.name}")
        return zip_path
    except Exception as e:
        logging.error(f"  Erro ao criar ZIP: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# SERVER REPORTING
# ─────────────────────────────────────────────────────────────
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
        "nvr_results": [{"nome": r["nome"], "status": r["status"]} for r in resultados],
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


def upload_zip(conf: dict, backup_id: str, zip_path: Path) -> bool:
    headers = {"X-Client-ID": conf["client_id"], "X-API-Key": conf["api_key"]}
    try:
        with open(zip_path, "rb") as f:
            r = requests.post(
                f"{conf['server_url']}/api/v1/agent/backup/upload/{backup_id}",
                headers=headers,
                files={"file": (zip_path.name, f, "application/zip")},
                timeout=TIMEOUT_SERVER,
                verify=False,
            )
        r.raise_for_status()
        logging.info(f"  ZIP enviado ao servidor. Resposta: {r.json()}")
        return True
    except Exception as e:
        logging.error(f"  Erro ao enviar ZIP: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────
def run_backup(trigger: str = "scheduled"):
    setup_logging()
    logging.info(f"\n{'='*60}\nINICIANDO BACKUP — {trigger.upper()}\n{'='*60}")

    conf = load_conf()

    logging.info("Buscando configuracao do servidor...")
    try:
        server_cfg = fetch_server_config(conf)
    except Exception as e:
        logging.error(f"Falha ao buscar config: {e}")
        return

    nvrs = server_cfg["nvrs"]
    zip_password = server_cfg.get("zip_password") or "TrilanBackup2024"
    client_name = server_cfg["client_name"]

    if not nvrs:
        logging.error("Nenhum NVR configurado no servidor para este cliente.")
        return

    logging.info(f"Cliente : {client_name}")
    logging.info(f"NVRs    : {len(nvrs)}")

    # Prepare temp directory
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    started_at = datetime.now()
    resultados = [processar_nvr(nvr, zip_password, TEMP_DIR) for nvr in nvrs]
    finished_at = datetime.now()

    # Show summary
    for r in resultados:
        icone = {"OK": "OK", "PARCIAL": "PARCIAL", "ERRO": "ERRO"}.get(r["status"], "?")
        logging.info(f"  {icone} {r['nome']}")

    # Create ZIP
    zip_path = criar_zip(TEMP_DIR, client_name, zip_password)

    # Send to server
    backup_id = post_report(conf, started_at, finished_at, resultados, trigger)
    if backup_id and zip_path:
        upload_zip(conf, backup_id, zip_path)

    # Cleanup
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    logging.info(f"\nBackup concluido em {(finished_at - started_at).total_seconds():.1f}s")


if __name__ == "__main__":
    run_backup("manual")
