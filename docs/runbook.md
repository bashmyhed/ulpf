# ULPF Pipeline — Manual Test Runbook

**SIH 2026 · Problem ID 26156 · NTRO ULPF**  
Step-by-step guide to run and verify every stage of the pipeline transparently.

> [!NOTE]
> This runbook covers two modes:
> - **Mode A — Python simulation** (works right now, no Docker required)
> - **Mode B — Full Docker stack** (Kafka + MinIO + Vector, requires Docker daemon)

---

## Prerequisites

```bash
# Check Python deps
python3 -c "import hashlib, json, csv, re, pathlib; print('Python OK')"

# Check emulator deps (Poisson rate)
python3 -c "import numpy; print('numpy OK')" 2>/dev/null || pip3 install numpy

# Check project root
ls /home/paul/projects/sih2/test-suite/docker/scripts/run_pipeline_test.py
ls /home/paul/projects/sih2/test-suite/emulators/
```

---

## Mode A — Python Simulation (No Docker)

This runs the full logical pipeline in-process: emulator logs → agent envelope → server validation → MinIO preservation + OCSF normalization.  
Every stage is verifiable independently.

---

### Stage 1 — Generate Fresh Log Files (Emulators)

Run each emulator to produce a batch of raw log events into the log directories.  
Each emulator streams **one event at a time** (Poisson process) to stdout, which you redirect to a log file.

```bash
cd /home/paul/projects/sih2/test-suite

# --- Collector A log sources ---

# Cisco ASA syslog (RFC 3164)
python3 emulators/cisco_asa_syslog.py --count 5 --rate 0.5 \
  > docker/logs/syslog/cisco_asa.log 2>/dev/null
echo "[✓] cisco_asa.log: $(wc -l < docker/logs/syslog/cisco_asa.log) lines"

# Linux auth syslog (PAM/sshd)
python3 emulators/linux_auth.py --count 5 --rate 0.5 \
  > docker/logs/syslog/linux_auth.log 2>/dev/null
echo "[✓] linux_auth.log: $(wc -l < docker/logs/syslog/linux_auth.log) lines"

# Palo Alto PAN-OS (CEF)
python3 emulators/firewall_cef.py --count 5 --rate 0.5 \
  > docker/logs/cef/paloalto.log 2>/dev/null
echo "[✓] paloalto.log: $(wc -l < docker/logs/cef/paloalto.log) lines"

# IBM QRadar (LEEF)
python3 emulators/leef_qradar.py --count 5 --rate 0.5 \
  > docker/logs/raw/qradar.log 2>/dev/null
echo "[✓] qradar.log: $(wc -l < docker/logs/raw/qradar.log) lines"

# --- Collector B log sources ---

# nginx access log (JSON)
python3 emulators/nginx_access.py --count 5 --rate 0.5 \
  > docker/logs/json/nginx.log 2>/dev/null
echo "[✓] nginx.log: $(wc -l < docker/logs/json/nginx.log) lines"

# AWS CloudTrail (JSON)
python3 emulators/cloudtrail_json.py --count 3 --rate 0.5 \
  > docker/logs/json/cloudtrail.log 2>/dev/null
echo "[✓] cloudtrail.log: $(wc -l < docker/logs/json/cloudtrail.log) lines"

# Kubernetes API audit (JSON)
python3 emulators/k8s_audit.py --count 3 --rate 0.5 \
  > docker/logs/json/k8s_audit.log 2>/dev/null
echo "[✓] k8s_audit.log: $(wc -l < docker/logs/json/k8s_audit.log) lines"

# IoT sensor telemetry (JSON)
python3 emulators/iot_sensor.py --count 5 --rate 0.5 \
  > docker/logs/json/iot.log 2>/dev/null
echo "[✓] iot.log: $(wc -l < docker/logs/json/iot.log) lines"

# PostgreSQL CSV log
python3 emulators/db_postgres.py --count 5 --rate 0.5 \
  > docker/logs/csv/postgres.csv 2>/dev/null
echo "[✓] postgres.csv: $(wc -l < docker/logs/csv/postgres.csv) lines"

# --- Collector C log sources ---

# Windows Security / Sysmon (EVTX XML, single-line)
python3 emulators/windows_event.py --count 10 --rate 0.5 \
  > docker/logs/syslog/windows_events.log 2>/dev/null
echo "[✓] windows_events.log: $(wc -l < docker/logs/syslog/windows_events.log) lines"
```

