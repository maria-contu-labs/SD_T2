#!/usr/bin/env bash
# Reproduz a carga do E2 sem sobrescrever os resultados oficiais.
set -euo pipefail
cd "$(dirname "$0")/.."
SISTEMA="${1:-cassandra}"
[[ "$SISTEMA" == etcd || "$SISTEMA" == cassandra ]] || { echo "Use etcd ou cassandra" >&2; exit 2; }
PROCESSOS=2 DURACAO="${DURACAO:-180}" WARMUP=0 MONITORAR="${MONITORAR:-1}" \
  bash scripts/rodar_carga.sh "$SISTEMA" PILOTO 2 99
python3 scripts/resumo_piloto.py "$SISTEMA" 2 99
