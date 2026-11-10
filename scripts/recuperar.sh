#!/usr/bin/env bash
set -euo pipefail
NO="${1:?Informe o no}"
case "$NO" in n1|n2|n3) ;; *) exit 1;; esac
printf 'RECUPERAR,%s,%s\n' "$NO" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker start "$NO"
