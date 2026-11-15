#!/usr/bin/env bash
# ==============================================================================
# Script de Execução COMPLETA do Experimento 4 (E4 — Latência Elevada)
# Automatiza: Ambiente -> Preparação -> Latência (+50ms) -> Carga (3 reps) -> Limpeza
# Uso: PROCESSOS=2 ./scripts/executar_e4.sh <etcd|cassandra> <N_OTIMO>
# Exemplo: PROCESSOS=2 ./scripts/executar_e4.sh etcd 2
# ==============================================================================

set -euo pipefail
cd "$(dirname "$0")/.."

SISTEMA="${1:?Informe o sistema (etcd ou cassandra)}"
N="${2:?Informe o N_otimo obtido no E1}"

case "$SISTEMA" in
    etcd|cassandra) ;;
    *) echo "Erro: Sistema inválido '$SISTEMA'. Use etcd ou cassandra." >&2; exit 1 ;;
esac

# Função de limpeza garantida ao sair (mesmo em caso de erro ou término normal)
cleanup() {
    echo ""
    echo "🧹 [LIMPEZA] Removendo latência de rede e encerrando contêineres..."
    ./scripts/latencia_off.sh n1 n2 n3 2>/dev/null || true
    docker compose -f "${SISTEMA}.yml" down -v 2>/dev/null || true
    echo "✅ Limpeza concluída com sucesso."
}
trap cleanup EXIT

echo "============================================================"
echo " EXPERIMENTO E4 COMPLETO: REDE COM LATÊNCIA ELEVADA (+50ms)"
echo " Sistema: $SISTEMA | N_ótimo: $N | Duração: 180s por repetição"
echo "============================================================"

echo ""
echo "🚀 1/5. Subindo ambiente Docker para $SISTEMA..."
./scripts/ambiente.sh "$SISTEMA"

echo ""
echo "⚙️ 2/5. Criando esquema e chaves de teste..."
./scripts/preparar.sh "$SISTEMA"

echo ""
echo "🌐 3/5. Aplicando latência de 50ms por sentido (RTT ~100ms)..."
./scripts/latencia_on.sh 50ms n1 n2 n3

echo ""
echo "📡 Verificando RTT inter-nós:"
./scripts/rtt.sh n1 172.20.0.12 || true

echo ""
echo "⚡ 4/5. Executando as 3 repetições da carga do E4..."

for REP in 1 2 3; do
    echo ""
    echo "------------------------------------------------------------"
    echo ">>> Rodando E4 | Sistema: $SISTEMA | N: $N | Repetição $REP/3"
    echo "------------------------------------------------------------"

    ./scripts/rodar_carga.sh "$SISTEMA" E4 "$N" "$REP"

    python3 analisar.py --input gerador/resultados --output graficos > /dev/null 2>&1 || true

    echo ""
    echo "📊 === RESULTADOS NO TERMINAL (E4 | $SISTEMA | Repetição $REP) ==="
    python3 -c "
import csv, os

path = 'graficos/resumo_consolidado.csv'
if not os.path.exists(path):
    print('Aviso: Arquivo de resultados consolidado ainda não foi gerado.')
else:
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r['sistema'] == '$SISTEMA' and r['experimento'] == 'E4' and str(r['N']) == '$N']
        if rows:
            print(f'{\"OPERAÇÃO\":<10} | {\"VAZÃO (req/s)\":<15} | {\"p50 (ms)\":<10} | {\"p95 (ms)\":<10} | {\"p99 (ms)\":<10} | {\"ERROS\":<6}')
            print('-' * 75)
            for r in rows:
                p50 = f\"{float(r['p50_ms']):.2f}\" if r['p50_ms'] else 'N/A'
                p95 = f\"{float(r['p95_ms']):.2f}\" if r['p95_ms'] else 'N/A'
                p99 = f\"{float(r['p99_ms']):.2f}\" if r['p99_ms'] else 'N/A'
                vazao = f\"{float(r['vazao_req_s']):.2f}\" if r['vazao_req_s'] else 'N/A'
                print(f\"{r['operacao']:<10} | {vazao:<15} | {p50:<10} | {p95:<10} | {p99:<10} | {r['erros']:<6}\")
        else:
            print('Nenhum registro encontrado para este experimento no resumo.')
"
done

echo ""
echo "🏁 5/5. Finalizando o Experimento E4 para $SISTEMA!"
