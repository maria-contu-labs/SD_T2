#!/usr/bin/env bash
# Uso: ./scripts/executar_e3.sh etcd|cassandra original|alta
set -euo pipefail
SISTEMA="${1:?Informe o sistema}"
CONDI="${2:?original ou alta}"
case "$CONDI" in original|alta) ;; *) exit 1;; esac
for REP in 1 2 3; do
 docker exec gerador python /app/stale.py "$SISTEMA" --pairs 10000 \
 --output "/app/resultados/E3/${SISTEMA}_stale_${CONDI}_r${REP}.csv.gz"
done
