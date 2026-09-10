# -*- coding: utf-8 -*-

import os
import re
import shutil
import datetime

try:
    import tkinter as tk
    from tkinter import messagebox as tkMessageBox
    from tkinter import filedialog
except ImportError:
    import Tkinter as tk
    import tkMessageBox
    import tkFileDialog as filedialog


# ============================================================
# CONFIGURACAO
# ============================================================

PASTA_BACKUP = r"C:\Users\Helena\Documents"

ARQUIVO_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agente_unm.log"
)


# ============================================================
# LOCALIZAR ONEDRIVE
# ============================================================

def encontrar_onedrive():

    candidatos = [
        os.environ.get("OneDriveCommercial"),
        os.environ.get("OneDrive"),
        os.environ.get("OneDriveConsumer")
    ]

    for caminho in candidatos:

        if caminho and os.path.isdir(caminho):

            return os.path.abspath(caminho)

    return None


# ============================================================
# LOG
# ============================================================

def registrar_log(mensagem):

    agora = datetime.datetime.now()

    data_hora = agora.strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    linha = "[{}] {}\n".format(
        data_hora,
        mensagem
    )

    try:

        arquivo = open(
            ARQUIVO_LOG,
            "a"
        )

        arquivo.write(linha)
        arquivo.close()

    except Exception:
        pass

    print(linha.strip())


# ============================================================
# IDENTIFICA DATA/HORA DO BACKUP
# ============================================================

def extrair_data_backup(nome_arquivo):

    """
    Procura dentro do nome:

        YYYYMMDD_HHMMSS

    Exemplos:

        20260910_030154_allback.zip

        backup_agerip_20260910_030154_allback.zip

        UNM_backup_20260910_030154.zip
    """

    padrao = r'(\d{8})_(\d{6})'

    resultado = re.search(
        padrao,
        nome_arquivo
    )

    if not resultado:
        return None

    data_str = resultado.group(1)
    hora_str = resultado.group(2)

    try:

        return datetime.datetime.strptime(
            data_str + "_" + hora_str,
            "%Y%m%d_%H%M%S"
        )

    except ValueError:

        return None


# ============================================================
# LOCALIZAR BACKUPS
# ============================================================

def encontrar_backups(pasta_origem=None):

    if not pasta_origem:
        pasta_origem = PASTA_BACKUP

    backups = []

    if not os.path.isdir(pasta_origem):

        registrar_log(
            "ERRO: pasta de origem nao existe: {}".format(
                pasta_origem
            )
        )

        return backups

    extensoes = [
        ".zip",
        ".tar",
        ".gz",
        ".7z"
    ]

    for nome in os.listdir(pasta_origem):

        caminho = os.path.join(
            pasta_origem,
            nome
        )

        if not os.path.isfile(caminho):
            continue

        extensao = os.path.splitext(
            nome
        )[1].lower()

        if extensao not in extensoes:
            continue

        data_backup = extrair_data_backup(
            nome
        )

        if data_backup is None:
            continue

        backups.append({
            "nome": nome,
            "caminho": caminho,
            "data": data_backup
        })

    backups.sort(
        key=lambda x: x["data"],
        reverse=True
    )

    return backups


# ============================================================
# NOVO NOME DO ARQUIVO
# ============================================================

def novo_nome(nome_original):

    resultado = re.search(
        r'(\d{8})_(\d{6})',
        nome_original
    )

    if not resultado:

        raise Exception(
            "Formato de backup desconhecido:\n{}".format(
                nome_original
            )
        )

    data_str = resultado.group(1)
    hora_str = resultado.group(2)

    data_backup = datetime.datetime.strptime(
        data_str + "_" + hora_str,
        "%Y%m%d_%H%M%S"
    )

    # Mantemos ZIP como formato final,
    # conforme o padrão desejado.
    return data_backup.strftime(
        "%d-%m-%Y_%H_%M_%S.zip"
    )


# ============================================================
# CRIAR PASTA DO CLIENTE
# ============================================================

