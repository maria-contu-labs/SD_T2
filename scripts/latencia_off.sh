#!/usr/bin/env bash
# Uso: ./latencia_off.sh n1 n2 n3
set -euo pipefail
for c in "$@"; do
  docker run --rm --net "container:$c" --cap-add NET_ADMIN nicolaka/netshoot sh -c '
    IF=$(ip -o -4 addr show | awk "\$4 ~ /^172.20.0./ {print \$2}")
    tc qdisc del dev "$IF" root 2>/dev/null || true
    echo "netem removido em $IF"'
done
