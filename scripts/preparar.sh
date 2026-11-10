#!/usr/bin/env bash
# Rodar apos cluster estar saudavel. Uso: ./scripts/preparar.sh etcd|cassandra
set -euo pipefail
SISTEMA="${1:?Informe o sistema}"
if [ "$SISTEMA" = cassandra ]; then
 docker exec n1 cqlsh -e "CREATE KEYSPACE IF NOT EXISTS lab WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 3};"
 docker exec n1 cqlsh -e "CREATE TABLE IF NOT EXISTS lab.kv (k text PRIMARY KEY, v blob);"
fi
docker exec gerador python /app/carga.py "$SISTEMA" --prepare
