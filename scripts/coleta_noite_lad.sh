#!/usr/bin/env bash
# Coleta noturna: E1 completo e E3 (rede normal e atraso de 50 ms por sentido).
# Execute somente no host autorizado do LAD com Docker/Compose disponíveis.
# Uso: PROCESSOS=2 ./scripts/coleta_noite_lad.sh
set -Eeuo pipefail
cd "$(dirname "$0")/.."

PROCESSOS="${PROCESSOS:-2}"
E3_ALTA="${E3_ALTA:-1}"
E1_PONTOS="${E1_PONTOS:-1 2 4 8 16 32 64 128 256 512}"
read -r -a PONTOS <<< "$E1_PONTOS"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="logs/coleta_lad/$RUN_ID"
mkdir -p "$LOG_DIR"

ATRAZO_ATIVO=0
SISTEMA_ATUAL=""
limpar_atraso() {
    if [[ "$ATRAZO_ATIVO" == "1" ]]; then
        echo "[LIMPEZA] Removendo netem de $SISTEMA_ATUAL" >&2
        ./scripts/latencia_off.sh n1 n2 n3 >&2 || true
        ATRAZO_ATIVO=0
    fi
}
ao_sair() {
    local codigo="$?"
    limpar_atraso
    if [[ "$codigo" -eq 0 ]]; then
        echo "[FINALIZADO] Coleta encerrada com sucesso em $(date -Is)"
    else
        echo "[ERRO] Coleta interrompida (status=$codigo) em $(date -Is). Verifique os logs e os manifests." >&2
    fi
    echo "Registros do controle: $LOG_DIR"
}
trap ao_sair EXIT

registrar() {
    local mensagem="$1"
    printf '\n[%s] %s\n' "$(date -Is)" "$mensagem"
    printf '%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$mensagem" >> "$LOG_DIR/fases.csv"
}

# Sem contêineres privilegiados, alguns experimentos não funcionarão no LAD.
for cmd in docker python3 tar; do command -v "$cmd" >/dev/null || { echo "Falta comando $cmd" >&2; exit 1; }; done
docker info >/dev/null 2>&1 || { echo 'Docker daemon indisponível/sem permissão no host escolhido.' >&2; exit 1; }
docker compose version >/dev/null || { echo 'Docker Compose não disponível.' >&2; exit 1; }
[[ "$PROCESSOS" =~ ^[1-9][0-9]*$ ]] || { echo 'PROCESSOS inválido' >&2; exit 1; }
[[ "$E3_ALTA" == 0 || "$E3_ALTA" == 1 ]] || { echo 'E3_ALTA deve ser 0 ou 1' >&2; exit 1; }
for n in "${PONTOS[@]}"; do [[ "$n" =~ ^[1-9][0-9]*$ ]] || { echo "N inválido: $n" >&2; exit 1; }; done
for f in scripts/ambiente.sh scripts/preparar.sh scripts/executar_e1.sh scripts/executar_e3.sh scripts/latencia_on.sh scripts/latencia_off.sh scripts/rtt.sh; do
    [[ -f "$f" ]] || { echo "Script ausente: $f" >&2; exit 1; }
done

{
    echo "inicio=$(date -Is)"
    echo "host=$(hostname)"
    echo "PROCESSOS=$PROCESSOS"
    echo "E1_PONTOS=$E1_PONTOS"
    echo "E3_ALTA=$E3_ALTA"
    echo "warmup_E1=30s duracao_E1=120s repeticoes=3"
    uname -a
    command -v lscpu >/dev/null && lscpu || true
    command -v free >/dev/null && free -h || true
    command -v df >/dev/null && df -h . || true
    docker version || true
    docker compose version || true
    git rev-parse HEAD 2>/dev/null || true
} > "$LOG_DIR/ambiente.txt" 2>&1

# Preserva arquivos oficiais anteriores antes de qualquer sobrescrita.
ANTERIORES=()
for p in gerador/resultados/E1 gerador/resultados/E3; do
    [[ -d "$p" ]] && ANTERIORES+=("$p")
