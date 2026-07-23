#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 RELEASE_ID /absolute/path/to/released.csv" >&2
  exit 1
fi

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIRECTORY}/network_env.sh"

RELEASE_ID="$1"
RELEASED_CSV="$(realpath "$2")"
DATASET_HASH="$(sha256sum "${RELEASED_CSV}" | awk '{print $1}')"

QUERY_SPEC="$(
  python3 - "${RELEASE_ID}" "${DATASET_HASH}" <<'PY'
import json
import sys

print(json.dumps({
    "function": "VerifyRelease",
    "Args": [sys.argv[1], sys.argv[2]],
}, separators=(",", ":")))
PY
)"

use_hospital1
peer chaincode query \
  --channelID "${CHANNEL_NAME}" \
  --name "${CHAINCODE_NAME}" \
  --ctor "${QUERY_SPEC}"
