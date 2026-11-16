#!/usr/bin/env bash
# ==============================================================================
# Script de Execução COMPLETA do Experimento 5 (E5 — Partição de Rede)
# Automatiza: Ambiente -> Preparação -> Orquestração da Partição (n1) -> Análise -> Limpeza
# Uso: PROCESSOS=2 ./scripts/executar_e5.sh <etcd|cassandra> <N_OTIMO>
# Exemplo: PROCESSOS=2 ./scripts/executar_e5.sh etcd 2
# ==============================================================================

set -euo pipefail
cd "$(dirname "$0")/.."

SISTEMA="${1:?Informe o sistema (etcd ou cassandra)}"
N="${2:?Informe o N_otimo obtido no E1}"

case "$SISTEMA" in
    etcd|cassandra) ;;
    *) echo "Erro: Sistema inválido '$SISTEMA'. Use etcd ou cassandra." >&2; exit 1 ;;
esac

# Limpeza automática garantida mesmo em caso de erro ou interrupção
cleanup() {
    echo ""
    echo "🧹 [LIMPEZA] Reconectando nó n1 se necessário e encerrando contêineres..."
    ./scripts/cura.sh 2>/dev/null || true
    docker compose -f "${SISTEMA}.yml" down -v 2>/dev/null || true
    echo "✅ Limpeza concluída com sucesso."
}
trap cleanup EXIT

echo "============================================================"
echo " EXPERIMENTO E5 COMPLETO: PARTIÇÃO DE REDE (Isolamento de n1)"
echo " Sistema: $SISTEMA | N_ótimo: $N"
echo " Cronograma por repetição: 45s normal -> 60s partição -> 75s cura"
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

echo ""
echo "⚡ 3/4. Executando as 3 repetições do E5 com orquestração de partição..."

for REP in 1 2 3; do
    echo ""
    echo "------------------------------------------------------------"
    echo ">>> Rodando E5 | Sistema: $SISTEMA | N: $N | Repetição $REP/3"
    echo "------------------------------------------------------------"

    # Invoca a orquestração que injeta a partição no n1 no tempo correto
    python3 orquestrar.py E5 "$SISTEMA" "$N" --rep "$REP"

    # Atualiza análise e gráficos de linha do tempo
    python3 analisar.py --input gerador/resultados --output graficos > /dev/null 2>&1 || true

    echo ""
    echo "📊 Status da Repetição $REP concluída."
done

echo ""
echo "🏁 4/4. Finalizando o Experimento E5 para $SISTEMA!"
