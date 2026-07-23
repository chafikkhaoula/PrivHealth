#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"

docker compose \
  -p privhealth \
  -f "${NETWORK_ROOT}/docker-compose.yaml" \
  stop

echo "PrivHealth containers stopped. Ledger volumes were preserved."
