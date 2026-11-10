#!/usr/bin/env bash
# Executa a carga diária (Linux). Chamado pelo cron às 06h00.
# Saída completa em logs/agendado_AAAA-MM-DD.log (data no nome).
set -u
cd "$(dirname "$0")/.."
mkdir -p logs
LOG="logs/agendado_$(date +%F).log"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"

echo "==== $(date '+%F %T') início da execução agendada" >> "$LOG"
# flock -n: se a execução anterior ainda roda, esta sai na hora (1ª proteção;
# a 2ª é o advisory lock no PostgreSQL, que vale mesmo fora do cron)
flock -n /tmp/etl_prevencao_perdas.lock "$PY" etl.py --modo diario >> "$LOG" 2>&1
CODIGO=$?
echo "==== $(date '+%F %T') fim (código $CODIGO)" >> "$LOG"
exit $CODIGO