def criar_pasta_cliente(caminho_cliente):

    pasta_onedrive = encontrar_onedrive()

    if not pasta_onedrive:

        raise Exception(
            "Nao foi possivel localizar o OneDrive nesta maquina."
        )

    registrar_log(
        "OneDrive encontrado: {}".format(
            pasta_onedrive
        )
    )

    caminho_cliente = caminho_cliente.strip()

    caminho_cliente = caminho_cliente.replace(
        "/",
        "\\"
    )

    # --------------------------------------------------------
    # Aceita:
    #
    # Cliente
    # /Cliente
    # /OneDrive/Cliente
    # /One Drive/Cliente
    # --------------------------------------------------------

    prefixos = [
        "OneDrive\\",
        "One Drive\\"
    ]

    for prefixo in prefixos:

        if caminho_cliente.lower().startswith(
            prefixo.lower()
        ):

            caminho_cliente = caminho_cliente[
                len(prefixo):
            ]

            break

    caminho_cliente = caminho_cliente.strip(
        "\\/"
    )

    if not caminho_cliente:

        raise Exception(
            "Nome do cliente nao foi informado."
        )

    # --------------------------------------------------------
    # Protecao contra ..
    # --------------------------------------------------------

    partes = caminho_cliente.split("\\")

    for parte in partes:

        if parte == "..":

            raise Exception(
                "Caminho invalido."
            )

    # --------------------------------------------------------
    # Caminho completo
    # --------------------------------------------------------

    pasta_cliente = os.path.join(
        pasta_onedrive,
        caminho_cliente
    )

    pasta_unm = os.path.join(
        pasta_cliente,
        "UNM2000"
    )

    # --------------------------------------------------------
    # Criar cliente
    # --------------------------------------------------------

    if not os.path.isdir(pasta_cliente):

        os.makedirs(
            pasta_cliente
        )

        registrar_log(
            "Pasta do cliente criada: {}".format(
                pasta_cliente
            )
        )

    else:

        registrar_log(
            "Pasta do cliente ja existe: {}".format(
                pasta_cliente
            )
        )

    # --------------------------------------------------------
    # Criar UNM2000
    # --------------------------------------------------------

    if not os.path.isdir(pasta_unm):

        os.makedirs(
            pasta_unm
        )

        registrar_log(
            "Pasta UNM2000 criada: {}".format(
                pasta_unm
            )
        )

    else:

        registrar_log(
            "Pasta UNM2000 ja existe: {}".format(
                pasta_unm
            )
        )

    pasta_unm = os.path.abspath(
        pasta_unm
    )

    registrar_log(
        "Destino final: {}".format(
            pasta_unm
        )
    )

    return pasta_unm


# ============================================================
# TAMANHO DO ARQUIVO
# ============================================================

def tamanho_arquivo(caminho):

    tamanho = os.path.getsize(
        caminho
    )

    return tamanho / float(
        1024 * 1024
    )


# ============================================================
# EXECUTA BACKUP
# ============================================================

def realizar_backup(caminho_cliente, pasta_origem=None):

    if not pasta_origem:

        pasta_origem = PASTA_BACKUP

    registrar_log(
        "Inicio da verificacao."
    )

    # --------------------------------------------------------
    # Verifica origem
    # --------------------------------------------------------

    if not os.path.isdir(pasta_origem):

        raise Exception(
            "Pasta de backup nao encontrada:\n{}".format(
                pasta_origem
            )
        )

    registrar_log(
        "Pasta de origem: {}".format(
            os.path.abspath(pasta_origem)
        )
    )

    # --------------------------------------------------------
    # Cria destino
    # --------------------------------------------------------

    pasta_destino = criar_pasta_cliente(
        caminho_cliente
    )

    # --------------------------------------------------------
    # Procura backups
    # --------------------------------------------------------

    backups = encontrar_backups(
        pasta_origem
    )

    if not backups:

        raise Exception(
            "Nenhum backup no formato esperado foi encontrado."
        )

    # --------------------------------------------------------
    # Procura backup ainda nao processado
    #
    # Comeca pelo mais recente.
    # Se ele ja existir, procura o proximo.
    # --------------------------------------------------------

    backup_pendente = None

    for backup in backups:

        nome_original = backup["nome"]

        nome_destino = novo_nome(
            nome_original
        )

        arquivo_destino = os.path.join(
            pasta_destino,
            nome_destino
        )

        if os.path.isfile(
            arquivo_destino
        ):

            registrar_log(
                "Arquivo ja existe no destino: {}".format(
                    arquivo_destino
                )
            )

        else:

            backup_pendente = backup
            break

    # --------------------------------------------------------
    # Nenhum novo
    # --------------------------------------------------------

    if backup_pendente is None:

        registrar_log(
            "Todos os backups encontrados ja existem no destino."
        )

        return {
            "status": "ja_processado",
            "destino": pasta_destino
        }

    # --------------------------------------------------------
    # Dados do backup
    # --------------------------------------------------------

    nome_original = backup_pendente["nome"]

    arquivo_origem = backup_pendente["caminho"]

    data_backup = backup_pendente["data"]

    # --------------------------------------------------------
    # Nome destino
    # --------------------------------------------------------

    nome_destino = novo_nome(
        nome_original
    )

    arquivo_destino = os.path.join(
        pasta_destino,
        nome_destino
    )

    # --------------------------------------------------------
    # Informacoes
    # --------------------------------------------------------

    registrar_log(
        "Novo backup encontrado: {}".format(
            nome_original
        )
    )

    registrar_log(
        "Data/hora do backup: {}".format(
            data_backup.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )
    )

    # --------------------------------------------------------
    # Verifica se e de hoje
    # --------------------------------------------------------

    data_hoje = datetime.datetime.now().date()

    if data_backup.date() == data_hoje:

        registrar_log(
            "OK: O backup encontrado e de hoje."
        )

        backup_de_hoje = True

    else:

        registrar_log(
            "AVISO: O backup encontrado NAO e de hoje."
        )

        registrar_log(
            "Data do backup: {}".format(
                data_backup.strftime(
                    "%d/%m/%Y"
                )
            )
        )

        registrar_log(
            "Data de hoje: {}".format(
                data_hoje.strftime(
                    "%d/%m/%Y"
                )
            )
        )

        backup_de_hoje = False

    # --------------------------------------------------------
    # Copia
    # --------------------------------------------------------

    registrar_log(
        "Copiando backup..."
    )

    shutil.copy2(
        arquivo_origem,
        arquivo_destino
    )

    registrar_log(
        "Backup copiado com sucesso."
    )

    registrar_log(
        "Origem: {}".format(
            arquivo_origem
        )
    )

    registrar_log(
        "Destino: {}".format(
            arquivo_destino
        )
    )

    # --------------------------------------------------------
    # Retorno
    # --------------------------------------------------------

    return {
        "status": "copiado",
        "origem": arquivo_origem,
        "destino": arquivo_destino,
        "nome": nome_destino,
        "nome_original": nome_original,
        "tamanho": tamanho_arquivo(
            arquivo_origem
        ),
        "data": data_backup,
        "backup_de_hoje": backup_de_hoje
    }


