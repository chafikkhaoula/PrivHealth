#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 RELEASE_ID" >&2
  exit 1
fi

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIRECTORY}/network_env.sh"

QUERY_SPEC="$(
  python3 - "$1" <<'PY'
import json
import sys

print(json.dumps({
    "function": "ReadRelease",
    "Args": [sys.argv[1]],
}, separators=(",", ":")))
PY
)"

use_hospital1
peer chaincode query \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --ctor "${QUERY_SPEC}"
