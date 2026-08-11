"""
Trilan NVR Backup Agent — Windows Service
Runs agent.py on a schedule and listens for manual trigger events.

Install:  python service.py install
Start:    python service.py start
Stop:     python service.py stop
Remove:   python service.py remove
"""
import sys
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path

import win32event
import win32service
import win32serviceutil
import servicemanager
import win32security

DIRETORIO = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
EVENTO_BACKUP_MANUAL = r"Global\TrilanAgentNVR_RunNow"

PASTA_LOG = DIRETORIO / "logs"
PASTA_LOG.mkdir(exist_ok=True)
ARQUIVO_LOG = PASTA_LOG / "servico.log"

logging.basicConfig(
    filename=str(ARQUIVO_LOG),
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def log(msg, is_error=False):
    if is_error:
        logging.error(msg)
    else:
        logging.info(msg)
    try:
        if is_error:
            servicemanager.LogErrorMsg(str(msg))
        else:
            servicemanager.LogInfoMsg(str(msg))
    except Exception:
        pass


class TrilanAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TrilanAgentNVR"
    _svc_display_name_ = "Trilan — Agente Backup NVR"
    _svc_description_ = "Executa backups automaticos de NVRs e envia os arquivos ao servidor Trilan."

    def __init__(self, args):
        super().__init__(args)
        self.stop_requested = False
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        sec_desc = win32security.SECURITY_DESCRIPTOR()
        sec_desc.SetSecurityDescriptorDacl(1, None, 0)
        sec_attr = win32security.SECURITY_ATTRIBUTES()
        sec_attr.SECURITY_DESCRIPTOR = sec_desc
        self.hBackupManual = win32event.CreateEvent(sec_attr, 0, 0, EVENTO_BACKUP_MANUAL)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        log("Parada solicitada.")
        self.stop_requested = True
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        log("=" * 60)
        log("TRILAN AGENT NVR INICIADO")
        log(f"Diretorio: {DIRETORIO}")
        try:
            self._load_schedule_and_run()
        except Exception:
            log(f"ERRO FATAL:\n{traceback.format_exc()}", is_error=True)
        log("TRILAN AGENT NVR ENCERRADO")
        log("=" * 60)

    def _load_schedule_and_run(self):
        """Load schedule from server config and run the event loop."""
        if str(DIRETORIO) not in sys.path:
            sys.path.insert(0, str(DIRETORIO))

        import configparser
        import requests

        conf_file = DIRETORIO / "agent.conf"
        cfg = configparser.ConfigParser()
        cfg.read(conf_file)
        server_url = cfg["server"]["url"].rstrip("/")
        client_id = cfg["auth"]["client_id"]
        api_key = cfg["auth"]["api_key"]

        headers = {"X-Client-ID": client_id, "X-API-Key": api_key}
        try:
            r = requests.get(f"{server_url}/api/v1/agent/config", headers=headers,
                             timeout=30, verify=False)
            r.raise_for_status()
            server_cfg = r.json()
            hora = int(server_cfg.get("backup_hour", 2))
            minuto = int(server_cfg.get("backup_minute", 0))
        except Exception as e:
            log(f"Aviso: nao foi possivel buscar horario do servidor ({e}). Usando 02:00.", is_error=True)
            hora, minuto = 2, 0

        self._run_loop(hora, minuto)

    def _run_loop(self, hora: int, minuto: int):
        import agent as agent_mod
        while not self.stop_requested:
            agora = datetime.now()
            proximo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if proximo <= agora:
                proximo += timedelta(days=1)
            log(f"Proximo backup: {proximo.strftime('%d/%m/%Y %H:%M')}")

            while not self.stop_requested:
                agora = datetime.now()
                segundos = (proximo - agora).total_seconds()
                if segundos <= 0:
                    self._executar_backup(agent_mod, "scheduled")
                    break

                espera_ms = int(min(segundos, 60) * 1000)
                resultado = win32event.WaitForMultipleObjects(
                    [self.hWaitStop, self.hBackupManual], False, espera_ms
                )
                if resultado == win32event.WAIT_OBJECT_0:
                    return
                elif resultado == win32event.WAIT_OBJECT_0 + 1:
                    self._executar_backup(agent_mod, "manual")

    def _executar_backup(self, agent_mod, trigger: str):
        if self.stop_requested:
            return
        log(f"INICIANDO BACKUP — {trigger.upper()}")
        try:
            agent_mod.run_backup(trigger)
            log("BACKUP FINALIZADO.")
        except Exception:
            log(f"ERRO NO BACKUP:\n{traceback.format_exc()}", is_error=True)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(TrilanAgentService)
