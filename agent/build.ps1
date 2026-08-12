Write-Host "Criando ambiente virtual e instalando dependencias..."
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install pyinstaller pywin32

Write-Host "Compilando serviço em background (service.exe)..."
# O serviço Windows no PyInstaller precisa ser Console (não windowed) para o pywin32 funcionar
pyinstaller --noconfirm --onefile `
    --hidden-import win32timezone `
    --hidden-import win32serviceutil `
    --hidden-import win32service `
    --hidden-import servicemanager `
    --name TrilanAgentService `
    service.py

Write-Host "Compilando aplicativo da bandeja (tray.exe)..."
pyinstaller --noconfirm --onefile --windowed `
    --name TrilanAgentTray `
    tray.py

Write-Host "Limpando arquivos temporários..."
Remove-Item -Recurse -Force build
Remove-Item TrilanAgentService.spec
Remove-Item TrilanAgentTray.spec

Write-Host "======================================"
Write-Host "Build concluído! Executáveis na pasta 'dist'"
Write-Host "======================================"
