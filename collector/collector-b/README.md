# ULPF Collector Instance B (Structured JSON & CSV)

Edge collector instance dedicated to web access logs, cloud infrastructure audit trails, container orchestrators, IoT sensors, and database activity logs.

## Supported Sources & Enveloping

| Source | Format | Canonical `source.type` | Vendor / Product | Extra Metadata |
|---|---|---|---|---|
| Nginx Access | NDJSON | `web.nginx.access` | Nginx / Nginx HTTP | `source.web` (server_name, format) |
| AWS CloudTrail | NDJSON | `cloud.aws.cloudtrail` | AWS / CloudTrail | `source.cloud` (provider, region) |
| Kubernetes Audit | NDJSON | `k8s.audit` | CNCF / Kubernetes Audit | `source.k8s` (cluster, stage) |
| IoT Telemetry | NDJSON | `iot.sensor` | Generic / IoT Sensor | `source.iot` (network, protocol) |
| PostgreSQL Logs | CSV | `db.postgres` | PostgreSQL / PostgreSQL DB | `source.db` (engine, schema) |

## Key Responsibilities

1. **Edge Ingestion**: Reads live JSON logs from `/logs/json/*.log` and CSV logs from `/logs/csv/*.csv`.
2. **Lossless Framing**: Computes SHA-256 (`raw_sha256`) and byte length (`raw_len`) over raw bytes.
3. **v1 Envelope Packaging**: Stamps `site_id`, `collector_id`, `collected_at` (epoch ms), clock sync status, file position.
4. **Kafka Shipping**: Streams envelopes to Kafka topic `ulpf-raw-logs`.

## Build & Run

### 1. Build Image

```bash
docker build -t ulpf-collector-b:latest ./collector/collector-b
```

### 2. Run in Production (Tail Real Logs)

```bash
docker run -d \
  --name ulpf-collector-b \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e SITE_ID=kol-dc1 \
  -e COLLECTOR_ID=collector-b \
  -e MOCK_MODE=false \
  -v /var/log/apps:/logs:ro \
  ulpf-collector-b:latest
```

### 3. Run in Mock / Self-Contained Test Mode

```bash
docker run -d \
  --name ulpf-collector-b-mock \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e MOCK_MODE=true \
  ulpf-collector-b:latest
```
When `MOCK_MODE=true`, background Python emulators generate realistic Poisson-distributed logs for Nginx, CloudTrail, K8s, IoT, and PostgreSQL directly into `/logs/...`.
