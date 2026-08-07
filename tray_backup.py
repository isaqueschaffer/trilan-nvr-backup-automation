import os
import sys
import time
import threading
import subprocess
from pathlib import Path

import win32event
import win32con
import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

# ============================================================
# CONFIGURAÇÕES
# ============================================================
DIRETORIO = Path(__file__).resolve().parent
SERVICO = "TrilanBackupNVR"
PASTA_BACKUP = Path(r"C:\BKP_NVR")
ARQUIVO_LOG = DIRETORIO / "logs" / "servico.log"

EVENTO_BACKUP_MANUAL = r"Global\TrilanBackupNVR_RunNow"
NO_WINDOW = subprocess.CREATE_NO_WINDOW

# ============================================================
# INTERFACE GRÁFICA (ÍCONE)
# ============================================================
def criar_icone():
    """Desenha dinamicamente o ícone do NVR na bandeja do Windows."""
    img = Image.new("RGB", (64, 64), "white")
    d = ImageDraw.Draw(img)
    
    # Corpo e discos do NVR
    d.rectangle((10, 10, 54, 25), outline="black", width=3)
    d.rectangle((10, 29, 54, 44), outline="black", width=3)
    d.ellipse((16, 15, 21, 20), fill="green")
    d.ellipse((16, 34, 21, 39), fill="green")
    
    # Seta indicando download/backup
    d.line((28, 48, 28, 58), fill="black", width=3)
    d.line((28, 58, 23, 53), fill="black", width=3)
    d.line((28, 58, 33, 53), fill="black", width=3)
    
    return img

# ============================================================
# CONTROLE DO SERVIÇO (SC.EXE)
# ============================================================
def cmd_servico(acao):
    """Executa um comando de serviço (start/stop) de forma invisível."""
    try:
        subprocess.run(["sc.exe", acao, SERVICO], creationflags=NO_WINDOW)
    except Exception as e:
        print(f"Erro ao executar {acao} no serviço: {e}")

def reiniciar_servico(icone, item):
    def _reiniciar():
        cmd_servico("stop")
        time.sleep(2)
        cmd_servico("start")
    threading.Thread(target=_reiniciar, daemon=True).start()

def servico_esta_rodando():
    try:
        res = subprocess.run(["sc.exe", "query", SERVICO], capture_output=True, text=True, creationflags=NO_WINDOW)
        return "RUNNING" in res.stdout
    except Exception:
        return False

def monitorar_servico(icone):
    """Atualiza o texto exibido ao passar o mouse sobre o ícone."""
    while True:
        try:
            status = "em execução" if servico_esta_rodando() else "PARADO (backup automático não vai rodar)"
            icone.title = f"Trilan Backup NVR - Serviço {status}"
        except Exception:
            pass
        time.sleep(10)

# ============================================================
# AÇÕES DO MENU
# ============================================================
def executar_backup_agora(icone, item):
    try:
        evento = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, EVENTO_BACKUP_MANUAL)
        win32event.SetEvent(evento)
        evento.Close()
        icone.notify("Backup solicitado ao serviço.", "Trilan Backup NVR")
    except Exception as erro:
        icone.notify("Não foi possível solicitar o backup. O serviço está rodando?", "Trilan Backup NVR")
        print(f"Erro ao solicitar backup: {erro}")

def abrir_pasta_backup(icone, item):
    try:
        PASTA_BACKUP.mkdir(parents=True, exist_ok=True)
        os.startfile(PASTA_BACKUP)
    except Exception as e:
        print(f"Erro ao abrir pasta: {e}")

def abrir_log(icone, item):
    try:
        ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
        if not ARQUIVO_LOG.exists():
            ARQUIVO_LOG.touch()
        subprocess.Popen(["notepad.exe", str(ARQUIVO_LOG)])
    except Exception as e:
        print(f"Erro ao abrir log: {e}")

# ============================================================
# MENU E LOOP PRINCIPAL
# ============================================================
def criar_menu():
    return pystray.Menu(
        item("▶ Executar backup agora", executar_backup_agora),
        pystray.Menu.SEPARATOR,
        item("▶ Iniciar serviço", lambda i, j: cmd_servico("start")),
        item("■ Parar serviço", lambda i, j: cmd_servico("stop")),
        item("↻ Reiniciar serviço", reiniciar_servico),
        pystray.Menu.SEPARATOR,
        item("📁 Abrir pasta de backups", abrir_pasta_backup),
        item("📄 Abrir log", abrir_log),
        pystray.Menu.SEPARATOR,
        item("❌ Sair", lambda i, j: i.stop())
    )

def main():
    while True:
        try:
            icone = pystray.Icon("TrilanBackupNVR", criar_icone(), "Trilan Backup NVR", criar_menu())
            
            # Inicia o monitor de status em segundo plano
            threading.Thread(target=monitorar_servico, args=(icone,), daemon=True).start()
            
            # Bloqueia a execução mantendo o ícone ativo
            icone.run()
            break  # Só chega aqui se o usuário clicar em "Sair" (icone.stop())
            
        except Exception as e:
            print(f"Bandeja encontrou um erro inesperado e será reiniciada em 5s: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()