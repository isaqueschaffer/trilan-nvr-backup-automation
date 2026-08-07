import os
import sys
import json
import time
import shutil
import hashlib
import base64
import smtplib
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage

# Tamanho máximo seguro de anexo (bytes) antes de codificação base64.
# Gmail limita mensagens a 25MB após base64 (~37% de inflação),
# então o arquivo bruto precisa ficar bem abaixo disso.
LIMITE_ANEXO_BYTES = 20 * 1024 * 1024  # 20 MB

import requests
from requests.auth import HTTPDigestAuth
import pyzipper


# ============================================================
# CAMINHOS DE CONFIGURAÇÃO
# ============================================================

DIRETORIO_SCRIPT = Path(__file__).resolve().parent

ARQUIVO_CONFIG = DIRETORIO_SCRIPT / "config.json"
ARQUIVO_EMAIL = DIRETORIO_SCRIPT / "config_email.json"

# Chave AES fixa usada pelo WebSDK Hikvision para cifrar o
# parâmetro secretkey do endpoint /ISAPI/System/configurationData.
# NÃO é segredo do cliente — é constante do protocolo do fabricante.
AES_KEY_HEX = "bf8a6df8640f38f3812c19d2aaca7743"

TIMEOUT = 60

LOG_FILE = None


# ============================================================
# CARGA E VALIDAÇÃO DE CONFIG
# ============================================================

def carregar_json(caminho, nome):
    if not caminho.exists():
        print(f"\n❌ ERRO: {nome} não encontrado em {caminho}\n")
        sys.exit(1)

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as erro:
        print(f"\n❌ ERRO ao ler {nome}: {erro}\n")
        sys.exit(1)


def carregar_config():
    config = carregar_json(ARQUIVO_CONFIG, "config.json")

    obrigatorios = ["cliente", "pasta_backup", "senha_encriptacao", "nvrs"]
    for campo in obrigatorios:
        if campo not in config:
            print(f"❌ ERRO: campo '{campo}' ausente em config.json.")
            sys.exit(1)

    if not config["nvrs"]:
        print("❌ ERRO: nenhum NVR configurado.")
        sys.exit(1)

    for nvr in config["nvrs"]:
        for campo in ["nome", "ip", "usuario", "senha"]:
            if campo not in nvr:
                print(f"❌ ERRO: campo '{campo}' ausente em um NVR de config.json.")
                sys.exit(1)

    return config


def carregar_config_email():
    config = carregar_json(ARQUIVO_EMAIL, "config_email.json")

    obrigatorios = ["smtp_server", "smtp_port", "email", "senha_app", "destinatarios"]
    for campo in obrigatorios:
        if campo not in config:
            print(f"❌ ERRO: campo '{campo}' ausente em config_email.json.")
            sys.exit(1)

    if isinstance(config["destinatarios"], str):
        config["destinatarios"] = [config["destinatarios"]]

    return config


# ============================================================
# LOG
# ============================================================

def log(mensagem):
    print(mensagem)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}\n")
        except Exception:
            pass


# ============================================================
# UTILITÁRIOS
# ============================================================

def sha256_arquivo(caminho):
    sha256 = hashlib.sha256()
    with open(caminho, "rb") as f:
        while True:
            bloco = f.read(1024 * 1024)
            if not bloco:
                break
            sha256.update(bloco)
    return sha256.hexdigest()


def tamanho_kb(caminho):
    return os.path.getsize(caminho) / 1024


def data_pasta():
    return datetime.now().strftime("%d-%m-%Y")


# ============================================================
# SECRETKEY (protocolo Hikvision WebSDK)
# ============================================================

