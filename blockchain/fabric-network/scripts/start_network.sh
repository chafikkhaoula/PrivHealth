#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"

"${SCRIPT_DIRECTORY}/bootstrap_runtime.sh"
source "${SCRIPT_DIRECTORY}/network_env.sh"
cd "${NETWORK_ROOT}"

for container_name in \
  privhealth-orderer \
  privhealth-peer0-hospital1 \
  privhealth-peer0-hospital2
do
  if docker container inspect "${container_name}" >/dev/null 2>&1; then
    echo "Container ${container_name} already exists." >&2
    echo "Use scripts/start_existing_network.sh instead." >&2
    exit 1
  fi
done

for port in 17050 17053 17051 19051 19443 19444 19445; do
  if ss -ltnH | awk '{print $4}' | grep -Eq "[:.]${port}$"; then
    echo "Required PrivHealth port ${port} is already in use." >&2
    exit 1
  fi
done

mkdir -p \
  "${NETWORK_ROOT}/organizations" \
  "${NETWORK_ROOT}/channel-artifacts"

if [[ ! -d "${NETWORK_ROOT}/organizations/ordererOrganizations" ]]; then
  cryptogen generate \
    --config="${NETWORK_ROOT}/crypto-config.yaml" \
    --output="${NETWORK_ROOT}/organizations"
fi

export FABRIC_CFG_PATH="${NETWORK_ROOT}"
configtxgen \
  -profile PrivHealthChannelGenesis \
  -outputBlock "${NETWORK_ROOT}/channel-artifacts/${CHANNEL_NAME}.block" \
  -channelID "${CHANNEL_NAME}"
export FABRIC_CFG_PATH="${RUNTIME_ROOT}/config"

docker compose \
  -p privhealth \
  -f "${NETWORK_ROOT}/docker-compose.yaml" \
  up -d

for attempt in $(seq 1 30); do
  running_count="$(
    docker ps \
      --filter label=application=privhealth \
      --filter status=running \
      --format '{{.Names}}' \
      | wc -l
  )"
  if [[ "${running_count}" -eq 3 ]]; then
    break
  fi
  if [[ "${attempt}" -eq 30 ]]; then
    echo "PrivHealth containers did not become ready." >&2
    docker ps -a --filter label=application=privhealth
    exit 1
  fi
  sleep 1
done

osnadmin channel join \
  --channelID "${CHANNEL_NAME}" \
  --config-block "${NETWORK_ROOT}/channel-artifacts/${CHANNEL_NAME}.block" \
  -o "${ORDERER_ADMIN_ADDRESS}" \
  --ca-file "${ORDERER_CA}" \
  --client-cert "${ORDERER_ADMIN_TLS_CERT}" \
  --client-key "${ORDERER_ADMIN_TLS_KEY}"

use_hospital1
peer channel join \
  --blockpath "${NETWORK_ROOT}/channel-artifacts/${CHANNEL_NAME}.block"

use_hospital2
peer channel join \
  --blockpath "${NETWORK_ROOT}/channel-artifacts/${CHANNEL_NAME}.block"

echo
echo "PrivHealth Fabric network started successfully."
docker ps \
  --filter label=application=privhealth \
  --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
