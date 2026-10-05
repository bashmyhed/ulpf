# ULPF Collector Instance A (Syslog / CEF / LEEF)

Edge collector instance dedicated to network devices, perimeter firewalls, and operating system authentication logs.

## Supported Sources & Enveloping

| Source | Format | Canonical `source.type` | Vendor / Product | Extra Metadata |
|---|---|---|---|---|
| Cisco ASA Firewall | RFC 3164 Syslog | `fw.cisco.asa` | Cisco / ASA | `source.syslog` (rfc, facility) |
| Linux Auth | RFC 3164 Syslog | `linux.auth` | Linux / PAM-sshd | `source.syslog`, `source.os` |
| Palo Alto PAN-OS | ArcSight CEF | `fw.paloalto` | Palo Alto Networks / PAN-OS | `source.cef` (version, device_vendor) |
| IBM QRadar | IBM LEEF 1.0 | `siem.qradar` | IBM / QRadar | `source.leef` (version, delimiter) |

## Key Responsibilities

1. **Edge Ingestion**: Reads live log files from `/logs/syslog/`, `/logs/cef/`, and `/logs/raw/`.
2. **Lossless Framing**: Computes SHA-256 (`raw_sha256`) and byte length (`raw_len`) over raw bytes.
3. **v1 Envelope Packaging**: Stamps `site_id`, `collector_id`, `collected_at` (epoch ms), clock sync status, file position.
4. **Kafka Shipping**: Streams envelopes to Kafka topic `ulpf-raw-logs`.

## Build & Run

### 1. Build Image

```bash
docker build -t ulpf-collector-a:latest ./collector/collector-a
```

### 2. Run in Production (Tail Real Logs)

```bash
docker run -d \
  --name ulpf-collector-a \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e SITE_ID=kol-dc1 \
  -e COLLECTOR_ID=collector-a \
  -e MOCK_MODE=false \
  -v /var/log/remote:/logs:ro \
  ulpf-collector-a:latest
```

### 3. Run in Mock / Self-Contained Test Mode

```bash
docker run -d \
  --name ulpf-collector-a-mock \
  --network ulpf-net \
  -e KAFKA_BOOTSTRAP=kafka:9092 \
  -e MOCK_MODE=true \
  ulpf-collector-a:latest
```
When `MOCK_MODE=true`, background Python emulators generate realistic Poisson-distributed logs directly into `/logs/...`.
