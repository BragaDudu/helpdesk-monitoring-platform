@echo off
REM Sobe a aplicacao usando o Python DO PROJETO (.venv).
REM Assim nunca da 'ModuleNotFoundError' por esquecer de ativar o ambiente.
cd /d "%~dp0"
echo.
echo  Iniciando HelpDesk ^& Monitoring...
echo  Abra no navegador:  http://localhost:8010
echo  Documentacao da API: http://localhost:8010/docs
echo  (para parar: Ctrl+C)
echo.
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8010
pause