def gerar_secretkey_e_iv(senha_encriptacao):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    timestamp = str(int(time.time() * 1000))
    iv = hashlib.md5(timestamp.encode("utf-8")).hexdigest()

    senha_escapada = (
        senha_encriptacao
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    texto = base64.b64encode(senha_escapada.encode("utf-8"))

    chave = bytes.fromhex(AES_KEY_HEX)
    iv_bytes = bytes.fromhex(iv)

    cipher = AES.new(chave, AES.MODE_CBC, iv_bytes)
    encrypted = cipher.encrypt(pad(texto, AES.block_size))

    return encrypted.hex(), iv


# ============================================================
# TESTE DE CONECTIVIDADE
# ============================================================

def testar_nvr(ip, usuario, senha):
    url = f"http://{ip}/ISAPI/System/status"
    try:
        resposta = requests.get(
            url, auth=HTTPDigestAuth(usuario, senha), timeout=10
        )
        return resposta.status_code in (200, 401)
    except Exception:
        return False


# ============================================================
# BACKUP CONFIG NVR (.bin)
# ============================================================

def backup_config_nvr(ip, usuario, senha, senha_encriptacao, pasta_destino):
    log("Gerando secretkey...")
    secretkey, iv = gerar_secretkey_e_iv(senha_encriptacao)
    log(f"IV: {iv}")
    log("Secretkey gerada.")

    url = (
        f"http://{ip}/ISAPI/System/configurationData"
        f"?secretkey={secretkey}&security=1&iv={iv}"
    )

    arquivo = pasta_destino / f"CONFIG_NVR_{data_pasta()}.bin"

    log("")
    log("Baixando configuração...")

    try:
        resposta = requests.get(
            url, auth=HTTPDigestAuth(usuario, senha), timeout=TIMEOUT, stream=True
        )
        log(f"HTTP: {resposta.status_code}")

        if resposta.status_code != 200:
            log(f"ERRO HTTP: {resposta.status_code}")
            return None

        with open(arquivo, "wb") as f:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                if bloco:
                    f.write(bloco)

        tamanho = os.path.getsize(arquivo)
        log(f"Bytes recebidos: {tamanho:,}")

        with open(arquivo, "rb") as f:
            primeiros = f.read(500)

        if b"<ResponseStatus" in primeiros:
            log("ERRO: NVR devolveu XML de erro em vez do backup.")
            arquivo.unlink(missing_ok=True)
            return None

        if tamanho < 100000:
            log("ERRO: backup muito pequeno (provável falha de autenticação/chave).")
            arquivo.unlink(missing_ok=True)
            return None

        hash_sha256 = sha256_arquivo(arquivo)
        log(f"Tamanho: {tamanho_kb(arquivo):,.2f} KB")
        log(f"SHA-256: {hash_sha256}")

        return {
            "arquivo": str(arquivo),
            "nome": arquivo.name,
            "tamanho": tamanho,
            "tamanho_kb": round(tamanho_kb(arquivo), 2),
            "sha256": hash_sha256,
        }

    except requests.exceptions.Timeout:
        log("ERRO: timeout.")
    except requests.exceptions.ConnectionError:
        log("ERRO: não foi possível conectar.")
    except Exception as e:
        log(f"ERRO: {type(e).__name__}: {e}")

    return None


# ============================================================
# BACKUP IPCAM (.xls)
# ============================================================

def backup_ipcam(ip, usuario, senha, pasta_destino):
    url = f"http://{ip}/ISAPI/ContentMgmt/InputProxy/ipcConfig"
    arquivo = pasta_destino / f"CONFIG_IPCAM_{data_pasta()}.xls"

    log("")
    log("Baixando parâmetros das câmeras IP...")

    try:
        resposta = requests.get(url, auth=HTTPDigestAuth(usuario, senha), timeout=TIMEOUT)
        log(f"HTTP IPCAM: {resposta.status_code}")

        if resposta.status_code != 200:
            log(f"ERRO IPCAM HTTP: {resposta.status_code}")
            return None

        conteudo = resposta.content
        if not conteudo:
            log("ERRO: resposta vazia.")
            return None

        with open(arquivo, "wb") as f:
            f.write(conteudo)

        tamanho = os.path.getsize(arquivo)
        hash_sha256 = sha256_arquivo(arquivo)

        log(f"IPCAM recebido: {tamanho:,} bytes")
        log(f"SHA-256 IPCAM: {hash_sha256}")

        return {
            "arquivo": str(arquivo),
            "nome": arquivo.name,
            "tamanho": tamanho,
            "tamanho_kb": round(tamanho_kb(arquivo), 2),
            "sha256": hash_sha256,
        }

    except Exception as e:
        log(f"ERRO IPCAM: {type(e).__name__}: {e}")

    return None


# ============================================================
# PROCESSAR UM NVR
# ============================================================

def processar_nvr(nvr, senha_encriptacao, pasta_data):
    nome = nvr["nome"]
    ip = nvr["ip"]
    usuario = nvr["usuario"]
    senha = nvr["senha"]

    log("")
    log("=" * 60)
    log(nome)
    log(f"IP: {ip}")
    log("=" * 60)

    pasta_nvr = pasta_data / nome.replace(" ", "_")
    pasta_nvr.mkdir(parents=True, exist_ok=True)

    log("Testando conectividade...")
    if not testar_nvr(ip, usuario, senha):
        log("❌ NVR inacessível.")
        return {"nome": nome, "ip": ip, "status": "ERRO", "erro": "NVR inacessível", "arquivos": []}

    log("NVR acessível.")

    arquivos = []

    resultado_nvr = backup_config_nvr(ip, usuario, senha, senha_encriptacao, pasta_nvr)
    if resultado_nvr:
        arquivos.append(resultado_nvr)
        log("✅ Backup NVR concluído.")
    else:
        log("❌ Falha no backup NVR.")

    resultado_ipcam = backup_ipcam(ip, usuario, senha, pasta_nvr)
    if resultado_ipcam:
        arquivos.append(resultado_ipcam)
        log("✅ Backup IPCAM concluído.")
    else:
        log("❌ Falha no backup IPCAM.")

    if len(arquivos) == 2:
        status = "OK"
    elif len(arquivos) == 1:
        status = "PARCIAL"
    else:
        status = "ERRO"

    return {"nome": nome, "ip": ip, "status": status, "arquivos": arquivos}


# ============================================================
# RELATÓRIO
# ============================================================

def salvar_relatorio(cliente, resultados, pasta_data):
    relatorio = {
        "cliente": cliente,
        "data": datetime.now().isoformat(),
        "resultados": resultados,
    }
    arquivo = pasta_data / "relatorio_backup.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=4, ensure_ascii=False)
    return arquivo


# ============================================================
# ZIP COM SENHA (AES-256 via pyzipper)
# ============================================================

def criar_zip(pasta_data, cliente, senha_zip):
    nome_zip = f"BACKUP_{cliente.upper()}_{data_pasta()}.zip"
    arquivo_zip = pasta_data / nome_zip

    log("")
    log("=" * 60)
    log("COMPACTANDO BACKUP")
    log("=" * 60)

    try:
        with pyzipper.AESZipFile(
            arquivo_zip, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as zip_file:
            zip_file.setpassword(senha_zip.encode("utf-8"))

            for arquivo in pasta_data.rglob("*"):
                if not arquivo.is_file():
                    continue
                if arquivo == arquivo_zip:
                    continue
                if arquivo.name in ("backup.log", "relatorio_backup.json"):
                    continue

                caminho_relativo = arquivo.relative_to(pasta_data)
                log(f"Adicionando: {caminho_relativo}")
                zip_file.write(arquivo, arcname=str(caminho_relativo))

        tamanho = tamanho_kb(arquivo_zip)
        hash_sha256 = sha256_arquivo(arquivo_zip)

        log("")
        log("✅ ZIP criado.")
        log(f"Tamanho: {tamanho:,.2f} KB")
        log(f"SHA-256 ZIP: {hash_sha256}")

        return {
            "arquivo": str(arquivo_zip),
            "nome": arquivo_zip.name,
            "tamanho_kb": round(tamanho, 2),
            "sha256": hash_sha256,
        }

    except Exception as e:
        log(f"❌ Erro ao criar ZIP: {type(e).__name__}: {e}")
        return None


def verificar_zip(arquivo_zip, senha_zip):
    log("")
    log("Verificando ZIP...")
    try:
        with pyzipper.AESZipFile(arquivo_zip, "r") as zip_file:
            zip_file.setpassword(senha_zip.encode("utf-8"))
            arquivos = zip_file.namelist()
            for nome in arquivos:
                with zip_file.open(nome) as f:
                    while f.read(1024 * 1024):
                        pass
        log("✅ ZIP íntegro.")
        log(f"Arquivos no ZIP: {len(arquivos)}")
        return True
    except Exception as e:
        log(f"❌ Falha na verificação do ZIP: {e}")
        return False


# ============================================================
# ENVIO DE E-MAIL (genérico, via config_email.json)
# ============================================================

def enviar_email(caminho_zip, caminho_relatorio, cliente, resultados, config_email):
    log("")
    log("=" * 60)
    log("ENVIO DO BACKUP POR E-MAIL")
    log("=" * 60)

    remetente = config_email["email"]
    senha_app = config_email["senha_app"]
    destinatarios = config_email["destinatarios"]
    smtp_server = config_email["smtp_server"]
    smtp_port = int(config_email["smtp_port"])

    data = datetime.now().strftime("%d-%m-%Y")
    assunto = f"Backup NVR - {cliente} - {data}"

    linhas_status = "\n".join(
        f"  {r['nome']}: {r['status']}" for r in resultados
    )

    corpo = f"""Backup automático de NVR concluído.

Cliente: {cliente}
Data: {data}

Status por NVR:
{linhas_status}

O arquivo ZIP protegido com senha está anexado.
Este e-mail foi enviado automaticamente pelo sistema de backup.
"""

    tamanho_zip = os.path.getsize(caminho_zip)
    anexar = tamanho_zip <= LIMITE_ANEXO_BYTES

    if not anexar:
        log(
            f"⚠️ ZIP tem {tamanho_zip / (1024*1024):.2f} MB, acima do limite "
            f"seguro de {LIMITE_ANEXO_BYTES / (1024*1024):.0f} MB para anexo. "
            f"E-mail será enviado SEM anexo, apenas com o caminho do arquivo."
        )
        corpo += (
            f"\nATENÇÃO: o ZIP tem {tamanho_zip / (1024*1024):.2f} MB e excede "
            f"o limite seguro de anexo por e-mail. O arquivo NÃO foi anexado.\n"
            f"Caminho local do ZIP: {caminho_zip}\n"
        )

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(destinatarios)
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    if anexar:
        try:
            with open(caminho_zip, "rb") as f:
                dados = f.read()
            mensagem.add_attachment(
                dados, maintype="application", subtype="zip",
                filename=os.path.basename(caminho_zip),
            )
        except Exception as erro:
            log(f"❌ ERRO ao anexar ZIP: {erro}")
            return False

    # Timeout generoso: precisa cobrir o tempo de UPLOAD do anexo inteiro,
    # não só o handshake. 300s dá margem para até redes lentas com anexos
    # próximos do limite (~20MB).
    servidor = None
    try:
        log(f"Conectando a {smtp_server}:{smtp_port}...")
        servidor = smtplib.SMTP(smtp_server, smtp_port, timeout=300)
        servidor.ehlo()
        servidor.starttls()
        servidor.ehlo()
        log("Autenticando...")
        servidor.login(remetente, senha_app)
        log("Enviando e-mail (isso pode demorar dependendo do tamanho do anexo)...")
        servidor.send_message(mensagem)

        log("✅ E-mail enviado com sucesso.")
        for destinatario in destinatarios:
            log(f"  Destinatário: {destinatario}")
        return True

    except Exception as erro:
        log(f"❌ ERRO AO ENVIAR E-MAIL: {type(erro).__name__}: {erro}")
        return False

    finally:
        if servidor is not None:
            try:
                servidor.quit()
            except Exception:
                # Conexão já pode estar morta (ex: após timeout no envio).
                # Ignorar aqui evita que o erro de limpeza mascare o erro
                # real que já foi logado acima.
                pass


# ============================================================
# MAIN
# ============================================================

def main():
    global LOG_FILE

    config = carregar_config()
    config_email = carregar_config_email()

    cliente = config["cliente"]
    pasta_backup = Path(config["pasta_backup"])
    senha_encriptacao = config["senha_encriptacao"]
    nvrs = config["nvrs"]

    pasta_data = pasta_backup / data_pasta()

    if pasta_data.exists():
        print(f"Pasta do dia já existe ({pasta_data}). Limpando antes de iniciar...")
        shutil.rmtree(pasta_data)

    pasta_data.mkdir(parents=True, exist_ok=True)

    LOG_FILE = pasta_data / "backup.log"

    print()
    print("=" * 60)
    print("BACKUP AUTOMÁTICO DE NVR")
    print("=" * 60)
    print(f"Cliente : {cliente}")
    print(f"Data    : {data_pasta()}")
    print(f"Pasta   : {pasta_data}")
    print(f"NVRs    : {len(nvrs)}")
    print("=" * 60)

    inicio = time.time()
    resultados = []

    for nvr in nvrs:
        resultado = processar_nvr(nvr, senha_encriptacao, pasta_data)
        resultados.append(resultado)

    caminho_relatorio = salvar_relatorio(cliente, resultados, pasta_data)
    log("")
    log(f"Relatório: {caminho_relatorio}")

    # Senha do ZIP: reaproveita senha_encriptacao (config.json tem só este campo).
    # Se algum cliente precisar de senha de ZIP diferente da senha de
    # criptografia do backup, adicionar campo "senha_zip" ao config.json.
    zip_resultado = criar_zip(pasta_data, cliente, senha_encriptacao)

    zip_ok = False
    if zip_resultado:
        zip_ok = verificar_zip(zip_resultado["arquivo"], senha_encriptacao)

    tempo = time.time() - inicio
    total = len(resultados)
    sucesso = sum(1 for r in resultados if r["status"] == "OK")
    parcial = sum(1 for r in resultados if r["status"] == "PARCIAL")
    erro = sum(1 for r in resultados if r["status"] == "ERRO")

    print()
    print("=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)

    for resultado in resultados:
        simbolo = {"OK": "✅", "PARCIAL": "⚠️", "ERRO": "❌"}[resultado["status"]]
        print(f"{simbolo} {resultado['nome']:<10} {resultado['status']}")

    print()
    print(f"Total NVRs : {total}")
    print(f"Sucesso    : {sucesso}")
    print(f"Parcial    : {parcial}")
    print(f"Erro       : {erro}")
    print(f"ZIP        : {'✅ OK' if zip_ok else '❌ ERRO'}")
    print(f"Tempo      : {tempo:.2f} segundos")

    if not zip_resultado:
        print()
        print("❌ Backup concluído, mas o ZIP não foi criado. E-mail não será enviado.")
        return

    email_ok = enviar_email(
        zip_resultado["arquivo"], caminho_relatorio, cliente, resultados, config_email
    )

    print()
    print("=" * 60)
    if email_ok:
        print("✅ BACKUP FINALIZADO E ENVIADO POR E-MAIL")
    else:
        print("⚠️ BACKUP FINALIZADO, MAS O E-MAIL NÃO FOI ENVIADO")
    print("=" * 60)
    print(f"\nZIP: {zip_resultado['arquivo']}\n")


if __name__ == "__main__":
    main()
