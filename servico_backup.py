import os
import sys
import time
import traceback
from datetime import datetime, timedelta

import win32event
import win32service
import win32serviceutil
import servicemanager
import win32security
import win32con


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DIRETORIO = os.path.dirname(
    os.path.abspath(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.abspath(__file__)
)

HORA_BACKUP = 14
MINUTO_BACKUP = 48

EVENTO_BACKUP_MANUAL = r"Global\TrilanBackupNVR_RunNow"


# ============================================================
# LOG
# ============================================================

PASTA_LOG = os.path.join(
    DIRETORIO,
    "logs"
)

os.makedirs(
    PASTA_LOG,
    exist_ok=True
)

ARQUIVO_LOG = os.path.join(
    PASTA_LOG,
    "servico.log"
)


def escrever_log(mensagem):

    texto = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{mensagem}"
    )

    try:

        with open(
            ARQUIVO_LOG,
            "a",
            encoding="utf-8"
        ) as arquivo:

            arquivo.write(
                texto + "\n"
            )

    except Exception:
        pass

    try:

        servicemanager.LogInfoMsg(
            texto
        )

    except Exception:
        pass


# ============================================================
# SERVIÇO
# ============================================================

class BackupNVRService(
    win32serviceutil.ServiceFramework
):

    _svc_name_ = "TrilanBackupNVR"

    _svc_display_name_ = (
        "Trilan - Backup Automático de NVR"
    )

    _svc_description_ = (
        "Executa automaticamente o backup dos NVRs "
        "configurados e envia o resultado por e-mail."
    )

    def __init__(self, args):

        super().__init__(args)

        self.hWaitStop = win32event.CreateEvent(
            None,
            0,
            0,
            None
        )
        security = win32security.SECURITY_ATTRIBUTES()

        security.SECURITY_DESCRIPTOR = (
            win32security.SECURITY_DESCRIPTOR()
        )

        security.SECURITY_DESCRIPTOR.SetSecurityDescriptorDacl(
            1,
            None,
            0
        )

        self.hBackupManual = win32event.CreateEvent(
            security,
            0,
            0,
            EVENTO_BACKUP_MANUAL
        )

        self.stop_requested = False
     

    # ========================================================
    # PARAR
    # ========================================================

    def SvcStop(self):

        self.ReportServiceStatus(
            win32service.SERVICE_STOP_PENDING
        )

        escrever_log(
            "Solicitação de parada recebida."
        )

        self.stop_requested = True

        win32event.SetEvent(
            self.hWaitStop
        )

    # ========================================================
    # INICIAR
    # ========================================================

    def SvcDoRun(self):

        escrever_log("=" * 60)
        escrever_log(
            "SERVIÇO TRILAN BACKUP NVR INICIADO"
        )
        escrever_log(
            f"Diretório: {DIRETORIO}"
        )
        escrever_log(
            f"Horário automático: "
            f"{HORA_BACKUP:02d}:{MINUTO_BACKUP:02d}"
        )

        try:

            self.executar_loop()

        except Exception:

            escrever_log(
                "ERRO FATAL NO SERVIÇO:"
            )

            escrever_log(
                traceback.format_exc()
            )

        escrever_log(
            "SERVIÇO TRILAN BACKUP NVR ENCERRADO"
        )

    # ========================================================
    # BACKUP
    # ========================================================

    def executar_backup(self, origem):

        if self.stop_requested:
            return

        escrever_log("=" * 60)

        escrever_log(
            f"INICIANDO BACKUP - Origem: {origem}"
        )

        try:

            import backup_nvr

            backup_nvr.main()

            escrever_log(
                "BACKUP FINALIZADO COM SUCESSO."
            )

        except Exception:

            escrever_log(
                "ERRO DURANTE O BACKUP:"
            )

            escrever_log(
                traceback.format_exc()
            )

        escrever_log("=" * 60)

    # ========================================================
    # LOOP
    # ========================================================

    def executar_loop(self):

        while not self.stop_requested:

            agora = datetime.now()

            proximo = agora.replace(
                hour=HORA_BACKUP,
                minute=MINUTO_BACKUP,
                second=0,
                microsecond=0
            )

            if proximo <= agora:

                proximo += timedelta(
                    days=1
                )

            escrever_log(
                "Próximo backup automático: "
                f"{proximo.strftime('%d/%m/%Y %H:%M:%S')}"
            )

            while not self.stop_requested:

                agora = datetime.now()

                segundos = (
                    proximo - agora
                ).total_seconds()

                if segundos <= 0:

                    self.executar_backup(
                        "Agendamento automático"
                    )

                    break

                espera_ms = int(
                    min(segundos, 60) * 1000
                )

                resultado = (
                    win32event.WaitForMultipleObjects(
                        [
                            self.hWaitStop,
                            self.hBackupManual
                        ],
                        False,
                        espera_ms
                    )
                )

                if resultado == win32event.WAIT_OBJECT_0:

                    return

                if resultado == (
                    win32event.WAIT_OBJECT_0 + 1
                ):

                    self.executar_backup(
                        "Solicitação manual pela bandeja"
                    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    win32serviceutil.HandleCommandLine(
        BackupNVRService
    )