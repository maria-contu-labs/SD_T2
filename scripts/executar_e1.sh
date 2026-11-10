#!/usr/bin/env bash
# Ex.: PROCESSOS=2 ./scripts/executar_e1.sh etcd 1 2 4 8 16 32 64 128 256 512
# 3 repeticoes de 120 s, excluindo 30 s iniciais (valores padrao).
set -euo pipefail
cd "$(dirname "$0")/.."
SISTEMA="${1:?Informe etcd ou cassandra}"
shift
if [ "$#" -eq 0 ]; then set -- 1 2 4 8 16 32 64 128 256 512; fi
for N in "$@"; do
 for REP in 1 2 3; do
  echo "Executando E1: $SISTEMA N=$N repeticao=$REP"
  if [ "${RESETAR:-0}" = "1" ]; then
   docker compose -f "$SISTEMA.yml" down -v
   ./scripts/ambiente.sh "$SISTEMA"
   ./scripts/preparar.sh "$SISTEMA"
  fi
  ./scripts/rodar_carga.sh "$SISTEMA" E1 "$N" "$REP"
 done
done
