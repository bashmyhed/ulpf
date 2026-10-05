# ULPF Collector Tier

The **Collector Tier** in the Universal Log Pre-processing Framework (ULPF) operates at the edge of each monitored network/datacenter site (`site_id`). It ingests raw, heterogeneous logs, losslessly packages them into the canonical **Metadata Guide v1 Envelope**, verifies cryptographic hashes, and forwards them to the central Kafka bus.

---

## Collector Instances Overview

| Subfolder | Name | Log Formats | Canonical Sources |
|---|---|---|---|
| [`collector-a/`](./collector-a) | Network & Host Security | RFC 3164 Syslog, ArcSight CEF, IBM LEEF | `fw.cisco.asa`, `linux.auth`, `fw.paloalto`, `siem.qradar` |
| [`collector-b/`](./collector-b) | Web, Cloud, K8s, IoT, DB | NDJSON, CSV | `web.nginx.access`, `cloud.aws.cloudtrail`, `k8s.audit`, `iot.sensor`, `db.postgres` |
| [`collector-c/`](./collector-c) | Windows Audit & Sysmon | XML | `windows.security`, `windows.sysmon`, `windows.powershell` |

---

## Key Ingestion Guarantees

Every collector strictly conforms to **ULPF Metadata Guide v1**:
1. **Raw Log Unchanged**: The verbatim payload is preserved bit-for-bit in `.raw`.
2. **Cryptographic Hashes**: SHA-256 is computed at the edge (`raw_sha256`) along with byte length (`raw_len`).
3. **No Central Fields at Collector**: Collectors **NEVER** generate `event_id` (ULID) or `integrity.*` verification blocks. Those are strictly stamped by the Central Processor upon receipt and verification.
4. **Context Stamps**: Collectors set `site_id`, `collector_id`, `collected_at` (epoch ms), `source_tz`, `clock.synced`, and physical/logical `source.position` (file path, inode, line offset).

---

## Dual-Mode Operation: Production vs Mock

Each collector subfolder is packaged with a `Dockerfile` supporting two deployment modes via `MOCK_MODE`:

1. **Production Mode (`MOCK_MODE=false`)**:
   Runs as a pure Vector edge agent tailing real enterprise log directories mounted at `/logs/...`.
2. **Mock Mode (`MOCK_MODE=true`)**:
   Starts realistic Poisson-distributed log generator scripts in the background, emitting continuous streams of synthetic events into `/logs/...`, while Vector ingests and ships them to Kafka.

---

## Individual Component Build Commands

```bash
# Build Collector A
docker build -t ulpf-collector-a:latest ./collector/collector-a

# Build Collector B
docker build -t ulpf-collector-b:latest ./collector/collector-b

# Build Collector C
docker build -t ulpf-collector-c:latest ./collector/collector-c
```
