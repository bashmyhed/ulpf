# Collector C — `config/` Directory

**Handles:** Windows Event Log (EVTX/XML) — Security-Auditing · Sysmon · PowerShell Operational

The original [`../vector.yaml`](../vector.yaml) is **preserved and unchanged** — it is the live file used by Docker. This `config/` directory provides the same configuration split into organized, documented files for readability and maintainability.

---

## File Layout

```
config/
├── sources.yaml    # File-based sources: syslog/windows_events.log + xml/ directory
├── transform.yaml  # EVTX XML subtype detection + ULPF envelope construction
├── sinks.yaml      # Kafka upstream + local debug file
└── env.yaml        # Environment variable reference (not loaded by Vector)
```

---

## Pipeline Flow

```
/logs/syslog/windows_events.log  ──┐
/logs/xml/*.log                  ──┼──► [envelope_c transform]
/logs/xml/*.xml                  ──┘         │
                                              │  1. Validate (abort if empty)
                                              │  2. SHA-256 hash + raw_len
                                              │  3. Subtype detection:
                                              │     contains "Sysmon"
                                              │         → windows.sysmon
                                              │     contains "PowerShell"
                                              │         → windows.powershell
                                              │     else
                                              │         → windows.security
                                              │  4. Build ULPF Envelope
                                              │     (includes evtx.channel + evtx.provider)
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                         [kafka_out]              [local_debug]
                         ulpf-raw-logs            /logs/debug/instance-c-sent.ndjson
                         → central parser         (windows_evtx route → Audit Activity 4801)
```

---

## Log Sources

| Source File Pattern                    | Format   | Classified As        | OCSF Class (central) |
| :------------------------------------- | :------- | :------------------- | :------------------- |
| `/logs/syslog/windows_events.log`      | EVTX XML | `windows.security`   | Audit Activity       |
| `/logs/xml/*.xml`                      | EVTX XML | `windows.sysmon`     | Audit Activity       |
| `/logs/xml/*.xml`                      | EVTX XML | `windows.powershell` | Audit Activity       |

---

## Environment Variables

| Variable         | Default         | Description                              |
| :--------------- | :-------------- | :--------------------------------------- |
| `SITE_ID`        | `kol-dc1`       | Data center identifier                   |
| `COLLECTOR_ID`   | `collector-c`   | Unique node name for traceability        |
| `KAFKA_BOOTSTRAP`| `kafka:9092`    | Kafka broker address                     |
| `INSTANCE_ENV`   | `test`          | Environment label (test/staging/prod)    |
| `MOCK_MODE`      | `false`         | Enable built-in mock Windows XML generator |
| `VECTOR_LOG`     | `info`          | Vector log verbosity                     |
