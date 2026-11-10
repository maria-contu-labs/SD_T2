#!/usr/bin/env bash
# Uso: ./rtt.sh n1 172.20.0.12   (mede o RTT de n1 ate o IP indicado, na rede entre nos)
set -euo pipefail
docker run --rm --net "container:$1" nicolaka/netshoot ping -c 5 "$2"
