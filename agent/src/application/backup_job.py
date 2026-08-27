import logging
import shutil
import requests
from datetime import datetime
from pathlib import Path
from requests.auth import HTTPDigestAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.core.config import load_conf, DIR_AGENT
from src.application.api_client import fetch_server_config, post_report, upload_zip
from src.nvr.factory import verificar_gravacao_nvr
from src.backup.crypto import gerar_secretkey
from src.backup.downloader import baixar_arquivo
from src.backup.archiver import criar_zip, data_hoje

TEMP_DIR = DIR_AGENT / "tmp_backup"

def setup_logging():
    log_dir = DIR_AGENT / "logs"
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger()
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        fh = logging.FileHandler(log_dir / "agent.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        import sys
        if sys.stdout is not None:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(ch)

def processar_nvr(nvr: dict, zip_password: str, pasta_data: Path) -> dict:
    nome, ip, user, pwd = nvr["name"], nvr["ip"], nvr["username"], nvr["password"]
    logging.info(f"\n{'='*50}\n{nome} (IP: {ip})\n{'='*50}")

    pasta_nvr = pasta_data / nome.replace(" ", "_")
    pasta_nvr.mkdir(parents=True, exist_ok=True)

    retorno = verificar_gravacao_nvr(ip, user, pwd)
    if isinstance(retorno, tuple) and len(retorno) == 2:
        cameras_status, tipo = retorno
    else:
        cameras_status, tipo = retorno, "DESCONHECIDO"
    
    if not cameras_status:
        logging.error("  NVR INACESSIVEL ou falha no login.")
        return {"nome": nome, "status": "ERRO"}
        
    logging.info(f"  NVR acessivel (Detectado: {tipo}).")

    sessao = requests.Session()
    sessao.auth = HTTPDigestAuth(user, pwd)
    sessao.verify = False
    
    sucessos = 0
    status = "OK"

    if tipo == "MOTOROLA":
        logging.info("  NVR Motorola detectado. Backup de arquivos de configuracao nao suportado nativamente. Gravacoes verificadas.")
        status = "SEM_ARQUIVOS"
    else:
        try:
            sessao.get(f"http://{ip}/ISAPI/System/status", timeout=5).raise_for_status()
            
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
                
            status = "OK" if sucessos == 2 else "PARCIAL"
        except Exception:
            logging.info("  API ISAPI falhou. Backup de arquivos pulado.")
            status = "PARCIAL"

    return {"nome": nome, "status": status, "cameras": cameras_status}

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

    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    started_at = datetime.now()
    resultados = [processar_nvr(nvr, zip_password, TEMP_DIR) for nvr in nvrs]
    finished_at = datetime.now()

    for r in resultados:
        icone = {"OK": "OK", "PARCIAL": "PARCIAL", "ERRO": "ERRO", "SEM_ARQUIVOS": "SEM_ARQUIVOS"}.get(r["status"], "?")
        logging.info(f"  {icone} {r['nome']}")

    zip_path = criar_zip(TEMP_DIR, client_name, zip_password)

    backup_id = post_report(conf, started_at, finished_at, resultados, trigger)
    if backup_id and zip_path:
        upload_zip(conf, backup_id, zip_path)

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    logging.info(f"\nBackup concluido em {(finished_at - started_at).total_seconds():.1f}s")
