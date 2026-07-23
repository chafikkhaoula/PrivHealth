#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"

docker compose \
  -p privhealth \
  -f "${NETWORK_ROOT}/docker-compose.yaml" \
  start

docker ps \
  --filter label=application=privhealth \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