**Verify raw log content:**
```bash
# Spot-check each format
head -2 docker/logs/syslog/cisco_asa.log    # should start with %ASA-
head -2 docker/logs/cef/paloalto.log        # should start with CEF:0|
head -2 docker/logs/raw/qradar.log          # should start with LEEF:1.0|
head -2 docker/logs/json/nginx.log | python3 -m json.tool  # valid JSON
head -2 docker/logs/csv/postgres.csv        # comma-separated
head -1 docker/logs/syslog/windows_events.log | grep -o '<Event' && echo "XML OK"
```

---

### Stage 2 — Run the Full Pipeline

```bash
cd /home/paul/projects/sih2/test-suite/docker
python3 scripts/run_pipeline_test.py
```

Expected output (all 5 stages):

```
━━━ 1 / 5 — Ingest & Envelope from real emulator logs (metadataGuide v1) ━━━
[INFO]    collector-a ← cisco_asa.log: N envelopes → Kafka
...
[INFO]    Total raw envelopes queued: N

━━━ 2 / 5 — Central Processor: Validate, Stamp ULID, Preserve & Normalize ━━━
[INFO]    Processed N events | SHA256 OK: N FAIL: 0 | Length FAIL: 0

━━━ 3 / 5 — Write outputs: MinIO Data Lake Preservation + OCSF Stream ━━━
...

━━━ 4 / 5 — Validation against metadataGuide Section 3 & 8 ━━━

━━━ 5 / 5 — Summary Report ━━━
  RESULT: PASSED ✓
```

---

### Stage 3 — Verify Preservation (Raw Envelopes / "MinIO")

The raw-lake file simulates what goes into MinIO `ulpf-data-lake` bucket.

```bash
# Count records
wc -l docker/output/raw-lake/preservation-events.ndjson

# Inspect first envelope (pretty printed)
head -1 docker/output/raw-lake/preservation-events.ndjson | python3 -m json.tool

# Verify key fields are present
python3 - <<'EOF'
import json
errors = []
with open("docker/output/raw-lake/preservation-events.ndjson") as f:
    for i, line in enumerate(f, 1):
        e = json.loads(line)
        for field in ["event_id","envelope_version","site_id","collector_id",
                      "seq","collected_at","source","raw","raw_sha256","raw_len",
                      "integrity","ingested_at","central_node"]:
            if field not in e:
                errors.append(f"line {i}: missing '{field}'")
        # Check integrity
        if not e.get("integrity", {}).get("verified"):
            errors.append(f"line {i}: integrity.verified is False")
        if not e.get("integrity", {}).get("length_verified"):
            errors.append(f"line {i}: integrity.length_verified is False")

if errors:
    for err in errors: print(f"[FAIL] {err}")
else:
    print(f"[PASS] All {i} preservation envelopes are valid")
EOF
```

**Verify SHA-256 independently:**
```bash
python3 - <<'EOF'
import json, hashlib
with open("docker/output/raw-lake/preservation-events.ndjson") as f:
    for i, line in enumerate(f, 1):
        e = json.loads(line)
        raw = e["raw"]
        expected = e["raw_sha256"]
        actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if actual != expected:
            print(f"[FAIL] line {i} SHA256 mismatch: {e['source']['type']}")
            print(f"  expected: {expected}")
            print(f"  actual:   {actual}")
            break
else:
    print(f"[PASS] All {i} SHA-256 hashes independently verified")
EOF
```

---

### Stage 4 — Verify OCSF Events

