# ULPF Validation Rules

**Version:** 2.0  
**Spec base:** [metadataGuide.md](../metadataGuide.md) §8  
**Enforced by:** Vector Server Engine (`stamp_and_verify` transform) and `scripts/validate_ocsf.py`

---

## Overview

Validation happens in two places:

1. **Vector Server Engine (runtime)** — enforced in the `stamp_and_verify` VRL transform. Events failing here are routed to the DLQ (`ulpf-dlq`).
2. **Post-hoc validator** — `scripts/validate_ocsf.py` checks the OCSF output files for spec compliance.

---

## 1. Vector Server Engine — Ingest-time Rules

These rules run on every event consumed from Kafka (`ulpf-raw-logs` topic).

### 1.1 Required Field Presence

All of the following fields must be present and non-null:

```
envelope_version, site_id, agent_id (or collector_id), seq,
collected_at, source.type, raw, raw_sha256, raw_len
```

**Action on failure:** route to `ulpf-dlq` topic with `dlq_reason: "missing_required_fields"`.

### 1.2 Envelope Version Check

```
envelope_version == 1
```

**Action on failure:** route to DLQ with `dlq_reason: "unsupported_envelope_version"`.

### 1.3 SHA-256 Integrity Verification

```
sha256(raw.encode('utf-8')) == raw_sha256
```

- `agent_hash` = `raw_sha256` as received from edge agent
- `server_hash` = SHA-256 recomputed by server engine
- `integrity.verified = (agent_hash == server_hash)`

**Action on failure:** `integrity.verified = false`; route to DLQ with `dlq_reason: "integrity_check_failed"`.

### 1.4 Byte Length Verification

```
len(raw.encode('utf-8')) == raw_len
```

- `integrity.length_verified = (computed_len == raw_len)`

**Action on failure:** `integrity.length_verified = false`; route to DLQ with `dlq_reason: "length_mismatch"`.

### 1.5 `source.type` Registry Check

`source.type` must be one of the values in the [source-type-registry.md](source-type-registry.md).

**Action on failure:** route to DLQ with `dlq_reason: "unknown_source_type"`.

### 1.6 `collected_at` Sanity Check

```
collected_at > 0
collected_at must be epoch milliseconds (13-digit integer)
```

**Action on failure:** route to DLQ with `dlq_reason: "invalid_timestamp"`.

### 1.7 ULID Generation

After all checks pass, the central parser generates:
```
event_id = ulid(seed_ms=collected_at)
ingested_at = current_epoch_ms()
```

ULID is monotonically sortable by `collected_at` time component.

---

## 2. `validate_ocsf.py` — Post-hoc Rules

Run manually or in CI against `output/ocsf-events.ndjson`.

```bash
python3 scripts/validate_ocsf.py
```

### 2.1 OCSF Structural Rules

| Rule | Check |
|------|-------|
| `class_uid` present | Integer, must match known OCSF class |
| `class_name` present | String, must match `class_uid` |
| `time` present | Integer epoch seconds |
| `metadata.uid` present | ULID format string |
| `metadata.version` = `"1.3.0"` | Exact string |
| `metadata.log_name` present | Must be in source type registry |
| `metadata.logged_time` present | Integer epoch milliseconds |
| `metadata.processed_time` present | Integer epoch milliseconds |
| `metadata.product.name` present | Non-empty string |
| `metadata.product.vendor_name` present | Non-empty string |

### 2.2 Integrity Rules (checked in OCSF events)

| Rule | Check |
|------|-------|
| `metadata.integrity.verified` | Must be `true` |
| `metadata.integrity.length_verified` | Must be `true` |
| `metadata.integrity.algorithm` | Must be `"sha256"` |
| `metadata.integrity.collector_hash` | 64-char hex string |
| `metadata.integrity.central_hash` | 64-char hex string, must equal `collector_hash` |

### 2.3 Lossless Rules

| Rule | Check |
|------|-------|
| `unmapped.raw_data` present | Non-empty string |
| `unmapped.envelope` present | Object containing full collector envelope |
| `unmapped.envelope.source.type` | Must match `metadata.log_name` |
| `unmapped.envelope.raw_sha256` | Must match `metadata.integrity.collector_hash` |

### 2.4 Test Results Reference

Last confirmed run output:
```
Events ingested                  194
Preservation envelopes stamped   194
OCSF normalized events           194
SHA256 integrity verified        194 / 194 (100%)
Byte length verified             194 / 194 (100%)
Validation rule errors           0
RESULT: PASSED ✓
```

---

## 3. DLQ — Dead Letter Queue

Events failing ingest-time validation are written to:

- **Kafka topic:** `ulpf-dlq`
- **Additional fields appended:**
  - `dlq_reason`: string code (see §1 above)
  - `dlq_at`: epoch ms when the event was DLQ'd
  - `dlq_node`: central parser node that rejected it

> [!TIP]
> DLQ events are retained for 7 days (default). They can be replayed after fixing the collector or data issue using `scripts/log_replay.py`.

---

## 4. Quick Reference — Validation Checklist

```
✅ envelope_version == 1
✅ All required fields present (site_id, collector_id, seq, collected_at, source.type, raw, raw_sha256, raw_len)
✅ source.type in registry
✅ sha256(raw) == raw_sha256
✅ len(raw) == raw_len
✅ collected_at is 13-digit epoch ms integer
✅ event_id is valid ULID
✅ integrity.verified == true
✅ integrity.length_verified == true
✅ unmapped.raw_data present in OCSF output
✅ unmapped.envelope present in OCSF output
✅ metadata.logged_time == collected_at
✅ metadata.uid == event_id
```
