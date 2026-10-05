# Central Parser — `config/` Directory

This directory contains the central parser's Vector configuration split into **organized, purpose-specific files**. The original monolithic [`../vector.yaml`](../vector.yaml) is **preserved and unchanged** — it remains the live config used by Docker/Vector at runtime.

---

## File Layout

```
config/
├── sources.yaml              # Kafka consumer source
├── sinks.yaml                # All output sinks (MinIO, file, OpenSearch, console)
├── env.yaml                  # Environment variable reference (not loaded by Vector)
└── transforms/
    ├── 01_stamp_and_verify.yaml   # Step 1: SHA-256 integrity check + ULID stamping
    ├── 02_route.yaml              # Step 2: Route by source.type to per-parser transforms
    ├── 03_parse_cisco_asa.yaml    # OCSF: Cisco ASA → Network Activity (4002)
    ├── 04_parse_linux_auth.yaml   # OCSF: Linux auth/syslog → OS Events (4001)
    ├── 05_parse_paloalto_cef.yaml # OCSF: Palo Alto CEF → Network Activity (4002)
    ├── 06_parse_qradar_leef.yaml  # OCSF: IBM QRadar LEEF → Network Activity (4002)
    ├── 07_parse_nginx_access.yaml # OCSF: NGINX JSON → Network Activity (4002)
    ├── 08_parse_cloudtrail.yaml   # OCSF: AWS CloudTrail → API Activity (6003)
    ├── 09_parse_k8s_audit.yaml    # OCSF: K8s Audit → API Activity (6003)
    ├── 10_parse_iot_sensor.yaml   # OCSF: IoT JSON → Device Activity (2001)
    ├── 11_parse_postgres_db.yaml  # OCSF: PostgreSQL CSV → Database Activity (4003)
    ├── 12_parse_windows_evtx.yaml # OCSF: Windows EVTX XML → Audit Activity (4801)
    └── 13_parse_unknown.yaml      # OCSF: Unmatched fallback → Unknown (0)
```

---

## Pipeline Flow

```
[Kafka] kafka_in
    │
    ▼
[01] stamp_and_verify        — verify SHA-256, generate ULID event_id, stamp ingested_at
    │
    ├──► [MinIO / local_raw_lake]   (raw preservation — written before parsing)
    │
    ▼
[02] route_source_type        — dispatch by source.type field
    │
    ├─► cisco_asa    ──► [03] parse_cisco_asa    ──► Network Activity
    ├─► linux_auth   ──► [04] parse_linux_auth   ──► Operating System Events
    ├─► paloalto_cef ──► [05] parse_paloalto_cef ──► Network Activity
    ├─► qradar_leef  ──► [06] parse_qradar_leef  ──► Network Activity
    ├─► nginx_access ──► [07] parse_nginx_access  ──► Network Activity (HTTP)
    ├─► cloudtrail   ──► [08] parse_cloudtrail   ──► API Activity
    ├─► k8s_audit    ──► [09] parse_k8s_audit    ──► API Activity
    ├─► iot_sensor   ──► [10] parse_iot_sensor   ──► Device Activity
    ├─► postgres_db  ──► [11] parse_postgres_db  ──► Database Activity
    ├─► windows_evtx ──► [12] parse_windows_evtx ──► Audit Activity
    └─► _unmatched   ──► [13] parse_unknown      ──► Unknown
             │
             ▼
    [ocsf_all / console_out / opensearch_sink]
```

---

## Adding a New Log Source

1. Add a new route entry in [`transforms/02_route.yaml`](transforms/02_route.yaml).
2. Create a new `transforms/NN_parse_<source>.yaml` with the corresponding OCSF remap logic.
3. Add the new transform name to the `inputs` lists in [`sinks.yaml`](sinks.yaml).
4. Mirror the changes in the monolithic [`../vector.yaml`](../vector.yaml) for Docker runtime.

---

## Environment Variables

See [`env.yaml`](env.yaml) for a full reference of all environment variables with defaults and descriptions.

| Variable               | Default                    | Description                              |
| :--------------------- | :------------------------- | :--------------------------------------- |
| `KAFKA_BOOTSTRAP`      | `kafka:9092`               | Kafka broker list                        |
| `MINIO_ENDPOINT`       | `http://minio:9000`        | MinIO S3 endpoint                        |
| `MINIO_BUCKET`         | `ulpf-data-lake`           | Raw log preservation bucket              |
| `MINIO_ROOT_USER`      | `minioadmin`               | MinIO access key                         |
| `MINIO_ROOT_PASSWORD`  | `minioadmin`               | MinIO secret key                         |
| `OPENSEARCH_ENDPOINT`  | `http://opensearch:9200`   | OpenSearch URL for SIEM indexing         |
| `VECTOR_LOG`           | `info`                     | Vector log level                         |
