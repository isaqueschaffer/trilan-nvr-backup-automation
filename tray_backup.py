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
# CONFIGURAÇÕES (Com proteção para o .EXE)
# ============================================================
if getattr(sys, 'frozen', False):
    DIRETORIO = Path(sys.executable).parent
else:
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
    img = Image.new("RGB", (64, 64), "white")
    d = ImageDraw.Draw(img)
    
    d.rectangle((10, 10, 54, 25), outline="black", width=3)
    d.rectangle((10, 29, 54, 44), outline="black", width=3)
    d.ellipse((16, 15, 21, 20), fill="green")
    d.ellipse((16, 34, 21, 39), fill="green")
    
    d.line((28, 48, 28, 58), fill="black", width=3)
    d.line((28, 58, 23, 53), fill="black", width=3)
    d.line((28, 58, 33, 53), fill="black", width=3)
    return img

# ============================================================
# CONTROLE DO SERVIÇO (SC.EXE)
# ============================================================
def cmd_servico(acao, icone):
    try:
        rodando = servico_esta_rodando()
        
        # 1. Evita disparar comando (e erro) se o serviço já estiver no estado desejado
        if acao == "start" and rodando:
            icone.notify("O serviço já está em execução.", "Trilan Backup NVR")
            return
        if acao == "stop" and not rodando:
            icone.notify("O serviço já está parado.", "Trilan Backup NVR")
            return

        # 2. Executa o comando (usando capture_output no lugar de DEVNULL para evitar telas)
        res = subprocess.run(
            ["sc.exe", acao, SERVICO], 
            creationflags=NO_WINDOW,
            capture_output=True,
            text=True
        )
        
        # 3. Se deu erro agora, é quase certeza que é falta de permissão (Administrador)
        if res.returncode != 0:
            icone.notify("Falha de permissão. Execute a bandeja como Administrador.", "Acesso Negado")
        else:
            # 4. Mensagem de sucesso para você saber que funcionou
            texto_acao = "iniciado" if acao == "start" else "parado"
            icone.notify(f"Serviço {texto_acao} com sucesso.", "Trilan Backup NVR")
            
    except Exception as e:
        icone.notify(f"Erro ao controlar serviço: {e}", "Erro")

def reiniciar_servico(icone, item):
    def _reiniciar():
        cmd_servico("stop", icone)
        time.sleep(2)
        cmd_servico("start", icone)
    threading.Thread(target=_reiniciar, daemon=True).start()

def servico_esta_rodando():
    try:
        res = subprocess.run(
            ["sc.exe", "query", SERVICO], 
            capture_output=True, 
            text=True, 
            creationflags=NO_WINDOW,
            stdin=subprocess.DEVNULL
        )
        return "RUNNING" in res.stdout
    except Exception:
        return False

def monitorar_servico(icone):
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

def abrir_pasta_backup(icone, item):
    try:
        PASTA_BACKUP.mkdir(parents=True, exist_ok=True)
        os.startfile(PASTA_BACKUP)
    except Exception as e:
        icone.notify(f"Erro ao abrir pasta: {e}", "Erro")

def abrir_log(icone, item):
    try:
        ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
        if not ARQUIVO_LOG.exists():
            ARQUIVO_LOG.touch()
        
        # Popen com DEVNULL isola o notepad do executável invisível
        subprocess.Popen(
            ["notepad.exe", str(ARQUIVO_LOG)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        icone.notify(f"Erro ao abrir log: {e}", "Erro")

# ============================================================
# MENU E LOOP PRINCIPAL
# ============================================================
def criar_menu():
    return pystray.Menu(
        item("▶ Executar backup agora", executar_backup_agora),
        pystray.Menu.SEPARATOR,
        item("▶ Iniciar serviço", lambda i, j: cmd_servico("start", i)),
        item("■ Parar serviço", lambda i, j: cmd_servico("stop", i)),
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
            threading.Thread(target=monitorar_servico, args=(icone,), daemon=True).start()
            icone.run()
            break
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    main()