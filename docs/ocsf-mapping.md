# ULPF OCSF 1.3 Normalization Mapping

**Version:** 1.0  
**OCSF version:** 1.3.0  
**Spec base:** [metadataGuide.md](../metadataGuide.md) §3  
**Verified against:** `output/ocsf-events.ndjson` (194 events, 0 validation errors)

---

## Overview

The central parser normalizes every event to an [OCSF 1.3](https://schema.ocsf.io/) class determined by `source.type`.  
The original raw envelope is always preserved in `unmapped.envelope` for lossless recovery.

---

## 1. OCSF Class Assignment by `source.type`

| `source.type` | OCSF `class_uid` | `class_name` | `category_uid` | Event count (test) |
|---------------|-----------------|--------------|---------------|-------------------|
| `fw.cisco.asa` | 4002 | Network Activity | 4 | 20 |
| `linux.auth` | 4001 | Operating System Events | 4 | 20 |
| `fw.paloalto` | 4002 | Network Activity | 4 | 20 |
| `siem.qradar` | 4002 | Network Activity | 4 | 20 |
| `web.nginx.access` | 4002 | Network Activity | 4 | 20 |
| `cloud.aws.cloudtrail` | 6003 | API Activity | 6 | 10 |
| `k8s.audit` | 6003 | API Activity | 6 | 10 |
| `iot.sensor` | 2001 | Device Activity | 2 | 15 |
| `db.postgres` | 4003 | Database Activity | 4 | 19 |
| `windows.security` | 4801 | Audit Activity | 4 | 40 |
| `windows.sysmon` | 4801 | Audit Activity | 4 | (included in windows.security count) |

---

## 2. Common `metadata.*` Field Mapping

These fields are set on **every** OCSF event regardless of `source.type`.

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `metadata.uid` | `event_id` | ULID assigned by central parser |
| `metadata.version` | hardcoded | `"1.3.0"` |
| `metadata.logged_time` | `collected_at` | Epoch ms integer — time collector wrapped the event |
| `metadata.processed_time` | `ingested_at` | Epoch ms integer — time central parser stamped the event |
| `metadata.log_name` | `source.type` | Canonical registry key (e.g. `"fw.cisco.asa"`) |
| `metadata.log_provider` | `source.transport` | Transport method (e.g. `"file"`, `"syslog_udp"`) |
| `metadata.product.name` | `source.product` | Product name from envelope |
| `metadata.product.vendor_name` | `source.vendor` | Vendor name from envelope |
| `metadata.product.version` | `source.product_version` | Product version from envelope |
| `metadata.integrity` | `integrity.*` | Full integrity object (see below) |

### `metadata.integrity` Object

```json
{
  "algorithm": "sha256",
  "collector_hash": "<hex>",
  "central_hash": "<hex>",
  "verified": true,
  "length_verified": true
}
```

---

## 3. Per-source-type Field Mappings

### 3.1 `fw.cisco.asa` → Network Activity (4002)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | parsed from `raw` | Epoch seconds |
| `message` | `raw` | Full syslog message |
| `src_endpoint.ip` | parsed from raw | Source IP if present |
| `metadata.event_code` | parsed ASA message ID | e.g. `"106103"` |
| `severity_id` | mapped from ASA severity | 3→High(4), 4→Medium(3), 5→Low(2) |
| `activity_id` | `1` (allowed) / `2` (denied) | Based on `permitted`/`denied` in message |

### 3.2 `linux.auth` → Operating System Events (4001)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | parsed from `raw` | |
| `message` | `raw` | Full syslog message |
| `actor.process.name` | parsed syslog process field | e.g. `"sshd"`, `"sudo"` |
| `severity_id` | mapped from syslog facility/severity | |
| `activity_id` | `1` | |

### 3.3 `fw.paloalto` → Network Activity (4002)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | from CEF `rt` extension | |
| `message` | CEF `msg` / `name` | |
| `src_endpoint.ip` | CEF `src` | |
| `dst_endpoint.ip` | CEF `dst` | |
| `metadata.event_code` | CEF `SignatureID` | |
| `severity_id` | mapped from CEF severity (0-10) | |

### 3.4 `siem.qradar` → Network Activity (4002)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | parsed from LEEF header or devTime | |
| `message` | `raw` | |
| `src_endpoint.ip` | LEEF `src` | |
| `metadata.event_code` | LEEF `EventID` | |

### 3.5 `web.nginx.access` → Network Activity (4002)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | JSON `time_local` or `@timestamp` | |
| `http_request.url.path` | JSON `request` / `path` | |
| `http_request.http_method` | JSON `method` | |
| `http_response.code` | JSON `status` | |
| `src_endpoint.ip` | JSON `remote_addr` | |
| `metadata.event_code` | JSON `status` | HTTP status code |

### 3.6 `cloud.aws.cloudtrail` → API Activity (6003)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | JSON `eventTime` | |
| `api.operation` | JSON `eventName` | |
| `api.service.name` | JSON `eventSource` | |
| `actor.user.name` | JSON `userIdentity.userName` | |
| `src_endpoint.ip` | JSON `sourceIPAddress` | |
| `metadata.event_code` | JSON `eventName` | |

### 3.7 `k8s.audit` → API Activity (6003)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | JSON `requestReceivedTimestamp` or `stageTimestamp` | |
| `api.operation` | JSON `verb` | |
| `api.service.name` | JSON `objectRef.resource` | |
| `actor.user.name` | JSON `user.username` | |
| `metadata.event_code` | JSON `verb` | |

### 3.8 `iot.sensor` → Device Activity (2001)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | JSON `timestamp` | |
| `device.uid` | JSON `device_id` | |
| `device.type` | JSON `device_type` | |
| `message` | JSON `reading` or `raw` | |
| `activity_id` | `1` | Telemetry |

### 3.9 `db.postgres` → Database Activity (4003)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | CSV column 0 (`log_time`) | |
| `database.name` | CSV column (`database_name`) | |
| `actor.user.name` | CSV column (`user_name`) | |
| `message` | CSV `message` column | |
| `metadata.event_code` | CSV `sql_state_code` | |
| `severity_id` | mapped from CSV `error_severity` | |

### 3.10 `windows.security` / `windows.sysmon` → Audit Activity (4801)

| OCSF field | Source | Notes |
|-----------|--------|-------|
| `time` | XML `TimeCreated SystemTime` attribute | |
| `metadata.event_code` | XML `EventID` | |
| `actor.process.name` | XML `Provider Name` | |
| `message` | `raw` | Full single-line XML |
| `severity_id` | mapped from XML `Level` | 2→Critical(5), 3→High(4), 4→Medium(3) |

---

## 4. Lossless Guarantee

Every OCSF event carries:

```json
{
  "unmapped": {
    "raw_data": "<verbatim original log line>",
    "collector_id": "collector-a",
    "site_id": "kol-dc1",
    "envelope": { /* full collector envelope */ }
  }
}
```

- `unmapped.raw_data` — exact bytes of the original log event
- `unmapped.envelope` — complete collector envelope including all metadata fields
- The MinIO raw-preservation object is the **primary** lossless store; `unmapped.envelope` is a secondary copy for SIEM-side correlation

> [!NOTE]
> The raw preservation copy in MinIO (`raw-preservation/site=<site_id>/source_type=<type>/date=.../`) is the chain-of-custody record.  
> The OCSF event is the analytics-optimized view. Both reference the same `event_id` (ULID).
