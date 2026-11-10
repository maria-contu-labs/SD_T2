#!/usr/bin/env bash
# Uso: ./scripts/ambiente.sh etcd|cassandra
# Sobe o cluster e aguarda tres membros prontos.
set -euo pipefail
cd "$(dirname "$0")/.."
SISTEMA="${1:?Informe etcd ou cassandra}"
case "$SISTEMA" in etcd|cassandra) ;; *) echo 'Sistema invalido' >&2; exit 1;; esac

docker compose -f "$SISTEMA.yml" up --build -d
if [ "$SISTEMA" = etcd ]; then
  echo 'Conferindo o consenso Raft e a disponibilidade dos tres endpoints...'
  for tentativa in $(seq 1 60); do
    if STATUS=$(docker exec n1 etcdctl --endpoints=http://172.21.0.11:2379,http://172.21.0.12:2379,http://172.21.0.13:2379 endpoint status -w table 2>/dev/null); then
      # EtcdCtl exibe um endpoint por linha; exige tres endpoints e um lider.
      if [ "$(printf '%s\n' "$STATUS" | grep -Ec 'http://172[.]21[.]0[.](11|12|13):2379' || true)" -eq 3 ] && printf '%s\n' "$STATUS" | grep -q 'true'; then
        printf '%s\n' "$STATUS"
        echo 'Etcd pronto para os testes.'
        exit 0
      fi
    fi
    sleep 2
  done
  echo 'Cluster etcd nao ficou pronto. Confira: docker compose -f etcd.yml logs --tail=80' >&2
  exit 1
else
  echo 'Conferindo o status dos tres nos Cassandra (UN = Up/Normal)...'
  for tentativa in $(seq 1 60); do
    if STATUS=$(docker exec n1 nodetool status 2>/dev/null); then
      if [ "$(printf '%s\n' "$STATUS" | grep -Ec '^UN[[:space:]]+' || true)" -eq 3 ]; then
        printf '%s\n' "$STATUS"
        echo 'Cassandra pronto para os testes.'
        exit 0
      fi
    fi
    sleep 5
  done
  echo 'Cluster Cassandra nao ficou pronto. Confira: docker compose -f cassandra.yml logs --tail=80' >&2
  exit 1
fi
