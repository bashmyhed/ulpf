# Collector A — `config/` Directory

**Handles:** Cisco ASA Syslog · Linux auth.log · Palo Alto CEF · IBM QRadar LEEF

The original [`../vector.yaml`](../vector.yaml) is **preserved and unchanged** — it is the live file used by Docker. This `config/` directory provides the same configuration split into organized, documented files for readability and maintainability.

---

## File Layout

```
config/
├── sources.yaml    # File-based sources: syslog/, cef/, raw/ directories
├── transform.yaml  # Log classification + ULPF envelope construction
├── sinks.yaml      # Kafka upstream + local debug file
└── env.yaml        # Environment variable reference (not loaded by Vector)
```

---

## Pipeline Flow

```
/logs/syslog/*.log  ──┐
/logs/cef/*.log     ──┼──► [envelope_a transform]
/logs/raw/*.log     ──┘         │
                                │  1. Validate (abort if empty)
                                │  2. SHA-256 hash + raw_len
                                │  3. Classify by content prefix:
                                │     CEF:  → fw.paloalto
                                │     LEEF: → siem.qradar
                                │     %ASA- → fw.cisco.asa
                                │     RFC3164 timestamp → linux.auth
                                │     else → unknown.syslog
                                │  4. Build ULPF Envelope
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           [kafka_out]              [local_debug]
           ulpf-raw-logs            /logs/debug/instance-a-sent.ndjson
           → central parser
```

---

## Log Sources

| Source File Pattern  | Format   | Classified As     | OCSF Class (central) |
| :------------------- | :------- | :---------------- | :------------------- |
| `/logs/syslog/*.log` | Syslog   | `fw.cisco.asa`    | Network Activity     |
| `/logs/syslog/*.log` | Syslog   | `linux.auth`      | OS Events            |
| `/logs/cef/*.log`    | CEF      | `fw.paloalto`     | Network Activity     |
| `/logs/raw/*.log`    | LEEF     | `siem.qradar`     | Network Activity     |

---

## Environment Variables

| Variable         | Default         | Description                              |
| :--------------- | :-------------- | :--------------------------------------- |
| `SITE_ID`        | `kol-dc1`       | Data center identifier                   |
| `COLLECTOR_ID`   | `collector-a`   | Unique node name for traceability        |
| `KAFKA_BOOTSTRAP`| `kafka:9092`    | Kafka broker address                     |
| `INSTANCE_ENV`   | `test`          | Environment label (test/staging/prod)    |
| `MOCK_MODE`      | `false`         | Enable built-in mock log generators      |
| `VECTOR_LOG`     | `info`          | Vector log verbosity                     |
