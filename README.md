# ULPF — Universal Log Parsing Framework

> **Lossless, Cryptographically Verified Edge-to-SIEM Log Pre-Processing Pipeline with OCSF v1.3.0 Normalization and Real-Time ML Anomaly Detection.**  
> *Developed for NTRO Problem Statement 26156 (Lossless Universal Log Parsing).*

[![Vector](https://img.shields.io/badge/Vector-0.40.0-00D2B4?style=flat-square&logo=vector&logoColor=white)](https://vector.dev)
[![VRL](https://img.shields.io/badge/Transforms-VRL-6366F1?style=flat-square)](https://vector.dev/docs/reference/vrl/)
[![Kafka](https://img.shields.io/badge/Streaming-Apache%20Kafka%20KRaft%203.7.0-231F20?style=flat-square&logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![OpenSearch](https://img.shields.io/badge/SIEM-OpenSearch%202.12.0-005EB8?style=flat-square&logo=opensearch&logoColor=white)](https://opensearch.org)
[![OpenSearch Dashboards](https://img.shields.io/badge/UI-OpenSearch%20Dashboards%202.12.0-005EB8?style=flat-square)](https://opensearch.org)
[![MinIO](https://img.shields.io/badge/Data%20Lake-MinIO%20S3-C72C48?style=flat-square&logo=minio&logoColor=white)](https://min.io)
[![Python](https://img.shields.io/badge/ML%20Engine-Python%203.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![OCSF](https://img.shields.io/badge/Schema-OCSF%20v1.3.0-FF6F00?style=flat-square)](https://schema.ocsf.io)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com)
[![Prometheus](https://img.shields.io/badge/Telemetry-Prometheus%20Metrics-E6522C?style=flat-square&logo=prometheus&logoColor=white)](https://prometheus.io)
[![Splunk HEC](https://img.shields.io/badge/Export-Splunk%20HEC-000000?style=flat-square&logo=splunk&logoColor=white)](https://www.splunk.com)
[![ClickHouse](https://img.shields.io/badge/OLAP-ClickHouse%20BigData-FFCC01?style=flat-square&logo=clickhouse&logoColor=black)](https://clickhouse.com)

---

## Installation & Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/bashmyhed/ulpf
cd ulpf
```

### 2. Prerequisites

- **Docker Engine** (v24.0+) & **Docker Compose** (v2.20+)
- **System Resources**: Minimum 4 CPU cores, 8 GB RAM (16 GB recommended for running full stack with OpenSearch, Dashboards, and MinIO).
- **Network Ports**: `5601` (Dashboards), `9200` (OpenSearch), `9000-9001` (MinIO), `9092` (Kafka), `8080` (Fleet Config API), `8686` (Vector API).

### 3. Deploy Complete Demonstration Stack

To launch all 11 core services (3 Multi-site Edge Agents, KRaft Kafka, Central Normalizer, MinIO Data Lake, OpenSearch SIEM, Dashboards, ML Worker, and Config Server):

```bash
docker compose up -d
```

Check service health:

```bash
docker compose ps
```

Access Web Interfaces:
- **OpenSearch SIEM Dashboards**: [http://localhost:5601](http://localhost:5601)
- **MinIO S3 Raw Lake Console**: [http://localhost:9001](http://localhost:9001) *(User: `minioadmin` / Pass: `minioadmin`)*
- **Fleet Config Server API**: [http://localhost:8080/health](http://localhost:8080/health)

---

## Automated Deployment CLI Wizards

ULPF includes production-grade interactive generator scripts in the project root:

### Deploy Custom Edge Collectors (`install-agent.sh`)

Generate tailored, standalone edge collection agent deployments configured for specific network segments, log directories, or syslog listeners:

```bash
# Interactive setup wizard
./install-agent.sh

# Non-interactive CLI deployment
./install-agent.sh --name agent-perimeter-01 --site kol-dc1 --kafka localhost:9092 --vendors P1
```

### Deploy Central Server & Sinks (`install-server.sh`)

Generate tailored central processing servers with your chosen modular sinks and optional bundled agents:

```bash
# Interactive setup wizard
./install-server.sh

# Non-interactive CLI deployment with Splunk HEC and ClickHouse sinks
./install-server.sh --name server-soc-01 --site kol-dc1 --sinks 1,3,11 --with-agent --agent-vendors P1
```

---

## Executive Summary: What We Are Doing

Modern enterprise networks generate massive volumes of logs across firewalls, network appliances, operating systems, cloud environments, containers, databases, and IoT endpoints. These logs arrive in highly fragmented, incompatible formats (Syslog RFC 3164/5424, CEF, LEEF, JSON, XML, CSV).

**ULPF (Universal Log Pre-processing Framework)** solves this by decoupling edge collection from downstream SIEM storage through a high-performance, lossless processing pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      1. Edge Collection Tier (Vector Agents)                    │
│   Site A (kol-dc1)          Site B (del-dc2)              Site C (mum-dc3)      │
│  [Firewalls/Auth Logs]    [Cloud/K8s/App Logs]        [Windows EVTX / Sysmon]   │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ Raw Message + Envelope (SHA-256 + Monotonic Seq)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    2. Streaming Ingestion Bus (Apache Kafka)                    │
│                                ulpf-raw-logs                                    │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ High-Throughput Batch Stream
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              3. Central Parser Engine (Vector + VRL Normalizers)                │
│    - Zero-Tamper Cryptographic Verification (HMAC-SHA256 & Length Checks)       │
│    - High-Resolution ULID Event Timestamping (1.3.0 Standard)                    │
│    - Dynamic Routing by Classified Source Type                                  │
└──────────────────────┬──────────────────────────────────┬───────────────────────┘
                       │                                  │
       [Branch 1: Forensic Cold Lake]     [Branch 2: Hot OCSF Normalization]
                       │                                  │
                       ▼                                  ▼
        ┌─────────────────────────────┐    ┌──────────────────────────────────────┐
        │       MinIO / AWS S3        │    │       OCSF v1.3.0 Classification     │
        │   Partitioned, Compressed   │    │  - 4002 Network Activity             │
        │      Raw Preserved Logs     │    │  - 4001 Operating System Events     │
        │  (Court-admissible Evidence)│    │  - 6003 API Activity                 │
        └─────────────────────────────┘    └──────────────────┬───────────────────┘
                                                              │
                                       ┌──────────────────────┴───────────────────┐
                                       ▼                                          ▼
                        ┌──────────────────────────────┐          ┌──────────────────────────────┐
                        │   OpenSearch SIEM Cluster    │          │  Modular Downstream Sinks    │
                        │  (Interactive Analytics UI)  │          │  - Splunk HEC SIEM           │
                        └──────────────┬───────────────┘          │  - ClickHouse BigData OLAP   │
                                       │                          │  - Cloud Lakes (GCP, Azure)  │
                                       │                          │  - Downstream Kafka Bus      │
                                       │                          │  - Syslog / CEF Forwarder    │
                                       │                          │  - SOAR Webhook Automation   │
                                       ▼                          │  - Airgap WORM Archive       │
                        ┌──────────────────────────────┐          │  - Prometheus Metrics Exporter│
                        │ Real-Time ML Anomaly Worker  │          └──────────────────────────────┘
                        │ (Isolation Forest / Outliers)│
                        │ Findings → ulpf-ml-findings  │
                        └──────────────────────────────┘
```

### Core Architecture Pillars

1. **Lossless Dual-Branch Pipeline**:
   - **Forensic Raw Lake (Branch 1)**: The original, untouched raw log payload is preserved alongside collector metadata in MinIO/S3 object storage, gzip compressed, and partitioned chronologically by `site/source_type/date`.
   - **Hot Normalized Stream (Branch 2)**: The log body is parsed by high-speed VRL routines into structured, typed **OCSF v1.3.0** security events with extracted observables (IP addresses, users, URLs, hashes).
2. **Cryptographic Integrity & Chain of Custody**:
   - Every log ingested at the edge is stamped with a SHA-256 digest and monotonic sequence ID.
   - The central parser validates the hash upon receipt; corrupted, truncated, or tampered packets are flagged with `metadata.integrity.verified: false` and routed to dead-letter queues.
3. **OCSF v1.3.0 Standardization**:
   - Conforms strictly to the Open Cybersecurity Schema Framework (OCSF) specification, enabling cross-vendor SIEM interoperability and eliminating manual rule rewrites.
4. **Machine Learning Anomaly Detection**:
   - Consumes normalized OCSF streams asynchronously.
   - Computes statistical feature drift, temporal frequency spikes, isolation forest outlier scores, and data-quality findings, indexing results into `ulpf-ml-findings`.
5. **GitOps Remote Fleet Management**:
   - Built-in configuration server distributes signed Vector pipeline configs with atomic directory swaps, configuration syntax gates, and zero-downtime hot reloading (`SIGHUP`).

---

## Supported Log Formats & Providers

The central normalization engine includes out-of-the-box VRL transformation modules for 12 vendor categories:

| Source Identifier | Log Category / Vendor | Input Format | Target OCSF Class | Key Observables Extracted |
| :--- | :--- | :--- | :--- | :--- |
| `fw.cisco.asa` | **Cisco ASA Firewall** | Syslog RFC 3164 (`%ASA-*`) | `4002 Network Activity` | `src_ip`, `dst_ip`, `port`, `action` |
| `auth.linux.ssh` | **Linux Auth / OpenSSH** | Syslog RFC 3164 / PAM | `4001 OS Events` | `user`, `hostname`, `src_ip`, `auth_status` |
| `fw.paloalto` | **Palo Alto Networks NGFW** | Common Event Format (`CEF:0`) | `4002 Network Activity` | `src_ip`, `dst_ip`, `rule`, `app`, `bytes` |
| `siem.qradar` | **IBM QRadar SIEM** | Log Event Extended Format (`LEEF`) | `4002 Network Activity` | `src_ip`, `dst_ip`, `usrName`, `devTime` |
| `web.nginx.access` | **NGINX Web Server** | JSON Access Logs | `4002 Network Activity` | `src_ip`, `url`, `http_status`, `user_agent` |
| `cloud.aws.cloudtrail` | **AWS CloudTrail** | JSON API Audit Logs | `6003 API Activity` | `user`, `src_ip`, `api_operation`, `arn` |
| `k8s.audit` | **Kubernetes Audit** | JSON K8s Audit Records | `6003 API Activity` | `user`, `verb`, `resource`, `namespace` |
| `iot.sensor` | **IoT Edge Gateways** | JSON Telemetry Streams | `4002 Network Activity` | `device_id`, `sensor_type`, `reading`, `status` |
| `db.postgres` | **PostgreSQL Database** | CSV Audit Logs | `6003 API Activity` | `user`, `database`, `query`, `client_ip` |
| `windows.security` | **Windows Security Event Log** | EVTX XML | `4001 OS Events` | `EventID`, `AccountName`, `LogonType`, `Workstation` |
| `windows.sysmon` | **Microsoft Sysmon** | EVTX XML | `4001 OS Events` | `ProcessId`, `Image`, `CommandLine`, `ParentImage` |
| `windows.powershell` | **PowerShell Script Audit** | EVTX XML | `4001 OS Events` | `ScriptBlockText`, `UserId`, `ExecutionPath` |

---

## Modular Sinks Library (NTRO PS 26156 Compliant)

All modular sinks reside under [`central/modules/sinks/`](file:///home/paul/projects/sih2/central/modules/sinks/) and can be plugged in without disrupting running pipelines:

| Sink Module | Target Technology | Purpose & Defense Integration |
| :--- | :--- | :--- |
| `01_splunk_hec_siem.yaml` | **Splunk Enterprise & Cloud (HEC)** | High-speed JSON event streaming to Splunk security clusters. |
| `02_elasticsearch_siem.yaml` | **Elasticsearch 7.x/8.x SIEM** | Direct data stream indexing into external Elastic Security deployments. |
| `03_clickhouse_bigdata.yaml` | **ClickHouse Columnar Database** | Petabyte-scale, sub-second analytics handling billions of events per day. |
| `04_s3_data_lake.yaml` | **AWS S3 / MinIO / Ceph** | Gzip-compressed NDJSON object storage lake for Athena, Trino, and Spark. |
| `05_gcp_cloud_storage.yaml` | **Google Cloud Storage (GCS)** | Direct lake export for Google Chronicle SIEM, BigQuery, and Vertex AI. |
| `06_azure_blob_storage.yaml` | **Azure Blob Storage** | Multi-cloud storage container for Microsoft Sentinel SIEM. |
| `07_kafka_streaming_bus.yaml` | **Downstream Apache Kafka / Redpanda** | Decoupled pub-sub message bus for inter-SOC federation and external sharing. |
| `08_syslog_forwarder_siem.yaml` | **TCP/TLS Syslog (ArcSight, QRadar)** | Socket forwarder delivering JSON/CEF/LEEF logs to legacy perimeter SIEMs. |
| `09_http_webhook_soar.yaml` | **SOAR Automation (Cortex XSOAR, Tines)** | Webhook dispatcher triggering automated incident response playbooks. |
| `10_airgap_local_archive.yaml` | **Immutable WORM Archive** | Rotating hourly compressed disk/SAN archives for air-gapped networks. |
| `11_prometheus_metrics.yaml` | **Prometheus Metrics Exporter** | Live telemetry endpoint (port 9598) tracking ingestion EPS and latency. |

---

## Repository Structure

```
ulpf/
├── docker-compose.yml          # Full 11-service local demonstration stack
├── install-agent.sh            # Edge collection agent deployment generator wizard
├── install-server.sh           # Central server & sinks deployment generator wizard
├── collector/                  # Reference multi-site edge agents (A, B, C)
│   ├── collector-a/            # Network & Auth logs (Cisco ASA, Linux Auth, QRadar)
│   ├── collector-b/            # Cloud, Web, & Container logs (Nginx, CloudTrail, K8s)
│   └── collector-c/            # Windows EVTX XML logs (Security, Sysmon, PowerShell)
├── central/                    # Central Parser & Normalizer Engine
│   ├── vector.yaml             # Complete consolidated central Vector pipeline
│   ├── config/                 # Modular configuration components (sources, transforms, sinks)
│   └── modules/                # Plug-and-play modular sinks library (NTRO PS compliant)
│       ├── README.md           # Sink integration and activation manual
│       ├── env/                # Environment variable reference templates
│       └── sinks/              # 11 Modular enterprise sink configs
├── ml/                         # Machine Learning Anomaly Detection Subsystem
│   ├── ulpf_ml/                # Python worker package (workers, models, evaluation)
│   └── models/                 # Pretrained baseline anomaly detection models
├── config-server/              # GitOps Central Configuration & Fleet Management API
├── deployment/                 # Target directory for generated agent & server instances
├── docs/                       # Technical specifications, schema references, & runbooks
│   ├── architecture.md         # Comprehensive system architecture & data flows
│   ├── envelope-spec.md        # Cryptographic metadata envelope specification
│   ├── ocsf-mapping.md         # Field-by-field OCSF v1.3.0 mapping dictionary
│   └── runbook.md              # Operational troubleshooting & maintenance runbook
└── scripts/                    # Test data generators & diagnostic utilities
```

---

## Verification & Health Check

### 1. Ingest Sample Verification Logs
```bash
# Inject sample logs across all 12 formats
./collector/collector-a/run.sh test-send 2>/dev/null || true
```

### 2. Verify OpenSearch OCSF Indexing
```bash
curl -s "http://localhost:9200/ulpf-ocsf-*/_search?size=1" | jq .
```

### 3. Verify MinIO Raw Lake Preservation
```bash
curl -s http://localhost:9000/minio/health/live
```

### 4. Verify ML Findings & Telemetry
```bash
curl -s "http://localhost:9200/ulpf-ml-findings/_search?size=1" | jq .
```

### 5. Validate Vector Configurations Offline
```bash
docker run --rm -v $(pwd)/central/vector.yaml:/etc/vector/vector.yaml:ro timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml
```
