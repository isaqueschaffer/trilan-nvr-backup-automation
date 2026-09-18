# -*- coding: utf-8 -*-
import re
import requests

# Desativa avisos de certificado SSL usando o urllib3 embutido no requests
requests.packages.urllib3.disable_warnings()

HOST = "https://192.168.12.2"
SESSION_COOKIE = "vsflvhpc50jv9n7qoqf73jje96"  # Insira seu cookie de sessao ativo aqui

USER = "admin"
PASSWORD = "sua_senha_aqui"


def login(session):
    """Autentica no Issabel caso o cookie expire."""
    login_url = "%s/index.php" % HOST
    payload = {
        "input_user": USER,
        "input_pass": PASSWORD,
        "submit_login": "Submit"
    }
    resp = session.post(login_url, data=payload, verify=False)
    return "menu=backup_restore" in resp.text or resp.status_code == 200


def disparar_backup(session):
    """Dispara a criacao do backup completo e retorna o nome do arquivo .tar gerado."""
    backup_url = "%s/index.php?menu=backup_restore" % HOST

    payload = {
        "process": "Executar",
        "backup_total": "on",
        "backup_endpoint": "on",
        "ep_db": "ep_db",
        "ep_config_files": "ep_config_files",
        "backup_fax": "on",
        "fx_db": "fx_db",
        "fx_pdf": "fx_pdf",
        "backup_email": "on",
        "em_db": "em_db",
        "em_mailbox": "em_mailbox",
        "backup_asterisk": "on",
        "as_db": "as_db",
        "as_config_files": "as_config_files",
        "as_monitor": "as_monitor",
        "as_voicemail": "as_voicemail",
        "as_sounds": "as_sounds",
        "as_mohmp3": "as_mohmp3",
        "as_dahdi": "as_dahdi",
        "backup_others": "on",
        "sugar_db": "sugar_db",
        "vtiger_db": "vtiger_db",
        "a2billing_db": "a2billing_db",
        "mysql_db": "mysql_db",
        "menus_permissions": "menus_permissions",
        "backup_others_new": "on",
        "calendar_db": "calendar_db",
        "address_db": "address_db",
        "conference_db": "conference_db",
        "eop_db": "eop_db",
        "option_url": "backup",
        "backup_file": ""
    }

    print "[*] Disparando a criacao do backup no servidor..."
    resp = session.post(backup_url, data=payload, verify=False, timeout=600)

    # 1. Tenta achar o nome do arquivo diretamente pelo padrão do Issabel no HTML retornado
    match = re.search(r"(issabelbackup-\d{14}-v\d+\.tar)", resp.text)
    if match:
        return match.group(1)

    # 2. Alternativa via regex no link de download (substitui o BeautifulSoup)
    link_match = re.search(r"file_name=(issabelbackup-[^&\"']+)", resp.text)
    if link_match:
        return link_match.group(1)

    raise ValueError("Nao foi possivel identificar o nome do arquivo gerado no retorno da pagina.")


def baixar_backup(session, filename):
    """Realiza o download em blocos do arquivo gerado."""
    download_url = (
        "%s/index.php?menu=backup_restore"
        "&action=download_file&file_name=%s&rawmode=yes" % (HOST, filename)
    )

    print "[*] Iniciando download de: %s" % filename
    resp = session.get(download_url, stream=True, verify=False)
    try:
        resp.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    finally:
        resp.close()
    print "[+] Download concluido com sucesso: %s" % filename


def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "%s/index.php?menu=backup_restore" % HOST
    })

    s.cookies.set("issabelSession", SESSION_COOKIE)
    s.cookies.set("lang", "pt_BR")

    try:
        nome_arquivo = disparar_backup(s)
        print "[+] Backup gerado com sucesso: %s" % nome_arquivo
        baixar_backup(s, nome_arquivo)
    except Exception as e:
        print "[-] Erro durante o processo: %s" % str(e)


if __name__ == "__main__":
    main()