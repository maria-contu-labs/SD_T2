#!/usr/bin/env bash
# Isola o no n1 da rede entre nos. n1 continua acessivel aos clientes (rede lab_clientes).
set -euo pipefail
docker network disconnect lab_cluster n1
echo "n1 isolado de n2 e n3 em $(date +%T)"
