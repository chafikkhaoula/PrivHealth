# Isolated PrivHealth Fabric Network

This directory defines a self-contained Hyperledger Fabric 2.5.15 network for
PrivHealth. It does not use the container names, ports, channel, chaincode,
network, crypto material, or ledger volumes of any existing Fabric deployment.

## Isolation map

| Resource | PrivHealth value |
| --- | --- |
| Docker project | `privhealth` |
| Docker network | `privhealth_fabric` |
| Orderer container | `privhealth-orderer` |
| Hospital 1 peer | `privhealth-peer0-hospital1` |
| Hospital 2 peer | `privhealth-peer0-hospital2` |
| Channel | `privhealthchannel` |
| Chaincode | `privhealth` |
| Host ports | `17050`, `17053`, `17051`, `19051`, `19443`–`19445` |
| Ledger volumes | names beginning with `privhealth_` |

The bootstrap script copies the Fabric binaries and configuration from
`/home/khcha/projects/fabric-samples` into this directory. It reads the source
installation but does not modify it.

## Start a new network

```bash
cd ~/projects/privhealth/blockchain/fabric-network
chmod +x scripts/*.sh
./scripts/start_network.sh
```

The script generates new cryptographic material, creates
`privhealthchannel`, starts only the three `privhealth-*` containers, and joins
the two hospital peers.

## Deploy the release registry

```bash
cd ~/projects/privhealth/blockchain/chaincode-javascript
npm install

cd ~/projects/privhealth/blockchain/fabric-network
./scripts/deploy_chaincode.sh
```

## Register and verify a release

```bash
./scripts/register_release.sh \
  ~/projects/privhealth/results/final_synthea_v02_seed42/release_n10000_k5_l2.json
```

```bash
./scripts/query_release.sh \
  ph-9001a7ca1b9bfaa3-adaptive-n10000-k5-l2
```

```bash
./scripts/verify_release.sh \
  ph-9001a7ca1b9bfaa3-adaptive-n10000-k5-l2 \
  ~/projects/privhealth/results/final_synthea_v02_seed42/adaptive_n10000_k5_l2.csv
```

## Benchmark the registry

The benchmark performs two unreported warm-ups and 30 measured sequential
attempts for each operation by default:

- `register`: two-peer-endorsed write with commit-event confirmation;
- `read`: world-state query through Hospital 1;
- `verify`: on-chain comparison of a presented hash with the registered hash.

```bash
./scripts/benchmark_registry.sh \
  --iterations 30 \
  --warmups 2
```

Each registration receives a unique benchmark release identifier. Results are
written to a timestamped directory under `results/` as raw measurements,
summary CSV/JSON, and environment metadata. Local CSV hashing is excluded from
the measured `verify` query so that blockchain latency remains separately
identifiable.

## Stop without deleting

```bash
./scripts/stop_network.sh
```

This stops only the three `privhealth-*` containers and preserves the
PrivHealth ledger volumes. To restart them:

```bash
./scripts/start_existing_network.sh
```

Do not use another project's `network.sh` for this deployment.
