# Trilan - Backup Automático de NVR

Sistema automatizado para realização de backup de configurações de NVRs e Câmeras IP (IPCAM) de dispositivos Hikvision via protocolo ISAPI. O sistema roda como um **Serviço do Windows**, garantindo execuções agendadas de forma invisível, e possui um aplicativo de **Bandeja do Sistema (System Tray)** para monitoramento e intervenção manual.

## 🚀 Funcionalidades

*   **Backup via ISAPI:** Download automático das configurações de NVRs (`.bin`) e IPCAMs (`.xls`).
*   **Segurança Criptográfica:** Geração de `secretkey` criptografada (AES) para autenticação segura com o WebSDK da Hikvision.
*   **Compactação Segura:** Arquivos baixados são organizados por data e compactados em um arquivo `.zip` protegido com criptografia **AES-256**.
*   **Notificação por E-mail:** Envio de relatório detalhado (Sucesso/Parcial/Erro) por NVR e anexo do arquivo ZIP (caso esteja dentro do limite de 20MB).
*   **Serviço do Windows (Background):** Agendamento diário nativo, sem necessidade de telas abertas ou usuários logados.
*   **Interface na Bandeja (System Tray):** Ícone na barra de tarefas para acompanhar o status, iniciar/parar o serviço, abrir logs e forçar um backup manual.
*   **Proteção contra Concorrência:** Uso de eventos nomeados (`win32event`) para garantir que apenas uma instância de backup rode por vez, evitando corrupção de arquivos.

## 🏗️ Arquitetura do Projeto

O projeto é dividido em três módulos principais:

1.  `backup_nvr.py`: O núcleo do sistema. Responsável pela comunicação HTTP/ISAPI com os NVRs, criptografia, geração do ZIP e envio do e-mail.
2.  `servico.py`: O wrapper do Serviço do Windows. Controla o agendamento (loop de tempo) e escuta eventos de requisição de backup manual.
3.  `bandeja.py`: A interface gráfica de usuário (GUI) discreta. Roda na bandeja do sistema para controle rápido do serviço e visualização de status.

## 📋 Pré-requisitos

*   **Python 3.8+** (Recomendado instalar marcando a opção "Add to PATH")
*   Pacotes Python necessários (instale via `pip`):

```bash
pip install requests pyzipper pycryptodome pypiwin32 pystray Pillow
```

## ⚙️ Configuração

Antes de iniciar, você deve criar dois arquivos de configuração JSON no mesmo diretório dos scripts.

### 1. config.json
Contém as definições do cliente e as credenciais de acesso aos equipamentos.

```json
{
    "cliente": "Nome do Cliente",
    "pasta_backup": "C:\\BKP_NVR",
    "senha_encriptacao": "SenhaForteParaOZipEAPI123",
    "nvrs": [
        {
            "nome": "NVR_Principal",
            "ip": "192.168.1.100",
            "usuario": "admin",
            "senha": "senha_do_nvr"
        },
        {
            "nome": "NVR_Secundario",
            "ip": "192.168.1.101",
            "usuario": "admin",
            "senha": "senha_do_nvr"
        }
    ]
}
```

### 2. config_email.json
Contém as configurações de SMTP para envio dos relatórios. (Recomendado usar Senhas de Aplicativo do Gmail/Outlook).

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email": "seu.email.envio@gmail.com",
    "senha_app": "sua_senha_de_aplicativo_aqui",
    "destinatarios": [
        "ti@trilan.com.br",
        "gestor@cliente.com.br"
    ]
}
```

## 🛠️ Instalação e Execução

### Instalando o Serviço do Windows
Abra o Prompt de Comando (cmd) ou PowerShell como Administrador, navegue até a pasta do projeto e execute:

```bash
python servico.py install
```

Para iniciar o serviço para que ele comece a rodar em background:

```bash
python servico.py start
```

*(Outros comandos úteis: `stop`, `restart`, `remove`, `update`)*

### Executando o App da Bandeja (System Tray)
Para ter o controle visual na barra de tarefas, basta executar o script da bandeja (ou colocá-lo na inicialização do Windows):

```bash
pythonw bandeja.py
```

*(Usamos `pythonw` para não abrir a janela preta do console no fundo).* 

O ícone 🟢 verde aparecerá perto do relógio do Windows. Clicando com o botão direito, você terá acesso ao menu de controle.

## 🕒 Horário do Backup Automático

Por padrão, o horário de execução do backup automático está definido no código-fonte do `servico.py`:

```python
HORA_BACKUP = 14
MINUTO_BACKUP = 48
```

Para alterar, modifique estas variáveis no arquivo `servico.py` e reinicie o serviço pelo aplicativo da bandeja.

## 📝 Logs e Solução de Problemas

O sistema gera logs detalhados para auditoria e resolução de problemas. Eles ficam localizados na subpasta `logs/` (criada automaticamente).

- `servico.log`: Contém o histórico de inicialização do serviço, status do loop de agendamento e o passo a passo da comunicação com os NVRs (criação de diretórios, tamanho dos arquivos, hash SHA-256 e status do envio do e-mail).
Você pode abrir este log rapidamente usando a opção “📄 Abrir log” no menu da bandeja do sistema.

## ⚠️ Limitações Conhecidas

- **Tamanho de Anexo de E-mail:** Limite de anexo fixado em 20MB. Caso o ZIP gerado exceda esse tamanho, o sistema enviará o relatório por e-mail indicando sucesso, mas **sem o anexo**, mantendo os arquivos salvos no disco local (`pasta_backup`).
- **Permissões de Rede:** O PC onde o sistema for instalado precisa de visibilidade de rede (rotas liberadas) para os IPs listados no `config.json` e acesso externo à internet para comunicação SMTP (porta 587 ou 465).

