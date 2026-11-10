@echo off
REM ===========================================================================
REM Executa a carga diária. Chamado pelo Agendador de Tarefas do Windows às 06h00.
REM A saída completa vai para logs\agendado_AAAA-MM-DD.log (data no nome).
REM O Python também grava logs\etl_AAAA-MM-DD.log com o log estruturado.
REM ===========================================================================
setlocal
cd /d "%~dp0.."

REM Data no formato ISO, independente da configuração regional do Windows
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set HOJE=%%i
if not exist logs mkdir logs

REM Usa o Python do ambiente virtual do projeto
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python

echo ==== %DATE% %TIME% inicio da execucao agendada >> "logs\agendado_%HOJE%.log"
%PY% etl.py --modo diario >> "logs\agendado_%HOJE%.log" 2>&1
set CODIGO=%ERRORLEVEL%
echo ==== %DATE% %TIME% fim (codigo %CODIGO%) >> "logs\agendado_%HOJE%.log"

REM 0=sucesso 1=parcial 2=falha 3=bloqueada (outra execucao em andamento)
exit /b %CODIGO%