```bash
# Count OCSF events
wc -l docker/output/ocsf-events.ndjson

# Pretty-print first event
head -1 docker/output/ocsf-events.ndjson | python3 -m json.tool

# Show OCSF class breakdown
python3 - <<'EOF'
import json
from collections import defaultdict
counts = defaultdict(int)
with open("docker/output/ocsf-events.ndjson") as f:
    for line in f:
        e = json.loads(line)
        key = f"{e['metadata']['log_name']:<30} class_uid={e['class_uid']} ({e['class_name']})"
        counts[key] += 1
print(f"{'source.type':<30}  {'class_uid':<10}  {'class_name':<30}  n")
print("-" * 80)
for k, n in sorted(counts.items()):
    print(f"  {k}  {n}")
EOF
```

**Check that every OCSF event carries lossless raw data:**
```bash
python3 - <<'EOF'
import json
with open("docker/output/ocsf-events.ndjson") as f:
    for i, line in enumerate(f, 1):
        e = json.loads(line)
        if "raw_data" not in e.get("unmapped", {}):
            print(f"[FAIL] line {i}: missing unmapped.raw_data")
            break
        if "envelope" not in e.get("unmapped", {}):
            print(f"[FAIL] line {i}: missing unmapped.envelope")
            break
else:
    print(f"[PASS] All {i} OCSF events carry unmapped.raw_data + unmapped.envelope")
EOF
```

---

### Stage 5 — Run the Official Validator

```bash
cd /home/paul/projects/sih2/test-suite/docker
python3 scripts/validate_ocsf.py
```

This checks all rules from [`docs/validation-rules.md`](../docs/validation-rules.md):
- Required OCSF fields
- `metadata.logged_time`, `metadata.processed_time`, `metadata.uid` (ULID)
- `integrity.verified == true`
- `integrity.length_verified == true`
- `unmapped.envelope` present
- `source.type` in canonical registry

---

### Stage 6 — Spot-Check Individual Source Types

Each source type has its own per-format output file:

```bash
# Cisco ASA — network activity
head -1 docker/output/by-format/fw_cisco_asa.ndjson | python3 -c "
import json,sys; e=json.load(sys.stdin)
print('class_uid:', e['class_uid'])
print('src_ip:', e.get('src_endpoint',{}).get('ip','—'))
print('event_code:', e['metadata'].get('event_code','—'))
print('raw:', e['unmapped']['raw_data'][:80])
"

# Palo Alto CEF
head -1 docker/output/by-format/fw_paloalto.ndjson | python3 -c "
import json,sys; e=json.load(sys.stdin)
print('class_uid:', e['class_uid'])
print('raw_format:', e['unmapped']['envelope']['raw_format'])
print('raw:', e['unmapped']['raw_data'][:80])
"

# Windows Security (EVTX XML)
head -1 docker/output/by-format/windows_security.ndjson | python3 -c "
import json,sys; e=json.load(sys.stdin)
print('class_uid:', e['class_uid'])
print('event_code:', e['metadata'].get('event_code','—'))
print('raw:', e['unmapped']['raw_data'][:100])
"

# PostgreSQL CSV
head -1 docker/output/by-format/db_postgres.ndjson | python3 -c "
import json,sys; e=json.load(sys.stdin)
print('class_uid:', e['class_uid'])
print('raw:', e['unmapped']['raw_data'][:100])
"

# CloudTrail JSON
head -1 docker/output/by-format/cloud_aws_cloudtrail.ndjson | python3 -c "
import json,sys; e=json.load(sys.stdin)
print('class_uid:', e['class_uid'])
print('raw:', e['unmapped']['raw_data'][:100])
"
```

---

### Stage 7 — Verify Chain of Custody (Envelope ↔ OCSF Cross-check)

Confirm that every OCSF event's `event_id` matches the preservation envelope:

