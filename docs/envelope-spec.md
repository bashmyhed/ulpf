# ULPF Metadata Envelope — Field Specification

**Version:** 1.0  
**Spec base:** [metadataGuide.md](../metadataGuide.md) §2–§4  
**Status:** Implemented and passing (194/194 events, 100% integrity)

---

## Overview

Every log event in the ULPF pipeline is wrapped in a flat JSON **envelope** before it reaches Kafka.  
The envelope carries three classes of fields:

| Class | Who sets it | When |
|-------|-------------|------|
| **Agent fields** | Vector agent instance (Agent A/B/C) | At ingest from the log source |
| **Server stamps** | Vector server engine | After Kafka consume, before MinIO/OCSF write |
| **Source-specific nested** | Edge Agent (inside `source.*`) | Depends on `raw_format` |

> [!IMPORTANT]
> The envelope is **flat** — all fields sit at the top level. There is no wrapping `"envelope": {}` key.  
> `raw` and `raw_sha256` are both present at the top level alongside `source`, `flags`, etc.

---

## 1. Agent-emitted Fields

These fields are set by the Vector agent transform (`envelope_a`, `envelope_b`, `envelope_c`).

### 1.1 Identity & Versioning

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `envelope_version` | `int` | ✅ | Always `1` for this spec version |
| `site_name` | `string` | ✅ | Friendly site name (`"Site A"`, `"Site B"`, `"Site C"`) |
| `site_id` | `string` | ✅ | Deployment site identifier (e.g. `"kol-dc1"`, `"del-dc2"`, `"mum-dc3"`) |
| `agent_id` | `string` | ✅ | Logical agent ID (e.g. `"agent-a"`, `"agent-b"`, `"agent-c"`) |
| `collector_id` | `string` | ✅ | Backwards-compatibility alias for `agent_id` |
| `agent_version` | `string` | ✅ | Agent software version (e.g. `"1.0.0"`) |
| `seq` | `int` | ✅ | Per-agent monotonically increasing sequence number |

### 1.2 Timing

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `collected_at` | `int` | ✅ | Unix epoch **milliseconds** — time the collector wrapped this event |
| `source_tz` | `string` | ✅ | Timezone offset of the **source** device (e.g. `"+05:30"`, `"UTC"`) |
| `clock.synced` | `bool` | ✅ | Whether collector clock is NTP-synchronized |
| `clock.skew_ms` | `int` | ✅ | Measured NTP skew in milliseconds (0 when synced) |

### 1.3 Source Identity (`source.*`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source.type` | `string` | ✅ | Canonical dot-separated log source identifier (see registry) |
| `source.vendor` | `string` | ✅ | Device/software vendor (e.g. `"Cisco"`, `"nginx"`) |
| `source.product` | `string` | ✅ | Product name (e.g. `"ASA"`, `"PostgreSQL"`) |
| `source.product_version` | `string` | ✅ | Product version (`"unknown"` if not determinable) |
| `source.transport` | `string` | ✅ | How the log reached the collector: `file`, `syslog_udp`, `syslog_tcp`, `journald`, `http`, `kafka` |
| `source.host_name` | `string` | ✅ | FQDN of the collector host |
| `source.host_ip` | `string\|null` | — | Collector host IP (null if not configured) |
| `source.sender_ip` | `string\|null` | — | IP of the sending device (for network transports) |
| `source.sender_port` | `int\|null` | — | Source port of the sending device |
| `source.host_id` | `string\|null` | — | Arbitrary host identifier (cloud instance ID, etc.) |

#### File position sub-object (`source.position`)

Populated only for `transport: file`.

| Field | Type | Description |
|-------|------|-------------|
| `source.position.path` | `string` | Absolute path to the log file being tailed |
| `source.position.inode` | `int\|null` | File inode number (for rotation detection) |
| `source.position.offset` | `int\|null` | Byte offset of this event |
| `source.position.line_no` | `int\|null` | Line number of this event |

### 1.4 Raw Payload

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `raw` | `string` | ✅ | The **verbatim** original log line — never modified |
| `raw_format` | `string` | ✅ | Wire format identifier (see table below) |
| `raw_encoding` | `string` | ✅ | Character encoding (always `"utf-8"` in this deployment) |
| `raw_len` | `int` | ✅ | Byte length of `raw` (UTF-8 encoded) |
| `raw_sha256` | `string` | ✅ | Lowercase hex SHA-256 of `raw` bytes — computed at collector |

**`raw_format` values used in this deployment:**

| Value | Meaning |
|-------|---------|
| `syslog3164` | RFC 3164 BSD syslog |
| `cef` | ArcSight Common Event Format |
| `leef` | IBM LEEF (Log Event Extended Format) |
| `json` | Structured JSON log |
| `csv` | Comma-separated values |
| `evtx_xml` | Windows Event Log XML (single-line) |

