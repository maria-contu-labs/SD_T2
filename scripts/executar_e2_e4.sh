#!/usr/bin/env bash
# Uso: PROCESSOS=2 ./scripts/executar_e2_e4.sh etcd E2 N_OTIMO
set -euo pipefail
cd "$(dirname "$0")/.."
SISTEMA="${1:?Informe sistema}"
EXP="${2:?Informe E2 ou E4}"
N="${3:?Informe N otimo obtido no E1}"
case "$EXP" in E2|E4) ;; *) echo 'Experimento invalido' >&2; exit 1;; esac
for REP in 1 2 3; do
 # E4: a latencia deve ser reaplicada apos cada reset externo.
 if [ "${RESETAR:-0}" = "1" ]; then
   if [ "$EXP" = "E4" ]; then
     echo 'E4 com RESETAR=1 exige reaplicar netem antes de cada execucao; faça o reset e a configuracao manualmente.' >&2
     exit 1
   fi
   docker compose -f "$SISTEMA.yml" down -v
   ./scripts/ambiente.sh "$SISTEMA"
   ./scripts/preparar.sh "$SISTEMA"
 fi
 ./scripts/rodar_carga.sh "$SISTEMA" "$EXP" "$N" "$REP"
done
