"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const PrivacyReleaseContract = require(
  "../lib/privacyReleaseContract"
);
const {
  computeCertificateHash
} = require("../lib/privacyReleaseContract");

class MemoryStub {
  constructor() {
    this.state = new Map();
    this.event = null;
  }

  async getState(key) {
    return this.state.get(key) || Buffer.alloc(0);
  }

  async putState(key, value) {
    this.state.set(key, value);
  }

  async setEvent(name, payload) {
    this.event = { name, payload };
  }

  getTxID() {
    return "tx-test-001";
  }

  getTxTimestamp() {
    return { seconds: { toString: () => "1784800000" } };
  }
}

function context() {
  return {
    stub: new MemoryStub(),
    clientIdentity: {
      getMSPID: () => "Org1MSP"
    }
  };
}

function certificate() {
  const value = {
    schema_version: "privhealth-release/v1",
    release_id: "ph-0123456789abcdef-adaptive-n10000-k5-l2",
    artifact_name: "adaptive_n10000_k5_l2.csv",
    dataset_hash_sha256: "a".repeat(64),
    method: "adaptive",
    source_rows: 10000,
    retained_rows: 7054,
    target_k: 5,
    target_l: 2,
    achieved_k: 5,
    achieved_l: 2,
    suppression_rate: "0.294600",
    information_loss: "0.412167",
    hierarchy_loss: "0.166667",
    privacy_satisfied: true,
    quasi_identifiers: [
      "age",
      "gender",
      "race",
      "marital",
      "zip_code"
    ],
    sensitive_attribute: "condition",
    generalization_levels: {
      age: 1,
      gender: 0,
      marital: 0,
      race: 0,
      zip_code: 4
    },
    generator_version: "privhealth-v0.3",
    created_at_utc: "2026-07-23T12:00:00Z"
  };
  value.certificate_hash_sha256 = computeCertificateHash(value);
  return value;
}

test("creates and reads an immutable privacy-valid release", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const original = certificate();

  const created = JSON.parse(
    await contract.CreateRelease(ctx, JSON.stringify(original))
  );
  const read = JSON.parse(
    await contract.ReadRelease(ctx, original.release_id)
  );

  assert.equal(created.release_id, original.release_id);
  assert.deepEqual(read, created);
  assert.equal(created.registering_msp, "Org1MSP");
  assert.equal(ctx.stub.event.name, "PrivacyReleaseRegistered");
});

test("rejects a release that failed privacy", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const invalid = certificate();
  invalid.privacy_satisfied = false;
  invalid.certificate_hash_sha256 = computeCertificateHash(invalid);

  await assert.rejects(
    contract.CreateRelease(ctx, JSON.stringify(invalid)),
    /privacy_satisfied=true/
  );
});

test("rejects achieved k below target k", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const invalid = certificate();

  invalid.achieved_k = invalid.target_k - 1;
  invalid.certificate_hash_sha256 = computeCertificateHash(invalid);

  await assert.rejects(
    contract.CreateRelease(ctx, JSON.stringify(invalid)),
    /Achieved privacy values do not meet declared targets/
  );
});

test("rejects achieved l below target l", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const invalid = certificate();

  invalid.achieved_l = invalid.target_l - 1;
  invalid.certificate_hash_sha256 = computeCertificateHash(invalid);

  await assert.rejects(
    contract.CreateRelease(ctx, JSON.stringify(invalid)),
    /Achieved privacy values do not meet declared targets/
  );
});

test("rejects certificate metadata tampering", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const tampered = certificate();
  tampered.information_loss = "0.100000";

  await assert.rejects(
    contract.CreateRelease(ctx, JSON.stringify(tampered)),
    /Certificate hash does not match/
  );
});

test("rejects duplicate release identifiers", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const original = certificate();

  await contract.CreateRelease(ctx, JSON.stringify(original));
  await assert.rejects(
    contract.CreateRelease(ctx, JSON.stringify(original)),
    /already exists/
  );
});

test("verifies a presented dataset hash", async () => {
  const contract = new PrivacyReleaseContract();
  const ctx = context();
  const original = certificate();
  await contract.CreateRelease(ctx, JSON.stringify(original));

  const match = JSON.parse(
    await contract.VerifyRelease(
      ctx,
      original.release_id,
      original.dataset_hash_sha256
    )
  );
  const mismatch = JSON.parse(
    await contract.VerifyRelease(
      ctx,
      original.release_id,
      "b".repeat(64)
    )
  );

  assert.equal(match.matches, true);
  assert.equal(mismatch.matches, false);
});