```bash
python3 - <<'EOF'
import json

# Build index of preservation envelopes keyed by event_id
preserve = {}
with open("docker/output/raw-lake/preservation-events.ndjson") as f:
    for line in f:
        e = json.loads(line)
        preserve[e["event_id"]] = e

# Cross-check OCSF events
errors = 0
with open("docker/output/ocsf-events.ndjson") as f:
    for i, line in enumerate(f, 1):
        ocsf = json.loads(line)
        uid = ocsf["metadata"]["uid"]
        if uid not in preserve:
            print(f"[FAIL] line {i}: event_id {uid} not in preservation lake")
            errors += 1
            continue
        penv = preserve[uid]
        # Cross-check: raw data matches
        if ocsf["unmapped"]["raw_data"] != penv["raw"]:
            print(f"[FAIL] line {i}: raw_data mismatch for {uid}")
            errors += 1
        # Cross-check: SHA matches
        if ocsf["metadata"]["integrity"]["collector_hash"] != penv["raw_sha256"]:
            print(f"[FAIL] line {i}: SHA256 mismatch for {uid}")
            errors += 1

if errors == 0:
    print(f"[PASS] All {i} OCSF events cross-verified against preservation lake")
else:
    print(f"[FAIL] {errors} discrepancies found")
EOF
```

---

## Quick One-Liner Run (All Stages)

```bash
cd /home/paul/projects/sih2/test-suite/docker && \
  python3 scripts/run_pipeline_test.py && \
  python3 scripts/validate_ocsf.py && \
  echo "=== PIPELINE COMPLETE ==="
```

---

## Mode B — Full Docker Stack (When Docker Daemon Is Running)

> [!IMPORTANT]
> Requires Docker daemon. Start it with: `sudo systemctl start docker`

### Step 1 — Start the Stack

```bash
cd /home/paul/projects/sih2/test-suite/docker
sudo systemctl start docker   # one-time if daemon is stopped

# Pull images first (first run only)
bash run_test.sh --pull-only  # or: docker compose pull

# Start everything
docker compose up -d
```

Services started:
| Service | Port | Role |
|---------|------|------|
| `zookeeper` | 2181 | Kafka coordination |
| `kafka` | 9092 | Message broker |
| `minio` | 9000 / 9001 | Object store (data lake) |
| `minio-init` | — | Creates `ulpf-data-lake` bucket |
| `minio-init` | — | Creates `ulpf-data-lake` bucket |
| `ulpf-collector-a` | — | Agent A: Syslog/CEF/LEEF (Site A • `kol-dc1`) |
| `ulpf-collector-b` | — | Agent B: JSON/CSV (Site B • `del-dc2`) |
| `ulpf-collector-c` | — | Agent C: EVTX XML (Site C • `mum-dc3`) |
| `ulpf-central-parser` | — | Vector Server Engine: ULID, OCSF, Dual-Branch (Server Central • `kol-dc1`) |

### Step 2 — Run Emulators (Continuous Streaming)

In separate terminals (or with `&`):

```bash
cd /home/paul/projects/sih2/test-suite

# Terminal 1 — Agent A sources (Site A)
python3 emulators/cisco_asa_syslog.py --rate 1 >> docker/logs/syslog/cisco_asa.log &
python3 emulators/linux_auth.py        --rate 1 >> docker/logs/syslog/linux_auth.log &
python3 emulators/firewall_cef.py      --rate 1 >> docker/logs/cef/paloalto.log &
python3 emulators/leef_qradar.py       --rate 1 >> docker/logs/raw/qradar.log &

# Terminal 2 — Agent B sources (Site B)
python3 emulators/nginx_access.py    --rate 1 >> docker/logs/json/nginx.log &
python3 emulators/cloudtrail_json.py --rate 2 >> docker/logs/json/cloudtrail.log &
python3 emulators/k8s_audit.py       --rate 2 >> docker/logs/json/k8s_audit.log &
python3 emulators/iot_sensor.py      --rate 1 >> docker/logs/json/iot.log &
python3 emulators/db_postgres.py     --rate 1 >> docker/logs/csv/postgres.csv &

# Terminal 3 — Agent C sources (Site C)
python3 emulators/windows_event.py   --rate 0.5 >> docker/logs/syslog/windows_events.log &
```

