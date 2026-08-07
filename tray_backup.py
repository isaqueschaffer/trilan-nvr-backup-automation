import os
import sys
import subprocess
import threading
import time
import win32event
import win32con

import pystray

from PIL import Image, ImageDraw
from pystray import MenuItem as item


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DIRETORIO = os.path.dirname(
    os.path.abspath(__file__)
)

SERVICO = "TrilanBackupNVR"

PASTA_BACKUP = r"C:\BKP_NVR"

ARQUIVO_LOG = os.path.join(
    DIRETORIO,
    "logs",
    "servico.log"
)

EVENTO_BACKUP_MANUAL = r"Global\TrilanBackupNVR_RunNow"


# ============================================================
# ÍCONE
# ============================================================

def criar_icone():

    largura = 64
    altura = 64

    imagem = Image.new(
        "RGB",
        (largura, altura),
        "white"
    )

    desenho = ImageDraw.Draw(
        imagem
    )

    desenho.rectangle(
        (10, 10, 54, 25),
        outline="black",
        width=3
    )

    desenho.rectangle(
        (10, 29, 54, 44),
        outline="black",
        width=3
    )

    desenho.ellipse(
        (16, 15, 21, 20),
        fill="green"
    )

    desenho.ellipse(
        (16, 34, 21, 39),
        fill="green"
    )

    desenho.line(
        (28, 48, 28, 58),
        fill="black",
        width=3
    )

    desenho.line(
        (28, 58, 23, 53),
        fill="black",
        width=3
    )

    desenho.line(
        (28, 58, 33, 53),
        fill="black",
        width=3
    )

    return imagem


# ============================================================
# EXECUTAR COMANDO
# ============================================================

