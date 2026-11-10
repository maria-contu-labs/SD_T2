#!/usr/bin/env bash
# Uso: ./scripts/rodar_carga.sh etcd E1 32 1
# PROCESSOS=2 DURACAO=120 WARMUP=30 MONITORAR=1
# Divide o total N entre processos independentes. O N no enunciado SEMPRE
# corresponde à soma das threads, não ao número de threads por processo.
set -euo pipefail
cd "$(dirname "$0")/.."
SISTEMA="${1:?Informe etcd ou cassandra}"
EXP="${2:?Informe PILOTO, E1, E2 ou E4}"
N="${3:?Informe N total}"
REP="${4:-1}"
case "$SISTEMA" in etcd|cassandra) ;; *) echo 'Sistema invalido' >&2; exit 2;; esac
case "$EXP" in PILOTO|E1|E2|E4) ;; *) echo 'Experimento invalido' >&2; exit 2;; esac
[[ "$N" =~ ^[1-9][0-9]*$ ]] || { echo 'N deve ser positivo' >&2; exit 2; }
[[ "$REP" =~ ^[1-9][0-9]*$ ]] || { echo 'Repeticao invalida' >&2; exit 2; }
PROCESSOS="${PROCESSOS:-2}"
[[ "$PROCESSOS" =~ ^[1-9][0-9]*$ ]] || { echo 'PROCESSOS deve ser positivo' >&2; exit 2; }
if [ "$PROCESSOS" -gt "$N" ]; then PROCESSOS="$N"; fi
case "$EXP" in
 PILOTO) DURACAO="${DURACAO:-20}"; WARMUP="${WARMUP:-2}" ;;
 E1) DURACAO="${DURACAO:-120}"; WARMUP="${WARMUP:-30}" ;;
 E2) DURACAO="${DURACAO:-180}"; WARMUP="${WARMUP:-0}" ;;
 E4) DURACAO="${DURACAO:-180}"; WARMUP="${WARMUP:-30}" ;;
esac
[[ "$DURACAO" =~ ^[1-9][0-9]*$ ]] && [[ "$WARMUP" =~ ^[0-9]+$ ]] && [ "$WARMUP" -lt "$DURACAO" ] || {
 echo 'DURACAO e WARMUP invalidos' >&2; exit 2;
}
SEED="${SEED:-2026}"
MONITORAR="${MONITORAR:-1}"
mkdir -p "gerador/resultados/$EXP"
PREFIX="${SISTEMA}_n${N}_r${REP}"
ROOT="gerador/resultados/$EXP"
# Apaga metadados de sucesso antigos para não mascarar execuções incompletas.
rm -f "$ROOT/$PREFIX.manifest.json"

PIDS=()
MON_PID=''
cleanup() {
 if [ -n "$MON_PID" ]; then
  kill "$MON_PID" 2>/dev/null || true
  wait "$MON_PID" 2>/dev/null || true
 fi
}
trap cleanup EXIT

if [ "$MONITORAR" = "1" ]; then
 (
  printf 'epoch,container,cpu_pct,memoria\n'
  while true; do
   ts="$(date +%s)"
   docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' n1 n2 n3 gerador 2>/dev/null | \
     while IFS= read -r line; do printf '%s,%s\n' "$ts" "$line"; done
   sleep 3
  done
 ) > "$ROOT/$PREFIX.cpu.csv" &
 MON_PID=$!
fi

echo "Iniciando $SISTEMA $EXP: N total=$N, processos=$PROCESSOS, repeticao=$REP, duracao=$DURACAO s, aquecimento=$WARMUP s"
for (( i=0; i<PROCESSOS; i++ )); do
 # Distribuição equilibrada: soma EXATAMENTE N.
 THREADS=$((N / PROCESSOS + (i < N % PROCESSOS ? 1 : 0)))
 PROC_SEED=$((SEED + REP * 10000019 + i * 1000003))
 OUT="/app/resultados/$EXP/${PREFIX}_p${i}.csv.gz"
 docker exec gerador python /app/carga.py "$SISTEMA" \
  --threads "$THREADS" --seconds "$DURACAO" --warmup "$WARMUP" \
  --seed "$PROC_SEED" --output "$OUT" > "$ROOT/${PREFIX}_p${i}.log" 2>&1 &
 PIDS+=("$!")
 echo "  processo $i: $THREADS threads, semente $PROC_SEED"
done

ERRORS=0
for pid in "${PIDS[@]}"; do
 if ! wait "$pid"; then ERRORS=1; fi
done
if [ "$ERRORS" != 0 ]; then
 echo "ERRO em algum gerador. Confira: $ROOT/${PREFIX}_p*.log" >&2
 exit 1
fi
for (( i=0; i<PROCESSOS; i++ )); do
 test -f "$ROOT/${PREFIX}_p${i}.csv.gz" || { echo "CSV ausente: processo $i" >&2; exit 1; }
 test -f "$ROOT/${PREFIX}_p${i}.csv.gz.json" || { echo "Metadados ausentes: processo $i" >&2; exit 1; }
done
# Manifesto identifica runs completas e permite validar agrupamento no analisador.
cat > "$ROOT/$PREFIX.manifest.json" <<EOFJSON
{"sistema":"$SISTEMA","experimento":"$EXP","N_total":$N,"repeticao":$REP,"processos":$PROCESSOS,"seconds":$DURACAO,"warmup":$WARMUP,"seed_base":$SEED,"timestamp_utc":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOFJSON
printf 'Concluido: %s (%s processos). Arquivos: %s/%s_p*.csv.gz\n' "$EXP" "$PROCESSOS" "$ROOT" "$PREFIX"
