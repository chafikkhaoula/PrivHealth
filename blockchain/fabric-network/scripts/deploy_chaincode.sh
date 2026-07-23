#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"
CHAINCODE_PATH="$(cd "${NETWORK_ROOT}/../chaincode-javascript" && pwd)"
ARTIFACT_DIRECTORY="${NETWORK_ROOT}/chaincode-artifacts"
CHAINCODE_VERSION=0.3
CHAINCODE_SEQUENCE=1
CHAINCODE_LABEL=privhealth_0.3
CHAINCODE_PACKAGE="${ARTIFACT_DIRECTORY}/${CHAINCODE_LABEL}.tar.gz"

source "${SCRIPT_DIRECTORY}/network_env.sh"

mkdir -p "${ARTIFACT_DIRECTORY}"

if [[ ! -d "${CHAINCODE_PATH}/node_modules" ]]; then
  echo "Run npm install inside ${CHAINCODE_PATH} first." >&2
  exit 1
fi

if [[ ! -f "${CHAINCODE_PACKAGE}" ]]; then
  peer lifecycle chaincode package "${CHAINCODE_PACKAGE}" \
    --path "${CHAINCODE_PATH}" \
    --lang node \
    --label "${CHAINCODE_LABEL}"
fi

PACKAGE_ID="$(
  peer lifecycle chaincode calculatepackageid "${CHAINCODE_PACKAGE}"
)"
echo "Package ID: ${PACKAGE_ID}"

use_hospital1
peer lifecycle chaincode install "${CHAINCODE_PACKAGE}"

use_hospital2
peer lifecycle chaincode install "${CHAINCODE_PACKAGE}"

use_hospital1
peer lifecycle chaincode approveformyorg \
  -o "${ORDERER_ADDRESS}" \
  --ordererTLSHostnameOverride "${ORDERER_HOSTNAME}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --version "${CHAINCODE_VERSION}" \
  --package-id "${PACKAGE_ID}" \
  --sequence "${CHAINCODE_SEQUENCE}" \
  --tls \
  --cafile "${ORDERER_CA}"

use_hospital2
peer lifecycle chaincode approveformyorg \
  -o "${ORDERER_ADDRESS}" \
  --ordererTLSHostnameOverride "${ORDERER_HOSTNAME}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --version "${CHAINCODE_VERSION}" \
  --package-id "${PACKAGE_ID}" \
  --sequence "${CHAINCODE_SEQUENCE}" \
  --tls \
  --cafile "${ORDERER_CA}"

peer lifecycle chaincode checkcommitreadiness \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --version "${CHAINCODE_VERSION}" \
  --sequence "${CHAINCODE_SEQUENCE}" \
  --tls \
  --cafile "${ORDERER_CA}" \
  --output json

use_hospital1
peer lifecycle chaincode commit \
  -o "${ORDERER_ADDRESS}" \
  --ordererTLSHostnameOverride "${ORDERER_HOSTNAME}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --version "${CHAINCODE_VERSION}" \
  --sequence "${CHAINCODE_SEQUENCE}" \
  --tls \
  --cafile "${ORDERER_CA}" \
  --peerAddresses "${HOSPITAL1_PEER_ADDRESS}" \
  --tlsRootCertFiles "${HOSPITAL1_CA}" \
  --peerAddresses "${HOSPITAL2_PEER_ADDRESS}" \
  --tlsRootCertFiles "${HOSPITAL2_CA}"

peer lifecycle chaincode querycommitted \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}"
