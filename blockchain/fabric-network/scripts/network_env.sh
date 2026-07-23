#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"
PROJECT_ROOT="$(cd "${NETWORK_ROOT}/../.." && pwd)"
RUNTIME_ROOT="${NETWORK_ROOT}/runtime"

export PATH="${RUNTIME_ROOT}/bin:${PATH}"
export FABRIC_CFG_PATH="${RUNTIME_ROOT}/config"
export CORE_PEER_TLS_ENABLED=true

export CHANNEL_NAME=privhealthchannel
export CHAINCODE_NAME=privhealth
export ORDERER_ADDRESS=localhost:17050
export ORDERER_ADMIN_ADDRESS=localhost:17053
export ORDERER_HOSTNAME=orderer.privhealth.local
export ORDERER_CA="${NETWORK_ROOT}/organizations/ordererOrganizations/privhealth.local/tlsca/tlsca.privhealth.local-cert.pem"
export ORDERER_ADMIN_TLS_CERT="${NETWORK_ROOT}/organizations/ordererOrganizations/privhealth.local/orderers/orderer.privhealth.local/tls/server.crt"
export ORDERER_ADMIN_TLS_KEY="${NETWORK_ROOT}/organizations/ordererOrganizations/privhealth.local/orderers/orderer.privhealth.local/tls/server.key"

export HOSPITAL1_CA="${NETWORK_ROOT}/organizations/peerOrganizations/hospital1.privhealth.local/tlsca/tlsca.hospital1.privhealth.local-cert.pem"
export HOSPITAL2_CA="${NETWORK_ROOT}/organizations/peerOrganizations/hospital2.privhealth.local/tlsca/tlsca.hospital2.privhealth.local-cert.pem"
export HOSPITAL1_PEER_ADDRESS=localhost:17051
export HOSPITAL2_PEER_ADDRESS=localhost:19051

use_hospital1() {
  export CORE_PEER_LOCALMSPID=Hospital1MSP
  export CORE_PEER_TLS_ROOTCERT_FILE="${HOSPITAL1_CA}"
  export CORE_PEER_MSPCONFIGPATH="${NETWORK_ROOT}/organizations/peerOrganizations/hospital1.privhealth.local/users/Admin@hospital1.privhealth.local/msp"
  export CORE_PEER_ADDRESS="${HOSPITAL1_PEER_ADDRESS}"
}

use_hospital2() {
  export CORE_PEER_LOCALMSPID=Hospital2MSP
  export CORE_PEER_TLS_ROOTCERT_FILE="${HOSPITAL2_CA}"
  export CORE_PEER_MSPCONFIGPATH="${NETWORK_ROOT}/organizations/peerOrganizations/hospital2.privhealth.local/users/Admin@hospital2.privhealth.local/msp"
  export CORE_PEER_ADDRESS="${HOSPITAL2_PEER_ADDRESS}"
}
