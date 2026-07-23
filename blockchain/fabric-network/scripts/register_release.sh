#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/release-certificate.json" >&2
  exit 1
fi

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIRECTORY}/network_env.sh"

CERTIFICATE_PATH="$(realpath "$1")"
if [[ ! -f "${CERTIFICATE_PATH}" ]]; then
  echo "Certificate not found: ${CERTIFICATE_PATH}" >&2
  exit 1
fi

INVOKE_SPEC="$(
  python3 - "${CERTIFICATE_PATH}" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
certificate = json.loads(path.read_text(encoding="utf-8"))
certificate_json = json.dumps(
    certificate,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
)
print(json.dumps({
    "function": "CreateRelease",
    "Args": [certificate_json],
}, separators=(",", ":")))
PY
)"

use_hospital1
peer chaincode invoke \
  -o "${ORDERER_ADDRESS}" \
  --ordererTLSHostnameOverride "${ORDERER_HOSTNAME}" \
  --tls \
  --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --peerAddresses "${HOSPITAL1_PEER_ADDRESS}" \
  --tlsRootCertFiles "${HOSPITAL1_CA}" \
  --peerAddresses "${HOSPITAL2_PEER_ADDRESS}" \
  --tlsRootCertFiles "${HOSPITAL2_CA}" \
  --waitForEvent \
  --waitForEventTimeout 60s \
  --ctor "${INVOKE_SPEC}"
