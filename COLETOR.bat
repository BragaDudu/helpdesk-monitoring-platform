@echo off
REM Agente coletor: simula os sensores enviando leituras de temperatura.
REM Deixe rodando numa janela separada, junto com o INICIAR.bat.
cd /d "%~dp0"
echo.
echo  Iniciando o AGENTE COLETOR...
echo  Ele envia leituras para a API a cada 60 segundos.
echo  (para parar: Ctrl+C)
echo.
.venv\Scripts\python.exe -m backend.agent --intervalo 60 --lote 150
pause
