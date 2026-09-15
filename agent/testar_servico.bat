@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo  TRILAN AGENT NVR - TESTE DE SERVICO (SEM COMPILAR EXE)
echo ============================================================
echo.

:: ── Configuracoes do teste ────────────────────────────────────
set AGENT_DIR=%~dp0
set VENV_PYTHON=%AGENT_DIR%venv\Scripts\python.exe
set CONF_FILE=%AGENT_DIR%agent.conf

:: Credenciais do servidor (mesmas que vao no installer)
set SERVER_URL=http://hd208ec5kxz.sn.mynetname.net:7001
set CLIENT_ID=2ecd13ae-91fe-4d5e-81d1-14761396aed4
set API_KEY=sk_trilan_AlgOxKWtQNg7aNlU_2BVUKgqvojhu0ppfxof6Yihpok

:: ── PASSO 1: Verifica Python do venv ──────────────────────────
echo [1/7] Verificando Python do venv...
if not exist "%VENV_PYTHON%" (
    echo ERRO: Python nao encontrado em %VENV_PYTHON%
    echo Crie o venv com:  python -m venv venv
    goto :fim_erro
)
echo OK: %VENV_PYTHON%

:: ── PASSO 2: Instala dependencias ─────────────────────────────
echo.
echo [2/7] Instalando dependencias manualmente para evitar erro no Pillow...
"%VENV_PYTHON%" -m pip install requests==2.31.0 pyzipper==0.3.6 pycryptodome==3.20.0 pypiwin32==223 pystray==0.19.5 Pillow>=10.3.0
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias!
    goto :fim_erro
)
:: pywin32 precisa de pos-instalacao para registrar DLLs corretamente
"%VENV_PYTHON%" "%AGENT_DIR%venv\Scripts\pywin32_postinstall.py" -install 2>nul
echo OK: Dependencias instaladas.

:: ── PASSO 3: Cria agent.conf ───────────────────────────────────
echo.
echo [3/7] Criando agent.conf em %CONF_FILE%...
(
    echo [server]
    echo url = %SERVER_URL%
    echo.
    echo [auth]
    echo client_id = %CLIENT_ID%
    echo api_key = %API_KEY%
) > "%CONF_FILE%"

if not exist "%CONF_FILE%" (
    echo ERRO: Nao foi possivel criar agent.conf
    echo Execute este script como Administrador.
    goto :fim_erro
)
echo OK: agent.conf criado com sucesso.

:: ── PASSO 4: Para e remove servico anterior ───────────────────
echo.
echo [4/7] Removendo servico anterior (se existir)...
net stop TrilanAgentNVR 2>nul
"%VENV_PYTHON%" "%AGENT_DIR%service.py" stop   2>nul
"%VENV_PYTHON%" "%AGENT_DIR%service.py" remove 2>nul
timeout /t 2 /nobreak >nul
echo OK: Servico anterior removido (ou nao existia).

:: ── PASSO 5: Instala o servico via Python ─────────────────────
echo.
echo [5/7] Instalando servico com Python...
"%VENV_PYTHON%" "%AGENT_DIR%service.py" install
if errorlevel 1 (
    echo ERRO: Falha ao instalar o servico!
    echo Verifique se esta executando como Administrador.
    goto :fim_erro
)
echo OK: Servico instalado.

:: ── PASSO 6: Iniciando servico ─────────────────────────────────
echo.
echo [6/7] Iniciando servico...
"%VENV_PYTHON%" "%AGENT_DIR%service.py" start
if errorlevel 1 (
    echo ERRO: Falha ao iniciar o servico!
    goto :fim_erro
)
echo OK: Servico iniciado.

:: ── PASSO 7: Aguarda e mostra o log ──────────────────────────
echo.
echo [7/7] Aguardando 8 segundos e verificando log...
timeout /t 8 /nobreak >nul

echo.
echo ============================================================
echo  LOG DO SERVICO (servico.log)
echo ============================================================
set LOG1=%AGENT_DIR%logs\servico.log
set LOG2=%ProgramData%\Trilan NVR Backup Agent\logs\servico.log

if exist "%LOG1%" (
    type "%LOG1%"
) else if exist "%LOG2%" (
    type "%LOG2%"
) else (
    echo AVISO: Nenhum log encontrado.
)

echo.
echo ============================================================
echo  STATUS DO SERVICO
echo ============================================================
sc query TrilanAgentNVR

goto :fim_ok

:fim_erro
echo.
echo ============================================================
echo  TESTE FALHOU - verifique os erros acima
echo ============================================================
pause
exit /b 1

:fim_ok
echo.
echo ============================================================
echo  TESTE CONCLUIDO - verifique o log acima
echo ============================================================
pause
