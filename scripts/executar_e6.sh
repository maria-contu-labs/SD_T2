#!/usr/bin/env bash
# ==============================================================================
# Script de Execução COMPLETA do Experimento 6 (E6 — Failover / Queda de Nó)
# Automatiza: Ambiente -> Preparação -> Identificação do Líder -> Carga c/ Queda -> Limpeza
# Uso: PROCESSOS=2 ./scripts/executar_e6.sh <etcd|cassandra> <N_OTIMO> [no_opcional]
# Exemplo (matar líder no etcd): PROCESSOS=2 ./scripts/executar_e6.sh etcd 2
# Exemplo (matar nó específico): PROCESSOS=2 ./scripts/executar_e6.sh etcd 2 n1
# ==============================================================================

set -euo pipefail
cd "$(dirname "$0")/.."

SISTEMA="${1:?Informe o sistema (etcd ou cassandra)}"
N="${2:?Informe o N_otimo obtido no E1}"
NODE_ARG="${3:-auto}"

case "$SISTEMA" in
    etcd|cassandra) ;;
    *) echo "Erro: Sistema inválido '$SISTEMA'. Use etcd ou cassandra." >&2; exit 1 ;;
esac

TARGET_NODE=""

cleanup() {
    echo ""
    echo "🧹 [LIMPEZA] Garantindo que todos os nós estejam rodando e encerrando contêineres..."
    docker start n1 n2 n3 2>/dev/null || true
    docker compose -f "${SISTEMA}.yml" down -v 2>/dev/null || true
    echo "✅ Limpeza concluída com sucesso."
}
trap cleanup EXIT

echo "============================================================"
echo " EXPERIMENTO E6 COMPLETO: FAILOVER / QUEDA DE NÓ"
echo " Sistema: $SISTEMA | N_ótimo: $N"
echo " Cronograma por repetição: 45s normal -> 60s nó morto -> 75s pós-reinício"
echo "============================================================"

echo ""
echo "🚀 1/4. Subindo ambiente Docker para $SISTEMA..."
./scripts/ambiente.sh "$SISTEMA"

echo ""
echo "⚙️ 2/4. Criando esquema e chaves de teste..."
./scripts/preparar.sh "$SISTEMA"

if [ "$SISTEMA" = "cassandra" ]; then
    echo "⏳ Aguardando a estabilização completa da porta CQL (15s)..."
    sleep 15
fi

# Determinar qual nó será derrubado
if [ "$NODE_ARG" != "auto" ]; then
    TARGET_NODE="$NODE_ARG"
else
    if [ "$SISTEMA" = "etcd" ]; then
        echo ""
        echo "🔍 Detectando o nó LÍDER atual do etcd via etcdctl..."
        LEADER_IP=$(docker exec n1 etcdctl --endpoints=http://172.21.0.11:2379,http://172.21.0.12:2379,http://172.21.0.13:2379 endpoint status -w table 2>/dev/null | grep 'true' | awk '{print $2}' | grep -oE '172.21.0.1[1-3]' || echo "")
        case "$LEADER_IP" in
            "172.21.0.11") TARGET_NODE="n1" ;;
            "172.21.0.12") TARGET_NODE="n2" ;;
            "172.21.0.13") TARGET_NODE="n3" ;;
            *) TARGET_NODE="n1" ;;
        esac
        echo "👑 Nó líder identificado para a queda: $TARGET_NODE ($LEADER_IP)"
    else
        TARGET_NODE="n1"
        echo "📌 Nó selecionado para a queda no Cassandra: $TARGET_NODE"
    fi
fi

echo ""
echo "⚡ 3/4. Executando as 3 repetições do E6 com queda do nó $TARGET_NODE..."

for REP in 1 2 3; do
    echo ""
    echo "------------------------------------------------------------"
    echo ">>> Rodando E6 | Sistema: $SISTEMA | N: $N | Nó Alvo: $TARGET_NODE | Repetição $REP/3"
    echo "------------------------------------------------------------"

    python3 orquestrar.py E6 "$SISTEMA" "$N" --rep "$REP" --node "$TARGET_NODE"

    python3 analisar.py --input gerador/resultados --output graficos > /dev/null 2>&1 || true

    echo ""
    echo "📊 Status da Repetição $REP concluída."
done

echo ""
echo "🏁 4/4. Finalizando o Experimento E6 para $SISTEMA!"