# ============================================================
# SELECAO DE PASTA DE ORIGEM
# ============================================================

def escolher_pasta_origem():

    pasta_inicial = PASTA_BACKUP

    if "entrada_origem" in globals():

        try:

            pasta_atual = entrada_origem.get().strip()

            if os.path.isdir(pasta_atual):

                pasta_inicial = pasta_atual

        except Exception:
            pass

    pasta = filedialog.askdirectory(
        parent=janela,
        title="Selecione a pasta onde estao os backups da UNM2000",
        initialdir=pasta_inicial
    )

    if pasta:

        pasta = os.path.abspath(
            pasta
        )

        entrada_origem.delete(
            0,
            tk.END
        )

        entrada_origem.insert(
            0,
            pasta
        )

        registrar_log(
            "Pasta de origem selecionada: {}".format(
                pasta
            )
        )


# ============================================================
# SELECAO DE PASTA DO CLIENTE
# ============================================================

def escolher_pasta_destino():

    pasta_onedrive = encontrar_onedrive()

    if not pasta_onedrive:

        tkMessageBox.showerror(
            "Erro",
            "Nao foi possivel localizar o OneDrive."
        )

        return

    pasta = filedialog.askdirectory(
        parent=janela,
        title="Selecione a pasta do cliente dentro do OneDrive",
        initialdir=pasta_onedrive
    )

    if not pasta:

        return

    pasta = os.path.abspath(
        pasta
    )

    # --------------------------------------------------------
    # Descobre a parte relativa ao OneDrive
    # --------------------------------------------------------

    try:

        relativo = os.path.relpath(
            pasta,
            pasta_onedrive
        )

    except Exception:

        relativo = pasta

    if relativo == ".":

        tkMessageBox.showwarning(
            "Atencao",
            "Selecione a pasta de um cliente, e nao a pasta raiz do OneDrive."
        )

        return

    relativo = relativo.replace(
        os.sep,
        "\\"
    )

    entrada.delete(
        0,
        tk.END
    )

    entrada.insert(
        0,
        relativo
    )

    registrar_log(
        "Pasta do cliente selecionada: {}".format(
            relativo
        )
    )


# ============================================================
# EXECUTAR
# ============================================================

