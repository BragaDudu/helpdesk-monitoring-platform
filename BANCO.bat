@echo off
REM Abre o console SQL para explorar o banco de dados.
cd /d "%~dp0"
python -m backend.db_shell
pause
