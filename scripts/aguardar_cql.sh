#!/usr/bin/env bash
# Espera os tres coordenadores Cassandra aceitarem conexoes CQL.
set -euo pipefail

TENTATIVAS="${TENTATIVAS:-40}"
INTERVALO="${INTERVALO:-5}"

for tentativa in $(seq 1 "$TENTATIVAS"); do
  if docker exec gerador python -c '
import socket
hosts = ["172.21.0.11", "172.21.0.12", "172.21.0.13"]
for host in hosts:
    with socket.create_connection((host, 9042), timeout=3):
        pass
' >/dev/null 2>&1; then
    echo "CQL acessivel nos tres nos (tentativa $tentativa)."
    exit 0
  fi
  echo "Aguardando Cassandra CQL ($tentativa/$TENTATIVAS)..."
  sleep "$INTERVALO"
done

echo "Erro: CQL nao ficou acessivel nos tres nos." >&2
exit 1