done
if (( ${#ANTERIORES[@]} > 0 )); then
    registrar "Backup dos resultados E1/E3 preexistentes"
    tar -czf "$LOG_DIR/resultados_anteriores.tar.gz" "${ANTERIORES[@]}"
fi

# Só troca de sistema entre etapas, preservando os CSVs no volume montado do host.
preparar_sistema() {
    local sistema="$1"
    registrar "Alternando cluster para $sistema"
    limpar_atraso
    docker compose -f etcd.yml down -v >/dev/null 2>&1 || true
    docker compose -f cassandra.yml down -v >/dev/null 2>&1 || true
    SISTEMA_ATUAL="$sistema"
    ./scripts/ambiente.sh "$sistema"
    ./scripts/preparar.sh "$sistema"
    if [[ "$sistema" == cassandra ]]; then
        if [[ -f scripts/verificar_prontidao_e6.py ]]; then
            python3 scripts/verificar_prontidao_e6.py --timeout 300
        else
            local tentativa no tudo_ok
            tudo_ok=0
            for tentativa in $(seq 1 60); do
                tudo_ok=1
                for no in n1 n2 n3; do
                    if ! docker exec "$no" cqlsh -e 'SELECT release_version FROM system.local;' >/dev/null 2>&1; then
                        tudo_ok=0
                        break
                    fi
                done
                [[ "$tudo_ok" == 1 ]] && break
                sleep 5
            done
            [[ "$tudo_ok" == 1 ]] || { echo 'Cassandra não aceitou CQL em todos os nós.' >&2; return 1; }
        fi
    fi
}

conferir_rtt() {
    local arquivo="$1"
    # 'ping' do netshoot em Linux inclui 'rtt min/avg/max/mdev = ...'.
    python3 - "$arquivo" <<'PY'
import re, sys
p = open(sys.argv[1], encoding='utf-8').read()
m = re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev)\s*=\s*[0-9.]+/([0-9.]+)/', p)
if not m:
    raise SystemExit('ERRO: não foi possível identificar o RTT no ping; não executar E3 alta.')
ms = float(m.group(1))
print(f'RTT inter-nós medido: {ms:.2f} ms')
if not 70 <= ms <= 200:
    raise SystemExit(f'ERRO: RTT {ms:.2f} ms fora da faixa esperada (~100 ms).')
PY
}

registrar 'Início da coleta LAD (E1 e E3)'

# 1) Executa E1 dos dois sistemas antes do E3 lento, garantindo os 60 pontos primeiro.
for sistema in etcd cassandra; do
    preparar_sistema "$sistema"
    registrar "E1 $sistema: N=${E1_PONTOS}; três repetições por ponto"
    PROCESSOS="$PROCESSOS" RESETAR=0 DURACAO=120 WARMUP=30 \
        ./scripts/executar_e1.sh "$sistema" "${PONTOS[@]}"
    registrar "E1 $sistema concluído"
done

# 2) Faz E3 na condição normal para ambos antes de iniciar a condição de atraso.
for sistema in etcd cassandra; do
    preparar_sistema "$sistema"
    registrar "E3 $sistema original: 3 repetições x 10.000 pares"
    ./scripts/executar_e3.sh "$sistema" original
    registrar "E3 $sistema original concluído"
done

# 3) Faz E3 com latência somente se netem funcionar e o RTT for confirmado.
if [[ "$E3_ALTA" == 1 ]]; then
    for sistema in etcd cassandra; do
        preparar_sistema "$sistema"
        registrar "Aplicando netem +50ms por sentido em $sistema"
        ATRAZO_ATIVO=1  # Garante limpeza mesmo se a aplicação falhar em algum nó.
        ./scripts/latencia_on.sh 50ms n1 n2 n3
        RTT_ARQUIVO="$LOG_DIR/${sistema}_rtt_alta.txt"
        ./scripts/rtt.sh n1 172.20.0.12 | tee "$RTT_ARQUIVO"
        conferir_rtt "$RTT_ARQUIVO"
        registrar "E3 $sistema alta: 3 repetições x 10.000 pares"
        ./scripts/executar_e3.sh "$sistema" alta
        limpar_atraso
        registrar "E3 $sistema alta concluído"
    done
fi

# Analisar os CSVs no dia seguinte para não disputar RAM com o Cassandra.
registrar 'Todas as etapas solicitadas foram concluídas'