### 1.5 Flags

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `flags.truncated` | `bool` | `false` | Event was truncated to fit transport limits |
| `flags.multiline_joined` | `bool` | `false` | Multiple physical lines were joined into one logical event |
| `flags.decoded_from` | `string\|null` | `null` | Original encoding if transcoding was applied (e.g. `"latin-1"`) |
| `flags.redacted` | `bool` | `false` | PII/secret fields were redacted before shipping |
| `flags.duplicate_suspect` | `bool` | `false` | Dedup heuristic flagged this as a potential duplicate |

### 1.6 Labels

| Field | Type | Description |
|-------|------|-------------|
| `labels.env` | `string` | Deployment environment: `"prod"`, `"staging"`, `"test"` |
| `labels.tier` | `string` | Collector tier tag (matches `collector_id`, e.g. `"collector-a"`) |

---

## 2. Source-specific Nested Metadata

These sub-objects live inside `source.*` and are only present for the matching `raw_format`.

### 2.1 `source.syslog` — for `raw_format: syslog3164`

Used by: `fw.cisco.asa`, `linux.auth`

| Field | Type | Description |
|-------|------|-------------|
| `source.syslog.rfc` | `string` | `"3164"` or `"5424"` |
| `source.syslog.facility` | `string` | Syslog facility name (e.g. `"local4"`, `"auth"`) |
| `source.syslog.framing` | `string` | `"newline"` or `"octet-count"` |

### 2.2 `source.cef` — for `raw_format: cef`

Used by: `fw.paloalto`

| Field | Type | Description |
|-------|------|-------------|
| `source.cef.version` | `string` | CEF spec version (e.g. `"0"`) |
| `source.cef.device_vendor` | `string` | CEF `DeviceVendor` field |
| `source.cef.device_product` | `string` | CEF `DeviceProduct` field |
| `source.cef.device_version` | `string` | CEF `DeviceVersion` field |
| `source.cef.signature_id` | `string` | CEF `SignatureID` |
| `source.cef.name` | `string` | CEF event name |
| `source.cef.severity` | `string` | CEF severity string |

### 2.3 `source.leef` — for `raw_format: leef`

Used by: `siem.qradar`

| Field | Type | Description |
|-------|------|-------------|
| `source.leef.version` | `string` | LEEF version (`"1.0"` or `"2.0"`) |
| `source.leef.vendor` | `string` | LEEF vendor field |
| `source.leef.product` | `string` | LEEF product field |
| `source.leef.product_version` | `string` | LEEF product version |
| `source.leef.event_id` | `string` | LEEF event ID field |

### 2.4 `source.evtx` — for `raw_format: evtx_xml`

Used by: `windows.security`, `windows.sysmon`

| Field | Type | Description |
|-------|------|-------------|
| `source.evtx.channel` | `string` | Windows event channel (`"Security"`, `"Microsoft-Windows-Sysmon/Operational"`) |
| `source.evtx.provider` | `string` | `<Provider Name>` attribute from XML |

### 2.5 `source.k8s` — for Kubernetes audit logs

Used by: `k8s.audit`

| Field | Type | Description |
|-------|------|-------------|
| `source.k8s.cluster` | `string` | Kubernetes cluster name |
| `source.k8s.namespace` | `string\|null` | Namespace of the audited resource |
| `source.k8s.node` | `string\|null` | Node name |

### 2.6 `source.cloud` — for cloud provider logs

Used by: `cloud.aws.cloudtrail`

| Field | Type | Description |
|-------|------|-------------|
| `source.cloud.provider` | `string` | `"aws"`, `"gcp"`, `"azure"` |
| `source.cloud.account_id` | `string\|null` | Cloud account / project ID |
| `source.cloud.region` | `string\|null` | Cloud region |
| `source.cloud.service` | `string\|null` | Cloud service name (e.g. `"cloudtrail"`) |

### 2.7 `source.web` — for HTTP access logs

Used by: `web.nginx.access`

| Field | Type | Description |
|-------|------|-------------|
| `source.web.server_name` | `string\|null` | Virtual host / server name |
| `source.web.server_port` | `int\|null` | Listening port |

### 2.8 `source.iot` — for IoT sensor telemetry

Used by: `iot.sensor`

| Field | Type | Description |
|-------|------|-------------|
| `source.iot.device_id` | `string\|null` | IoT device unique identifier |
| `source.iot.device_type` | `string\|null` | Device category (e.g. `"temperature_sensor"`) |
| `source.iot.protocol` | `string\|null` | Transport protocol (e.g. `"mqtt"`, `"coap"`) |

