#!/usr/bin/env bash
# Executa as DUAS variantes do E6; preserva E6 original e resultados anteriores.
# O cluster deve estar em execução e com chaves previamente preparadas.
# Uso: PILOTO=1 ./scripts/executar_e6_v2.sh etcd 2
#      PROCESSOS=2 REPETICOES=3 ./scripts/executar_e6_v2.sh cassandra 8
set -euo pipefail
cd "$(dirname "$0")/.."
SYS="${1:?Uso: ./scripts/executar_e6_v2.sh etcd|cassandra N}"
N="${2:?Informe N do E1}"
[[ "$SYS" == etcd || "$SYS" == cassandra ]] || { echo "Sistema inválido" >&2; exit 2; }
[[ "$N" =~ ^[1-9][0-9]*$ ]] || { echo "N inválido" >&2; exit 2; }
PROCESSOS="${PROCESSOS:-2}"
REPETICOES="${REPETICOES:-3}"
[[ "$PROCESSOS" =~ ^[1-9][0-9]*$ && "$REPETICOES" =~ ^[1-9][0-9]*$ ]] || exit 2
if (( PROCESSOS > N )); then PROCESSOS="$N"; fi
if [[ "${PILOTO:-0}" == 1 ]]; then
    ANTES="${ANTES:-10}"; FALHA="${FALHA:-10}"; DEPOIS="${DEPOIS:-15}"
    BASE="PILOTO_E6_V2"
else
    ANTES="${ANTES:-45}"; FALHA="${FALHA:-60}"; DEPOIS="${DEPOIS:-75}"
    BASE="E6_V2"
fi
RUN_ID="$(date -u +%Y%m%dT%H%M%S)_$$"
FOLDER="$BASE/$RUN_ID"

if ! docker inspect gerador n1 n2 n3 >/dev/null 2>&1; then
    echo "Cluster ausente. Execute antes ./scripts/ambiente.sh $SYS e ./scripts/preparar.sh $SYS" >&2
    exit 1
fi

await_cluster() {
    if [[ "$SYS" == cassandra ]]; then
        # nodetool UN sozinho nao garante que a porta CQL 9042 esteja atendendo.
        # O driver conecta a TODOS os nos na inicializacao; valida a mesma condicao.
        python3 scripts/verificar_prontidao_e6.py --timeout "${CQL_READY_TIMEOUT:-240}"
        return $?
    fi
    local attempt
    for attempt in $(seq 1 35); do
        if docker exec n1 etcdctl --endpoints=http://172.21.0.11:2379,http://172.21.0.12:2379,http://172.21.0.13:2379 endpoint health --cluster >/dev/null 2>&1; then
            return 0
        fi
        sleep 3
    done
    echo "Cluster etcd nao recuperou os tres endpoints" >&2
    return 1
}

if [[ "$SYS" == etcd ]]; then
    ROLES=(lider seguidor)
else
    # Cassandra não tem leader/follower. A carga distribui requisições pelos 3 nós.
    ROLES=(coordenador_n1 coordenador_n2)
fi

echo "E6_v2: sistema=$SYS N=$N processos=$PROCESSOS reps=$REPETICOES"
echo "Fases: ${ANTES}s normal, ${FALHA}s falha, ${DEPOIS}s recuperação"
echo "Saída exclusiva: gerador/resultados/$FOLDER"
for role in "${ROLES[@]}"; do
    for ((rep=1; rep<=REPETICOES; rep++)); do
        await_cluster
        python3 orquestrar_e6_v2.py "$SYS" "$N" --role "$role" --rep "$rep" \
            --processes "$PROCESSOS" --before "$ANTES" --fault-seconds "$FALHA" \
            --after "$DEPOIS" --folder "$FOLDER"
    done
done
python3 analisar_e6_v2.py --input "gerador/resultados/$FOLDER" --output "graficos/e6_v2/$RUN_ID"
echo "Conclusão: revisar graficos/e6_v2/$RUN_ID antes de alterar relatório"
