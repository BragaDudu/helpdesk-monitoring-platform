@echo off
REM Roda os 34 testes automatizados.
cd /d "%~dp0"
.venv\Scripts\python.exe -m pytest -v
pause
