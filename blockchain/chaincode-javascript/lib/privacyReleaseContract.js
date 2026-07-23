"use strict";

const crypto = require("node:crypto");
const { Contract } = require("fabric-contract-api");

const KEY_PREFIX = "PRIVHEALTH_RELEASE::";
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const REQUIRED_FIELDS = [
  "schema_version",
  "release_id",
  "artifact_name",
  "dataset_hash_sha256",
  "certificate_hash_sha256",
  "method",
  "source_rows",
  "retained_rows",
  "target_k",
  "target_l",
  "achieved_k",
  "achieved_l",
  "suppression_rate",
  "information_loss",
  "hierarchy_loss",
  "privacy_satisfied",
  "quasi_identifiers",
  "sensitive_attribute",
  "generalization_levels",
  "generator_version",
  "created_at_utc"
];

function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => (
    `${JSON.stringify(key)}:${stableStringify(value[key])}`
  )).join(",")}}`;
}

function computeCertificateHash(certificate) {
  const unsigned = { ...certificate };
  delete unsigned.certificate_hash_sha256;
  return crypto
    .createHash("sha256")
    .update(stableStringify(unsigned), "utf8")
    .digest("hex");
}

function asInteger(certificate, field) {
  const value = Number(certificate[field]);
  if (!Number.isSafeInteger(value)) {
    throw new Error(`${field} must be a safe integer`);
  }
  return value;
}

function asNormalizedMetric(certificate, field) {
  const value = Number(certificate[field]);
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`${field} must be in [0, 1]`);
  }
  return value;
}

function validateCertificate(certificate) {
  for (const field of REQUIRED_FIELDS) {
    if (!(field in certificate)) {
      throw new Error(`Missing required field: ${field}`);
    }
  }
  if (certificate.schema_version !== "privhealth-release/v1") {
    throw new Error("Unsupported certificate schema version");
  }
  if (!/^[a-zA-Z0-9._-]{8,160}$/.test(certificate.release_id)) {
    throw new Error("Invalid release_id");
  }
  if (!SHA256_PATTERN.test(certificate.dataset_hash_sha256)) {
    throw new Error("dataset_hash_sha256 must be a lowercase SHA-256 digest");
  }
  if (!SHA256_PATTERN.test(certificate.certificate_hash_sha256)) {
    throw new Error(
      "certificate_hash_sha256 must be a lowercase SHA-256 digest"
    );
  }
  if (computeCertificateHash(certificate) !==
      certificate.certificate_hash_sha256) {
    throw new Error("Certificate hash does not match certificate content");
  }

  const sourceRows = asInteger(certificate, "source_rows");
  const retainedRows = asInteger(certificate, "retained_rows");
  const targetK = asInteger(certificate, "target_k");
  const targetL = asInteger(certificate, "target_l");
  const achievedK = asInteger(certificate, "achieved_k");
  const achievedL = asInteger(certificate, "achieved_l");
  asNormalizedMetric(certificate, "suppression_rate");
  asNormalizedMetric(certificate, "information_loss");
  asNormalizedMetric(certificate, "hierarchy_loss");

  if (sourceRows < 1 || retainedRows < 1 || retainedRows > sourceRows) {
    throw new Error("Invalid source/retained row counts");
  }
  if (targetK < 2 || targetL < 2) {
    throw new Error("Registration requires target_k >= 2 and target_l >= 2");
  }
  if (certificate.privacy_satisfied !== true) {
    throw new Error("Registration requires privacy_satisfied=true");
  }
  if (achievedK < targetK || achievedL < targetL) {
    throw new Error("Achieved privacy values do not meet declared targets");
  }
  if (!Array.isArray(certificate.quasi_identifiers) ||
      certificate.quasi_identifiers.length === 0) {
    throw new Error("quasi_identifiers must be a non-empty array");
  }
}

function releaseKey(releaseID) {
  return `${KEY_PREFIX}${releaseID}`;
}

function epochSeconds(timestamp) {
  if (!timestamp || timestamp.seconds === undefined) {
    throw new Error("Fabric transaction timestamp is unavailable");
  }
  return timestamp.seconds.toString();
}

class PrivacyReleaseContract extends Contract {
  async ReleaseExists(ctx, releaseID) {
    const state = await ctx.stub.getState(releaseKey(releaseID));
    return Boolean(state && state.length > 0);
  }

  async CreateRelease(ctx, certificateJSON) {
    let certificate;
    try {
      certificate = JSON.parse(certificateJSON);
    } catch (error) {
      throw new Error(`Certificate is not valid JSON: ${error.message}`);
    }
    validateCertificate(certificate);

    if (await this.ReleaseExists(ctx, certificate.release_id)) {
      throw new Error(`Release ${certificate.release_id} already exists`);
    }

    const record = {
      ...certificate,
      ledger_tx_id: ctx.stub.getTxID(),
      registered_at_epoch_seconds: epochSeconds(
        ctx.stub.getTxTimestamp()
      ),
      registering_msp: ctx.clientIdentity.getMSPID()
    };
    await ctx.stub.putState(
      releaseKey(certificate.release_id),
      Buffer.from(stableStringify(record))
    );
    await ctx.stub.setEvent(
      "PrivacyReleaseRegistered",
      Buffer.from(stableStringify({
        release_id: certificate.release_id,
        dataset_hash_sha256: certificate.dataset_hash_sha256,
        certificate_hash_sha256: certificate.certificate_hash_sha256
      }))
    );
    return stableStringify(record);
  }

  async ReadRelease(ctx, releaseID) {
    const state = await ctx.stub.getState(releaseKey(releaseID));
    if (!state || state.length === 0) {
      throw new Error(`Release ${releaseID} does not exist`);
    }
    return state.toString();
  }

  async VerifyRelease(ctx, releaseID, presentedDatasetHash) {
    if (!SHA256_PATTERN.test(presentedDatasetHash)) {
      throw new Error("Presented hash must be a lowercase SHA-256 digest");
    }
    const record = JSON.parse(await this.ReadRelease(ctx, releaseID));
    return stableStringify({
      release_id: releaseID,
      matches: record.dataset_hash_sha256 === presentedDatasetHash,
      registered_hash: record.dataset_hash_sha256,
      presented_hash: presentedDatasetHash
    });
  }
}

module.exports = PrivacyReleaseContract;
module.exports.computeCertificateHash = computeCertificateHash;
module.exports.stableStringify = stableStringify;
module.exports.validateCertificate = validateCertificate;