### Step 3 — Monitor Kafka Topic

```bash
# List topics
docker exec ulpf-kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Tail the raw-logs topic (live stream)
docker exec ulpf-kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic ulpf-raw-logs \
  --from-beginning \
  --max-messages 5 | python3 -m json.tool

# Check consumer group lag
docker exec ulpf-kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group ulpf-central-parser
```

### Step 4 — Monitor MinIO (Data Lake)

Open MinIO console in browser:
```
http://localhost:9001
Username: minioadmin
Password: minioadmin
```

Or via CLI:
```bash
# Install mc (MinIO client) if not present
docker run --rm --entrypoint mc minio/mc \
  alias set local http://localhost:9000 minioadmin minioadmin

# List preservation objects by source type
docker run --rm --entrypoint mc minio/mc \
  ls local/ulpf-data-lake/raw-preservation/
```

### Step 5 — Check Vector Logs

```bash
# Server engine logs (shows routing, validation, ULID stamping)
docker logs ulpf-central-parser --tail 50 -f

# Agent A logs
docker logs ulpf-collector-a --tail 20

# Check for DLQ events
docker exec ulpf-kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic ulpf-dlq \
  --from-beginning \
  --timeout-ms 3000
```

### Step 6 — Inspect Live Output Files

```bash
# OCSF stream (appended live)
tail -f docker/output/ocsf-events.ndjson | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    print(f\"{e['metadata']['uid']} | {e['metadata']['log_name']:<25} | class={e['class_uid']} | verified={e['metadata']['integrity']['verified']}\")
"

# Preservation lake (live)
tail -f docker/output/raw-lake/preservation-events.ndjson | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    print(f\"{e['event_id']} | {e['source']['type']:<25} | sha_ok={e['integrity']['verified']}\")
"
```

### Step 7 — Tear Down

```bash
docker compose down
# To also remove volumes (MinIO data):
docker compose down -v
```

---

## Output Files Reference

After running Mode A or B:

| File | Description |
|------|-------------|
| `docker/output/raw-lake/preservation-events.ndjson` | Raw envelopes with ULID stamps — the lossless chain-of-custody record |
| `docker/output/ocsf-events.ndjson` | All 194 OCSF 1.3 normalized events |
| `docker/output/by-format/fw_cisco_asa.ndjson` | Events for `fw.cisco.asa` only |
| `docker/output/by-format/fw_paloalto.ndjson` | Events for `fw.paloalto` only |
| `docker/output/by-format/linux_auth.ndjson` | Events for `linux.auth` only |
| `docker/output/by-format/siem_qradar.ndjson` | Events for `siem.qradar` only |
| `docker/output/by-format/web_nginx_access.ndjson` | Events for `web.nginx.access` only |
| `docker/output/by-format/cloud_aws_cloudtrail.ndjson` | Events for `cloud.aws.cloudtrail` only |
| `docker/output/by-format/k8s_audit.ndjson` | Events for `k8s.audit` only |
| `docker/output/by-format/iot_sensor.ndjson` | Events for `iot.sensor` only |
| `docker/output/by-format/db_postgres.ndjson` | Events for `db.postgres` only |
| `docker/output/by-format/windows_security.ndjson` | Events for `windows.security` only |

---

## What a Passing Run Proves

| Claim | How verified |
|-------|-------------|
| Raw log faithfully preserved | `raw_sha256` matches SHA-256 of `raw` (Stage 3) |
| No byte-level corruption | `raw_len` matches `len(raw.encode('utf-8'))` (Stage 3) |
| Chain of custody traceable | Every OCSF event cross-references preservation lake by `event_id` (Stage 7) |
| Globally unique event IDs | ULIDs are sortable by `collected_at` ms, no collisions |
| OCSF normalization correct | 0 validation errors from `validate_ocsf.py` (Stage 5) |
| All 10 source types covered | Source type breakdown table shows all types (Stage 4) |
| Lossless guarantee | Every OCSF event has `unmapped.raw_data` + `unmapped.envelope` (Stage 4) |