def executar():

    pasta_origem = entrada_origem.get().strip()

    caminho_cliente = entrada.get().strip()

    # --------------------------------------------------------
    # Verifica origem
    # --------------------------------------------------------

    if not pasta_origem:

        tkMessageBox.showwarning(
            "Atencao",
            "Informe ou selecione a pasta de origem dos backups."
        )

        return

    if not os.path.isdir(pasta_origem):

        tkMessageBox.showerror(
            "Erro",
            "A pasta de origem informada nao existe:\n{}".format(
                pasta_origem
            )
        )

        return

    # --------------------------------------------------------
    # Verifica cliente
    # --------------------------------------------------------

    if not caminho_cliente:

        tkMessageBox.showwarning(
            "Atencao",
            "Informe o caminho do cliente."
        )

        return

    try:

        resultado = realizar_backup(
            caminho_cliente,
            pasta_origem
        )

        # ----------------------------------------------------
        # Copiado
        # ----------------------------------------------------

        if resultado["status"] == "copiado":

            tamanho = resultado.get(
                "tamanho",
                0.0
            )

            if resultado.get(
                "backup_de_hoje",
                False
            ):

                situacao_data = (
                    "OK: backup de hoje."
                )

            else:

                situacao_data = (
                    "AVISO: o backup encontrado nao e de hoje."
                )

            mensagem = (
                "BACKUP REALIZADO COM SUCESSO\n\n"
                "Arquivo original:\n{}\n\n"
                "Arquivo salvo como:\n{}\n\n"
                "Data/hora do backup:\n{}\n\n"
                "{}\n\n"
                "Tamanho: {:.2f} MB\n\n"
                "Destino:\n{}"
            ).format(
                resultado["nome_original"],
                resultado["nome"],
                resultado["data"].strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
                situacao_data,
                tamanho,
                resultado["destino"]
            )

            tkMessageBox.showinfo(
                "Backup realizado",
                mensagem
            )

        # ----------------------------------------------------
        # Ja existia
        # ----------------------------------------------------

        elif resultado["status"] == "ja_processado":

            mensagem = (
                "BACKUP JA PROCESSADO\n\n"
                "Todos os backups encontrados ja "
                "existem no destino.\n\n"
                "Pasta:\n{}"
            ).format(
                resultado["destino"]
            )

            tkMessageBox.showinfo(
                "Backup ja existente",
                mensagem
            )

    except Exception as erro:

        registrar_log(
            "ERRO: {}".format(
                str(erro)
            )
        )

        tkMessageBox.showerror(
            "Erro / Alerta",
            str(erro)
        )


# ============================================================
# JANELA
# ============================================================

janela = tk.Tk()

janela.title(
    "Agente de Backup - UNM 2000"
)

janela.geometry(
    "650x370"
)

janela.resizable(
    False,
    False
)


# ============================================================
# TITULO
# ============================================================

titulo = tk.Label(
    janela,
    text="Agente de Backup UNM 2000",
    font=("Arial", 16)
)

titulo.pack(
    pady=(12, 10)
)


# ============================================================
# ORIGEM
# ============================================================

lbl_origem = tk.Label(
    janela,
    text="Informe ou selecione a pasta de origem:",
    font=("Arial", 10)
)

lbl_origem.pack(
    anchor="w",
    padx=30
)


frame_origem = tk.Frame(
    janela
)

frame_origem.pack(
    fill="x",
    padx=30,
    pady=(3, 10)
)


entrada_origem = tk.Entry(
    frame_origem,
    font=("Arial", 10)
)

entrada_origem.insert(
    0,
    PASTA_BACKUP
)

entrada_origem.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(0, 6)
)


btn_origem = tk.Button(
    frame_origem,
    text="Procurar...",
    font=("Arial", 9),
    command=escolher_pasta_origem
)

btn_origem.pack(
    side="right"
)


# ============================================================
# CLIENTE
# ============================================================

lbl_destino = tk.Label(
    janela,
    text="Informe o cliente ou selecione a pasta no OneDrive:",
    font=("Arial", 10)
)

lbl_destino.pack(
    anchor="w",
    padx=30
)


frame_destino = tk.Frame(
    janela
)

frame_destino.pack(
    fill="x",
    padx=30,
    pady=(3, 12)
)


entrada = tk.Entry(
    frame_destino,
    font=("Arial", 10)
)

entrada.insert(
    0,
    "Cliente"
)

entrada.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(0, 6)
)


btn_destino = tk.Button(
    frame_destino,
    text="Procurar...",
    font=("Arial", 9),
    command=escolher_pasta_destino
)

btn_destino.pack(
    side="right"
)


# ============================================================
# BOTAO
# ============================================================

botao = tk.Button(
    janela,
    text="Verificar e realizar backup",
    width=30,
    height=2,
    command=executar
)

botao.pack(
    pady=6
)


# ============================================================
# INFORMACOES
# ============================================================

info = tk.Label(
    janela,
    text=(
        "Origem: pasta onde estao os backups da UNM 2000\n"
        "Destino: OneDrive\\<Cliente>\\UNM2000\n"
        "O backup sera copiado mesmo se nao for de hoje."
    ),
    font=("Arial", 9)
)

info.pack(
    pady=(5, 10)
)


# ============================================================
# INICIO
# ============================================================

registrar_log(
    "Agente iniciado."
)

janela.mainloop()