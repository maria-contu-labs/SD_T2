#!/usr/bin/env bash
# Uso: ./latencia_on.sh 50ms n1 n2 n3
# Acrescenta atraso fixo na saida de cada no, apenas na rede entre nos (172.20.0.0/24).
# Atraso de 50ms por sentido resulta em RTT de 100ms entre nos.
set -euo pipefail
ATRASO="$1"; shift
for c in "$@"; do
  docker run --rm --net "container:$c" --cap-add NET_ADMIN -e D="$ATRASO" nicolaka/netshoot sh -c '
    IF=$(ip -o -4 addr show | awk "\$4 ~ /^172.20.0./ {print \$2}")
    tc qdisc replace dev "$IF" root netem delay "$D"
    echo "$(hostname): netem $D em $IF"'
done
