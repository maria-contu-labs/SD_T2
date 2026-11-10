#!/usr/bin/env bash
# Uso: ./scripts/falha.sh n1|n2|n3
set -euo pipefail
NO="${1:?Informe o no}"
case "$NO" in n1|n2|n3) ;; *) exit 1;; esac
printf 'FALHA,%s,%s\n' "$NO" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker kill "$NO"
