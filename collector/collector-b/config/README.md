# Collector B — `config/` Directory

**Handles:** NGINX Access JSON · AWS CloudTrail JSON · Kubernetes Audit JSON · IoT Sensor JSON · PostgreSQL CSV

The original [`../vector.yaml`](../vector.yaml) is **preserved and unchanged** — it is the live file used by Docker. This `config/` directory provides the same configuration split into organized, documented files for readability and maintainability.

---

## File Layout

```
config/
├── sources.yaml    # File-based sources: json/ and csv/ directories
├── transform.yaml  # JSON/CSV classification + ULPF envelope construction
├── sinks.yaml      # Kafka upstream + local debug file
└── env.yaml        # Environment variable reference (not loaded by Vector)
```

---

## Pipeline Flow

```
/logs/json/*.log   ──┐
/logs/json/*.json  ──┼──► [envelope_b transform]
/logs/csv/*.csv    ──┘         │
                                │  1. Validate + skip CSV headers
                                │  2. SHA-256 hash + raw_len
                                │  3. Classify by content inspection:
                                │     JSON + "apiVersion" + "audit.k8s.io"
                                │                         → k8s.audit
                                │     JSON + "eventSource" + "amazonaws.com"
                                │                         → cloud.aws.cloudtrail
                                │     JSON + "remote_addr" + "request_method"
                                │                         → web.nginx.access
                                │     JSON + "device_id" + "sensor_type"
                                │                         → iot.sensor
                                │     CSV  (contains comma)
                                │                         → db.postgres
                                │  4. Build ULPF Envelope
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           [kafka_out]              [local_debug]
           ulpf-raw-logs            /logs/debug/instance-b-sent.ndjson
           → central parser
```

---

## Log Sources

| Source File Pattern  | Format | Classified As           | OCSF Class (central)  |
| :------------------- | :----- | :---------------------- | :-------------------- |
| `/logs/json/*.log`   | JSON   | `k8s.audit`             | API Activity          |
| `/logs/json/*.log`   | JSON   | `cloud.aws.cloudtrail`  | API Activity          |
| `/logs/json/*.log`   | JSON   | `web.nginx.access`      | Network Activity      |
| `/logs/json/*.log`   | JSON   | `iot.sensor`            | Device Activity       |
| `/logs/csv/*.csv`    | CSV    | `db.postgres`           | Database Activity     |

---

## Environment Variables

| Variable         | Default         | Description                              |
| :--------------- | :-------------- | :--------------------------------------- |
| `SITE_ID`        | `kol-dc1`       | Data center identifier                   |
| `COLLECTOR_ID`   | `collector-b`   | Unique node name for traceability        |
| `KAFKA_BOOTSTRAP`| `kafka:9092`    | Kafka broker address                     |
| `INSTANCE_ENV`   | `test`          | Environment label (test/staging/prod)    |
| `MOCK_MODE`      | `false`         | Enable built-in mock log generators      |
| `VECTOR_LOG`     | `info`          | Vector log verbosity                     |
