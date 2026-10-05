# ULPF Central Log Processor & Normalizer

The **Central Processor** is the core processing and normalization engine of the Universal Log Pre-processing Framework (ULPF).

## Architecture & Responsibilities

1. **Ingest & Consume**: Subscribes to the Kafka topic `ulpf-raw-logs` partitioned across edge collectors.
2. **Forensic Integrity Verification**: Recomputes SHA-256 over raw log text verbatim and verifies against collector's declared `raw_sha256` and `raw_len`. Sets `integrity.verified: true`.
3. **Monotonic ULID Generation**: Generates deterministic, globally unique, time-ordered ULIDs (`event_id`) using the collector's millisecond timestamp and entropy.
4. **Data Lake Raw Preservation**: Preserves raw envelopes into MinIO S3 data lake (`ulpf-data-lake`) partitioned by site and canonical source type:
   `raw-preservation/site=<site_id>/source_type=<source_type>/date=<YYYY-MM-DD>/<file>.ndjson.gz`
   Compressed with **gzip** for 85–90% storage reduction.
5. **OCSF 1.3 Normalization**: Normalizes heterogeneous logs across 10 source categories to OCSF 1.3 schema (classes 4002 Network, 4001 OS, 4003 Database, 6003 API, 2001 Device, 4801 Audit, 0 Unknown).
6. **Delivery**: Emits normalized events to Kafka (`ulpf-ocsf-events`), OpenSearch,
   and local filesystem sinks (`/output/ocsf-events.ndjson`). The Kafka copy is an
   additive feed for the ML worker; it does not contain raw event bodies.

---

## Configuration & Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `KAFKA_BOOTSTRAP` | `kafka:9092` | Kafka broker bootstrap address |
| `MINIO_ENDPOINT` | `http://minio:9000` | MinIO / S3 API endpoint URL |
| `MINIO_BUCKET` | `ulpf-data-lake` | Target S3 bucket for raw preservation |
| `MINIO_ROOT_USER` | `minioadmin` | S3 access key ID |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | S3 secret access key |
| `VECTOR_LOG` | `info` | Vector log level (`debug`, `info`, `warn`, `error`) |

---

## Build and Deployment

### 1. Build Docker Image

```bash
docker build -t ulpf-central-parser:latest ./central
```

### 2. Run Container

```bash
docker run -d \
  --name ulpf-central-parser \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e MINIO_ENDPOINT=http://minio:9000 \
  -e MINIO_BUCKET=ulpf-data-lake \
  -v ./output:/output \
  ulpf-central-parser:latest
```

To run the central processor with the ML consumer, use the repository's Compose
overlay from the project root:

```bash
docker compose -f docker-compose.yml -f docker-compose.ml.yml up -d --build
```

See [`../docs/ml-integration.md`](../docs/ml-integration.md) for the worker's
state, health, and findings-index contract.
