# PrivHealth Privacy Release Registry

This module adds a narrow permissioned-blockchain contribution to PrivHealth.
Clinical rows and released CSV files remain off-chain. The Hyperledger Fabric
ledger stores only a release certificate containing:

- the SHA-256 digest of the released artifact;
- the target and achieved `k` and `l`;
- suppression and information-loss measurements;
- the applied generalization levels;
- the generator version and registering organization.

The smart contract is create-only. It has no update or delete transaction. A
release is rejected unless `privacy_satisfied=true`, `achieved_k >= target_k`,
`achieved_l >= target_l`, and the certificate digest is valid.

## Local validation

```bash
cd ~/projects/privhealth
source .venv/bin/activate
python -m unittest discover -s tests -v

cd blockchain/chaincode-javascript
npm install
npm test
```

## Create the first certificate

```bash
cd ~/projects/privhealth
source .venv/bin/activate

python scripts/create_release_certificate.py \
  --released-csv results/final_synthea_v02_seed42/adaptive_n10000_k5_l2.csv \
  --summary-csv results/final_synthea_v02_seed42/summary.csv \
  --dataset-size 10000 \
  --k 5 \
  --l 2 \
  --method adaptive \
  --output results/final_synthea_v02_seed42/release_n10000_k5_l2.json
```

Deployment is intentionally separated from local validation. Before deploying
to an existing multi-organization channel, inspect its committed chaincodes,
channel members, and lifecycle approval policy. This avoids changing a running
network with incorrect assumptions about its governance.
