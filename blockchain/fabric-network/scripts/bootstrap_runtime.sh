#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_ROOT="$(cd "${SCRIPT_DIRECTORY}/.." && pwd)"
SOURCE_ROOT="${FABRIC_SOURCE_ROOT:-/home/khcha/projects/fabric-samples}"
RUNTIME_ROOT="${NETWORK_ROOT}/runtime"

if [[ ! -x "${SOURCE_ROOT}/bin/peer" ]]; then
  echo "Fabric peer binary not found at ${SOURCE_ROOT}/bin/peer" >&2
  exit 1
fi
if [[ ! -f "${SOURCE_ROOT}/config/core.yaml" ]]; then
  echo "Fabric core.yaml not found at ${SOURCE_ROOT}/config/core.yaml" >&2
  exit 1
fi

mkdir -p "${RUNTIME_ROOT}"

if [[ ! -d "${RUNTIME_ROOT}/bin" ]]; then
  cp -a "${SOURCE_ROOT}/bin" "${RUNTIME_ROOT}/bin"
fi
if [[ ! -d "${RUNTIME_ROOT}/config" ]]; then
  cp -a "${SOURCE_ROOT}/config" "${RUNTIME_ROOT}/config"
fi

echo "PrivHealth-local Fabric runtime is ready:"
"${RUNTIME_ROOT}/bin/peer" version
