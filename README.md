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