### 2.9 `source.db` — for database logs

Used by: `db.postgres`

| Field | Type | Description |
|-------|------|-------------|
| `source.db.engine` | `string` | Database engine (e.g. `"postgresql"`) |
| `source.db.instance` | `string\|null` | Instance / database name |
| `source.db.schema` | `string\|null` | Schema name |

---

## 3. Vector Server Engine Stamps

These fields are added by the Vector Server Engine **after** consuming from Kafka. Edge Agents **must never** set these.

| Field | Type | Description |
|-------|------|-------------|
| `uid` / `event_id` | `string` | ULID — globally unique event identifier, monotonic sortable |
| `ingested_at` / `processed_time` | `int` | Unix epoch milliseconds when the server engine processed this event |
| `server_node` | `string` | Hostname of the Vector Server Engine node (e.g. `"ulpf-server-parser-01"`) |

### 3.1 Integrity Object

| Field | Type | Description |
|-------|------|-------------|
| `integrity.algorithm` | `string` | Hash algorithm used — always `"sha256"` |
| `integrity.agent_hash` / `collector_hash` | `string` | `raw_sha256` as received from the edge agent |
| `integrity.server_hash` / `central_hash` | `string` | SHA-256 recomputed by server engine from the `raw` field |
| `integrity.verified` | `bool` | `true` if `agent_hash == server_hash` |
| `integrity.length_verified` | `bool` | `true` if `len(raw.encode('utf-8')) == raw_len` |

> [!CAUTION]
> Events where `integrity.verified = false` are routed to the DLQ (`ulpf-dlq` Kafka topic) and **not** written to MinIO or OCSF output.

---

## 4. Complete Envelope Example

The following is a real envelope from `output/raw-lake/preservation-events.ndjson` (first event):

```json
{
  "envelope_version": 1,
  "site_id": "kol-dc1",
  "collector_id": "collector-a",
  "collector_version": "1.0.0",
  "seq": 1001,
  "collected_at": 1790735830160,
  "source_tz": "+05:30",
  "clock": { "synced": true, "skew_ms": 0 },
  "source": {
    "type": "fw.cisco.asa",
    "vendor": "Cisco",
    "product": "ASA",
    "product_version": "unknown",
    "transport": "file",
    "host_name": "collector-a.corp.local",
    "host_ip": null,
    "sender_ip": null,
    "sender_port": null,
    "host_id": null,
    "position": {
      "path": "/logs/syslog/cisco_asa.log",
      "inode": null,
      "offset": null,
      "line_no": null
    },
    "syslog": {
      "rfc": "3164",
      "facility": "local4",
      "framing": "newline"
    }
  },
  "raw_format": "syslog3164",
  "raw_encoding": "utf-8",
  "raw_len": 109,
  "raw_sha256": "13ff0c4a17eabb4a84624f35fc053ab01e321c118f58449beb25ce7303368194",
  "raw": "%ASA-3-106103: access-list acl-32 permitted 189.52.44.152 2976:60.13.101.184 -> SSH:151.142.3.195 hits=acl-90",
  "flags": {
    "truncated": false,
    "multiline_joined": false,
    "decoded_from": null,
    "redacted": false,
    "duplicate_suspect": false
  },
  "labels": {
    "env": "test",
    "tier": "collector-a"
  },
  "event_id": "01M3R2RK4GS3Z0SX49DTNBN317",
  "ingested_at": 1790735830166,
  "central_node": "ulpf-central-parser-01",
  "integrity": {
    "algorithm": "sha256",
    "collector_hash": "13ff0c4a17eabb4a84624f35fc053ab01e321c118f58449beb25ce7303368194",
    "central_hash": "13ff0c4a17eabb4a84624f35fc053ab01e321c118f58449beb25ce7303368194",
    "verified": true,
    "length_verified": true
  }
}
```

---

## 5. Field Count Summary

| Tier | Fields | Notes |
|------|--------|-------|
| Collector identity | 5 | `envelope_version`, `site_id`, `collector_id`, `collector_version`, `seq` |
| Timing | 4 | `collected_at`, `source_tz`, `clock.synced`, `clock.skew_ms` |
| Source identity | 10 | `source.type` … `source.host_id` + `source.position.*` |
| Source-specific nested | 3–7 | Depends on `raw_format` |
| Raw payload | 5 | `raw`, `raw_format`, `raw_encoding`, `raw_len`, `raw_sha256` |
| Flags | 5 | Inside `flags.*` |
| Labels | 2 | `labels.env`, `labels.tier` |
| **Central stamps** | **4** | `event_id`, `ingested_at`, `central_node`, `integrity.*` (5 sub-fields) |
