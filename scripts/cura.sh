#!/usr/bin/env bash
# Reconecta n1 a rede entre nos, com o mesmo IP.
set -euo pipefail
docker network connect --ip 172.20.0.11 lab_cluster n1
echo "particao curada em $(date +%T)"
