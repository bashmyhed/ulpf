# ULPF Documentation

**NTRO Universal Log Pre-processing Framework (ULPF)**  
*SIH 2026 · Problem ID 26156*

---

## Contents

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | Comprehensive system architecture: Multi-site Edge Agents, Kafka, Vector Server Engine, Dual Branches, GitOps Remote Config, and Dashboard |
| [envelope-spec.md](envelope-spec.md) | Full field reference for the metadata envelope — Edge Agent tier and Vector Server stamps |
| [pipeline-flow.md](pipeline-flow.md) | End-to-end data flow: emulators → Edge Agents (Sites A, B, C) → Kafka → Vector Server Engine → MinIO / OpenSearch / ML |
| [source-type-registry.md](source-type-registry.md) | Canonical `source.type` registry: all values, transport, raw_format, OCSF class |
| [ocsf-mapping.md](ocsf-mapping.md) | OCSF 1.3 normalization table — per source type field mappings |
| [validation-rules.md](validation-rules.md) | Ingest-time validation rules enforced by the Vector Server Engine |
| [runbook.md](runbook.md) | Step-by-step instructions to run and verify every pipeline stage (Python + Docker) |
| [ml-integration.md](ml-integration.md) | Additive OCSF-to-ML worker deployment, findings contract, and operational checks |

---

## Architecture at a Glance

```
Edge Agents [Site A (kol-dc1) / Site B (del-dc2) / Site C (mum-dc3)]
      ↓
Kafka Ingestion Bus (ulpf-raw-logs)
      ↓
Vector Server Engine [Server Central (kol-dc1)]
   (SHA-256 Zero-Tamper Verification & ULID Timestamping)
      ↓                                    ↓
Branch 1: Cold Raw Lake           Branch 2: Hot SIEM & ML Analytics
(MinIO S3 Gzip Storage)           (13x VRL Normalizers → OCSF v1.3.0)
                                           ↓                     ↓
                                  OpenSearch (SIEM)      Kafka (ulpf-ocsf-events)
                                                                 ↓
                                                          ML Anomaly Worker
                                                                 ↓
                                                         OpenSearch Findings
```

- **Edge Agents (Site A, Site B, Site C)** wrap every event in the v1 metadata envelope (including SHA-256 digest, monotonic seq, timestamp, and site metadata) and produce to Kafka.
- **Vector Server Engine** validates SHA-256 integrity, stamps ULID `uid`, routes by `source.type`, and writes:
  - Raw preservation envelope → MinIO bucket `ulpf-data-lake` (Gzip cold lake)
  - OCSF 1.3 normalized event → OpenSearch SIEM (`ulpf-ocsf-events`) and Kafka stream (`ulpf-ocsf-events`)
- **ML Worker** consumes the OCSF topic independently and writes scored anomaly windows and data-quality outcomes to `ulpf-ml-findings`.
- **GitOps Remote Config System** distributes verified Vector configurations to all agents and server engines with a zero-tamper pre-receive gate, atomic directory swap, and hot reload.

> All specification details live in [`metadataGuide.md`](../metadataGuide.md) and [`docs/architecture.md`](architecture.md).
