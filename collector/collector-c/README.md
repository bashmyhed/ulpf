# ULPF Collector Instance C (Windows EVTX XML)

Edge collector instance dedicated to Windows Event Logs (Security Auditing, Sysmon, and PowerShell operational channels).

## Supported Sources & Enveloping

| Source | Format | Canonical `source.type` | Vendor / Product | Extra Metadata |
|---|---|---|---|---|
| Windows Security | XML | `windows.security` | Microsoft / Security-Auditing | `source.evtx` (channel, provider) |
| Windows Sysmon | XML | `windows.sysmon` | Microsoft / Sysmon | `source.evtx` (channel, provider) |
| PowerShell Operational | XML | `windows.powershell` | Microsoft / PowerShell | `source.evtx` (channel, provider) |

## Key Responsibilities

1. **Edge Ingestion**: Reads live XML event logs from `/logs/xml/*.log` and `/logs/xml/*.xml`.
2. **Lossless Framing**: Computes SHA-256 (`raw_sha256`) and byte length (`raw_len`) over raw bytes.
3. **v1 Envelope Packaging**: Stamps `site_id`, `collector_id`, `collected_at` (epoch ms), clock sync status, file position.
4. **Kafka Shipping**: Streams envelopes to Kafka topic `ulpf-raw-logs`.

## Build & Run

### 1. Build Image

```bash
docker build -t ulpf-collector-c:latest ./collector/collector-c
```

### 2. Run in Production (Tail Real Logs)

```bash
docker run -d \
  --name ulpf-collector-c \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e SITE_ID=kol-dc1 \
  -e COLLECTOR_ID=collector-c \
  -e MOCK_MODE=false \
  -v /var/log/windows:/logs/xml:ro \
  ulpf-collector-c:latest
```

### 3. Run in Mock / Self-Contained Test Mode

```bash
docker run -d \
  --name ulpf-collector-c-mock \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e MOCK_MODE=true \
  ulpf-collector-c:latest
```
When `MOCK_MODE=true`, background Python emulators generate realistic Poisson-distributed Windows Security events directly into `/logs/xml/windows_events.log`.
