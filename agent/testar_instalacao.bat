@echo off
echo ============================================================
echo TESTE DE INSTALACAO DO TRILAN AGENT NVR
echo ============================================================
echo.

set APP_DIR=C:\Program Files (x86)\Trilan NVR Backup Agent
set CONF_FILE=%APP_DIR%\agent.conf
set SVC_EXE=%APP_DIR%\TrilanAgentService.exe

:: PASSO 1 - Verifica se o .exe existe
echo [1/5] Verificando TrilanAgentService.exe...
if not exist "%SVC_EXE%" (
    echo ERRO: %SVC_EXE% nao encontrado!
    goto :fim
)
echo OK: %SVC_EXE% encontrado.

:: PASSO 2 - Cria agent.conf de teste
echo.
echo [2/5] Criando agent.conf de teste...
(
    echo [server]
    echo url = http://hd208ec5kxz.sn.mynetname.net:7001
    echo.
    echo [auth]
    echo client_id = 2ecd13ae-91fe-4d5e-81d1-14761396aed4
    echo api_key = sk_trilan_AlgOxKWtQNg7aNlU_2BVUKgqvojhu0ppfxof6Yihpok
) > "%CONF_FILE%"

if not exist "%CONF_FILE%" (
    echo ERRO: Nao foi possivel criar %CONF_FILE%
    echo Verifique se voce tem permissao de escrita na pasta.
    goto :fim
)
echo OK: agent.conf criado em %CONF_FILE%

:: PASSO 3 - Para o servico se estiver rodando
echo.
echo [3/5] Parando servico existente (se houver)...
net stop TrilanAgentNVR 2>nul
"%SVC_EXE%" stop 2>nul
"%SVC_EXE%" remove 2>nul
timeout /t 2 /nobreak >nul
echo OK: Servico removido (ou nao existia).

:: PASSO 4 - Instala e inicia o servico
echo.
echo [4/5] Instalando e iniciando o servico...
"%SVC_EXE%" install
if errorlevel 1 (
    echo ERRO: Falha ao instalar o servico!
    goto :fim
)
echo OK: Servico instalado.

"%SVC_EXE%" start
if errorlevel 1 (
    echo ERRO: Falha ao iniciar o servico!
    goto :fim
)
echo OK: Servico iniciado.

:: PASSO 5 - Aguarda e verifica log
echo.
echo [5/5] Aguardando 5 segundos e verificando log...
timeout /t 5 /nobreak >nul

set LOG_FILE=%APP_DIR%\logs\servico.log
if exist "%LOG_FILE%" (
    echo.
    echo === CONTEUDO DO LOG ===
    type "%LOG_FILE%"
) else (
    echo Log nao encontrado em %LOG_FILE%
)

:fim
echo.
echo ============================================================
echo TESTE CONCLUIDO
echo ============================================================
pause
