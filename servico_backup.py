import os
import sys
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import win32event
import win32service
import win32serviceutil
import servicemanager
import win32security

# ============================================================
# CONFIGURAÇÃO
# ============================================================
DIRETORIO = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

HORA_BACKUP = 14
MINUTO_BACKUP = 48
EVENTO_BACKUP_MANUAL = r"Global\TrilanBackupNVR_RunNow"

# Configuração da Pasta de Logs
PASTA_LOG = DIRETORIO / "logs"
PASTA_LOG.mkdir(exist_ok=True)
ARQUIVO_LOG = PASTA_LOG / "servico.log"

logging.basicConfig(
    filename=ARQUIVO_LOG,
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log(mensagem, is_error=False):
    """Grava o log no arquivo de texto e no Visualizador de Eventos do Windows."""
    if is_error:
        logging.error(mensagem)
    else:
        logging.info(mensagem)

    try:
        if is_error:
            servicemanager.LogErrorMsg(mensagem)
        else:
            servicemanager.LogInfoMsg(mensagem)
    except Exception:
        pass


# ============================================================
# SERVIÇO
# ============================================================
class BackupNVRService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TrilanBackupNVR"
    _svc_display_name_ = "Trilan - Backup Automático de NVR"
    _svc_description_ = "Executa automaticamente o backup dos NVRs configurados e envia o resultado por e-mail."

    def __init__(self, args):
        super().__init__(args)
        self.stop_requested = False
        
        # Evento para solicitar parada do serviço
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        # Configuração de Segurança (DACL permissivo) para o Evento Global
        sec_desc = win32security.SECURITY_DESCRIPTOR()
        sec_desc.SetSecurityDescriptorDacl(1, None, 0)
        sec_attr = win32security.SECURITY_ATTRIBUTES()
        sec_attr.SECURITY_DESCRIPTOR = sec_desc

        # Evento para disparo manual via bandeja
        self.hBackupManual = win32event.CreateEvent(sec_attr, 0, 0, EVENTO_BACKUP_MANUAL)

    def SvcStop(self):
        """Chamado quando o serviço recebe comando de parada (Stop)."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        log("Solicitação de parada recebida.")
        self.stop_requested = True
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        """Chamado quando o serviço é iniciado."""
        log("=" * 60)
        log(f"SERVIÇO TRILAN BACKUP NVR INICIADO")
        log(f"Diretório: {DIRETORIO} | Horário automático: {HORA_BACKUP:02d}:{MINUTO_BACKUP:02d}")
        
        try:
            self.executar_loop()
        except Exception:
            log(f"ERRO FATAL NO SERVIÇO:\n{traceback.format_exc()}", is_error=True)
            
        log("SERVIÇO TRILAN BACKUP NVR ENCERRADO")
        log("=" * 60)

    def executar_backup(self, origem):
        """Aciona o script de backup."""
        if self.stop_requested:
            return

        log(f"\n{'='*60}\nINICIANDO BACKUP - Origem: {origem}\n{'='*60}")
        try:
            # Garante que o módulo backup_nvr seja encontrado na pasta do serviço
            if str(DIRETORIO) not in sys.path:
                sys.path.insert(0, str(DIRETORIO))
            
            import backup_nvr
            backup_nvr.main()
            
            log("BACKUP FINALIZADO COM SUCESSO.")
        except Exception:
            log(f"ERRO DURANTE O BACKUP:\n{traceback.format_exc()}", is_error=True)

    def executar_loop(self):
        """Loop principal que controla os horários e eventos."""
        while not self.stop_requested:
            agora = datetime.now()
            proximo = agora.replace(hour=HORA_BACKUP, minute=MINUTO_BACKUP, second=0, microsecond=0)
            
            # Se a hora de hoje já passou, agenda para amanhã
            if proximo <= agora:
                proximo += timedelta(days=1)

            log(f"Próximo backup automático: {proximo.strftime('%d/%m/%Y %H:%M:%S')}")

            # Loop de espera do próximo evento (ou timeout a cada minuto)
            while not self.stop_requested:
                agora = datetime.now()
                segundos = (proximo - agora).total_seconds()

                if segundos <= 0:
                    self.executar_backup("Agendamento automático")
                    break

                # Espera máxima de 60 segundos por ciclo
                espera_ms = int(min(segundos, 60) * 1000)
                eventos = [self.hWaitStop, self.hBackupManual]
                resultado = win32event.WaitForMultipleObjects(eventos, False, espera_ms)

                if resultado == win32event.WAIT_OBJECT_0:
                    return  # O evento hWaitStop foi acionado (parar serviço)
                elif resultado == win32event.WAIT_OBJECT_0 + 1:
                    self.executar_backup("Solicitação manual pela bandeja")


# ============================================================
# EXECUÇÃO
# ============================================================
if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(BackupNVRService)