def executar_comando(comando):

    try:

        subprocess.Popen(
            comando,
            cwd=DIRETORIO,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    except Exception as erro:

        print(
            f"Erro ao executar comando: {erro}"
        )


# ============================================================
# STATUS DO SERVIÇO
# ============================================================

def servico_esta_rodando():

    try:

        resultado = subprocess.run(
            [
                "sc.exe",
                "query",
                SERVICO
            ],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        return (
            "RUNNING"
            in resultado.stdout
        )

    except Exception:

        return False


# ============================================================
# ATUALIZAR TÍTULO
# ============================================================

def atualizar_status(icone):

    if servico_esta_rodando():

        icone.title = (
            "Trilan Backup NVR - "
            "Serviço em execução"
        )

    else:

        icone.title = (
            "Trilan Backup NVR - "
            "Serviço PARADO (backup automático não vai rodar)"
        )


# ============================================================
# THREAD DE MONITORAMENTO
# ============================================================

def monitorar_servico(icone):

    while True:

        try:
            atualizar_status(
                icone
            )
        except Exception:
            # Não deixa o thread de monitoramento morrer
            # silenciosamente e nunca mais atualizar o status.
            pass

        time.sleep(10)


# ============================================================
# EXECUTAR BACKUP AGORA
# ============================================================
#
# IMPORTANTE: esta função SÓ sinaliza o serviço via evento
# nomeado. Ela NÃO roda backup_nvr.py diretamente.
#
# Antes, este código também fazia subprocess.Popen do
# backup_nvr.py aqui, além de sinalizar o evento — isso fazia
# o backup rodar DUAS VEZES em paralelo (uma pelo serviço, outra
# por este processo), com risco real de corrupção porque as duas
# execuções escrevem/apagam a mesma pasta datada ao mesmo tempo.
#
# Consequência desta correção: se o serviço estiver PARADO,
# clicar aqui não faz mais nada acontecer além do aviso de erro
# abaixo — não existe mais um "modo standalone" de fallback.
# Isso é intencional: só deve existir um dono da execução do
# backup (o serviço). Se quiser rodar um backup avulso com o
# serviço parado, rode "py backup_nvr.py" manualmente pelo
# terminal, sabendo que está fora do fluxo controlado.

def executar_backup_agora(
    icone,
    item
):

    try:

        evento = win32event.OpenEvent(
            win32con.EVENT_MODIFY_STATE,
            False,
            EVENTO_BACKUP_MANUAL
        )

        win32event.SetEvent(
            evento
        )

        evento.Close()

        icone.notify(
            "Backup solicitado ao serviço.",
            "Trilan Backup NVR"
        )

    except Exception as erro:

        icone.notify(
            "Não foi possível solicitar o backup. "
            "O serviço está rodando?",
            "Trilan Backup NVR"
        )

        print(
            f"Erro ao solicitar backup: {erro}"
        )


# ============================================================
# ABRIR PASTA DE BACKUP
# ============================================================

def abrir_pasta_backup(
    icone,
    item
):

    try:

        os.startfile(
            PASTA_BACKUP
        )

    except Exception as erro:

        print(
            f"Erro ao abrir pasta: {erro}"
        )


# ============================================================
# ABRIR LOG
# ============================================================

def abrir_log(
    icone,
    item
):

    try:

        if not os.path.exists(
            ARQUIVO_LOG
        ):

            os.makedirs(
                os.path.dirname(
                    ARQUIVO_LOG
                ),
                exist_ok=True
            )

            open(
                ARQUIVO_LOG,
                "a",
                encoding="utf-8"
            ).close()

        subprocess.Popen(
            [
                "notepad.exe",
                ARQUIVO_LOG
            ]
        )

    except Exception as erro:

        print(
            f"Erro ao abrir log: {erro}"
        )


# ============================================================
# INICIAR SERVIÇO
# ============================================================

def iniciar_servico(
    icone,
    item
):

    executar_comando(
        [
            "sc.exe",
            "start",
            SERVICO
        ]
    )


# ============================================================
# PARAR SERVIÇO
# ============================================================

def parar_servico(
    icone,
    item
):

    executar_comando(
        [
            "sc.exe",
            "stop",
            SERVICO
        ]
    )


# ============================================================
# REINICIAR SERVIÇO
# ============================================================

def reiniciar_servico(
    icone,
    item
):

    def reiniciar():

        subprocess.run(
            [
                "sc.exe",
                "stop",
                SERVICO
            ],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        time.sleep(2)

        subprocess.run(
            [
                "sc.exe",
                "start",
                SERVICO
            ],
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    threading.Thread(
        target=reiniciar,
        daemon=True
    ).start()


# ============================================================
# SAIR
# ============================================================

def sair(
    icone,
    item
):

    icone.stop()


# ============================================================
# MENU
# ============================================================

def criar_menu():

    return pystray.Menu(

        item(
            "▶ Executar backup agora",
            executar_backup_agora
        ),

        pystray.Menu.SEPARATOR,

        item(
            "▶ Iniciar serviço",
            iniciar_servico
        ),

        item(
            "■ Parar serviço",
            parar_servico
        ),

        item(
            "↻ Reiniciar serviço",
            reiniciar_servico
        ),

        pystray.Menu.SEPARATOR,

        item(
            "📁 Abrir pasta de backups",
            abrir_pasta_backup
        ),

        item(
            "📄 Abrir log",
            abrir_log
        ),

        pystray.Menu.SEPARATOR,

        item(
            "❌ Sair",
            sair
        )
    )


# ============================================================
# MAIN
# ============================================================
#
# Reinício automático se o ícone da bandeja travar/lançar
# exceção inesperada. icone.run() só retorna normalmente quando
# "Sair" é clicado (icone.stop()) — nesse caso o loop termina
# de propósito. Qualquer outro retorno (exceção) é tratado como
# falha e reinicia o ícone após uma pausa curta, em vez de deixar
# a bandeja sumir silenciosamente.

def main():

    while True:

        try:

            icone = pystray.Icon(
                "TrilanBackupNVR",
                criar_icone(),
                "Trilan Backup NVR",
                criar_menu()
            )

            threading.Thread(
                target=monitorar_servico,
                args=(icone,),
                daemon=True
            ).start()

            icone.run()

            # Chegou aqui só se icone.stop() foi chamado (Sair).
            break

        except Exception as erro:

            print(
                f"Bandeja encontrou um erro inesperado e será "
                f"reiniciada em 5 segundos: {erro}"
            )

            time.sleep(5)


if __name__ == "__main__":

    main()