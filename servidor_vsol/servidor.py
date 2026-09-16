from flask import Flask, request, make_response, redirect
from pathlib import Path
import logging

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

USUARIO = "admin"
SENHA = "admin123"

BASE_DIR = Path(__file__).resolve().parent

ARQUIVO_BACKUP = BASE_DIR / "usrcfg.conf"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "vsol_teste.log"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logging.info("=" * 60)
logging.info("SERVIDOR VSOL DE TESTE INICIADO")
logging.info(f"Arquivo de backup: {ARQUIVO_BACKUP}")
logging.info(f"Arquivo de log: {LOG_FILE}")
logging.info("=" * 60)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    logging.info(
        f"[HTTP] Acesso à página inicial - "
        f"IP={request.remote_addr}"
    )

    return """
    <html>
        <body>
            <h1>VSOL OLT TESTE</h1>
            <p>Servidor de teste funcionando.</p>
        </body>
    </html>
    """


# ============================================================
# LOGIN
# ============================================================

@app.route("/action/login.html", methods=["GET", "POST"])
def login():

    if request.method == "GET":

        logging.info(
            f"[LOGIN] Página de login acessada - "
            f"IP={request.remote_addr}"
        )

        return """
        <html>
            <body>
                <h1>Login VSOL</h1>

                <form method="post">
                    <input name="user">
                    <input name="pass" type="password">
                    <button type="submit">Login</button>
                </form>

            </body>
        </html>
        """

    usuario = request.form.get("user")
    senha = request.form.get("pass")

    logging.info(
        f"[LOGIN] Tentativa de login - "
        f"usuario={usuario} "
        f"IP={request.remote_addr}"
    )

    if usuario == USUARIO and senha == SENHA:

        logging.info(
            f"[LOGIN] LOGIN REALIZADO COM SUCESSO - "
            f"usuario={usuario} "
            f"IP={request.remote_addr}"
        )

        resposta = make_response(
            redirect("/action/main.html")
        )

        resposta.set_cookie(
            "vsol_session",
            "teste-autenticado"
        )

        return resposta

    logging.warning(
        f"[LOGIN] LOGIN NEGADO - "
        f"usuario={usuario} "
        f"IP={request.remote_addr}"
    )

    return "login_error", 401


# ============================================================
# MAIN
# ============================================================

@app.route("/action/main.html")
def main():

    autenticado = (
        request.cookies.get("vsol_session")
        == "teste-autenticado"
    )

    if not autenticado:

        logging.warning(
            f"[MAIN] Acesso sem autenticação - "
            f"IP={request.remote_addr}"
        )

        return "login_error", 401

    logging.info(
        f"[MAIN] Acesso autorizado - "
        f"IP={request.remote_addr}"
    )

    return """
    <html>
        <body>
            <h1>VSOL OLT TESTE</h1>
            <p>Login realizado com sucesso.</p>
            <p>Modelo: V1600D</p>
            <p>Status: Online</p>
        </body>
    </html>
    """


# ============================================================
# DOWNLOAD DO BACKUP
# ============================================================

@app.route("/usrcfg.conf")
def backup():

    autenticado = (
        request.cookies.get("vsol_session")
        == "teste-autenticado"
    )

    if not autenticado:

        logging.warning(
            f"[BACKUP] Tentativa de download sem login - "
            f"IP={request.remote_addr}"
        )

        return "login_error", 401

    logging.info(
        f"[BACKUP] Solicitação de backup recebida - "
        f"IP={request.remote_addr}"
    )

    if not ARQUIVO_BACKUP.exists():

        logging.error(
            f"[BACKUP] Arquivo não encontrado: "
            f"{ARQUIVO_BACKUP}"
        )

        return "Arquivo de configuração não encontrado.", 404

    conteudo = ARQUIVO_BACKUP.read_bytes()

    tamanho = len(conteudo)

    logging.info(
        f"[BACKUP] Arquivo carregado - "
        f"tamanho={tamanho} bytes"
    )

    resposta = make_response(conteudo)

    resposta.headers["Content-Type"] = (
        "application/octet-stream"
    )

    resposta.headers["Content-Disposition"] = (
        "attachment; filename=usrcfg.conf"
    )

    logging.info(
        "[BACKUP] DOWNLOAD REALIZADO COM SUCESSO"
    )

    return resposta


# ============================================================
# DOWNLOAD ALTERNATIVO
# ============================================================

@app.route("/action/usrcfg.conf")
def backup_action():

    logging.info(
        f"[BACKUP] Endpoint /action/usrcfg.conf acessado - "
        f"IP={request.remote_addr}"
    )

    return backup()


# ============================================================
# SERVIDOR
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("VSOL OLT DE TESTE")
    print("=" * 50)
    print("IP:       127.0.0.1")
    print("Porta:    8080")
    print("Usuário:  admin")
    print("Senha:    admin123")
    print(f"Log:      {LOG_FILE}")
    print("=" * 50)

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False
    )
