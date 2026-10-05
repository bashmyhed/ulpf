# ULPF Vector Configuration Management Server

A lightweight, secure HTTP configuration management server for Vector collector and central instances. Built using **pure Python 3 standard library** with zero external dependencies, making it instantly deployable in air-gapped environments.

---

## Key Features

1. **Pre-Deployment `vector validate` Gate**:
   Every configuration change is validated via `vector validate --no-environment` in an isolated staging sandbox before deployment.
2. **Zero-Disruption Fallback Guarantee**:
   If a proposed configuration fails validation (syntax error, broken VRL logic, invalid DAG connection), the deployment is **immediately rejected (HTTP 422)**. The running collector continues operating on the previous valid configuration with zero disruption.
3. **Git Versioning & Audit Trail**:
   Every successful deployment creates an immutable Git commit with commit hash, author, timestamp, and message. Native rollback to any historical commit is supported via API.
4. **Lightweight Collector Polling (ETag / HTTP 304)**:
   Collectors fetch active configs using `If-None-Match: <commit_sha>`. When unchanged, the server returns `304 Not Modified` with zero body bandwidth.
5. **Atomic Deployments**:
   Active configurations are written using POSIX atomic renames (`os.replace`), ensuring Vector file watchers never read partial writes.
6. **Timing-Safe Authentication**:
   All administrative and configuration endpoints require Bearer Token / API Key authentication compared using `hmac.compare_digest`.
7. **Structured Audit Logging**:
   All validation events, deployment attempts, authentication failures, and rollbacks are recorded to console and `audit.log`.

---

## Architecture

```
                               ┌─────────────────────────────────────────────────────────────┐
                               │                    CONFIG SERVER (Python)                   │
                               │                                                             │
  Client / Operator / CI       │   ┌─────────────────────────────────────────────────────┐   │
   [POST /api/v1/configs/{id}] ───►│ 1. Auth & Input Sanitization (Bearer / API Token)   │   │
                               │   └──────────────────────────┬──────────────────────────┘   │
                               │                              │                              │
                               │   ┌──────────────────────────▼──────────────────────────┐   │
                               │   │ 2. Isolated Staging: writes proposed config to temp │   │
                               │   └──────────────────────────┬──────────────────────────┘   │
                               │                              │                              │
                               │   ┌──────────────────────────▼──────────────────────────┐   │
                               │   │ 3. Pre-Deployment: vector validate --no-environment │   │
                               │   └───────────────┬─────────────────────┬───────────────┘   │
                               │                   │                     │                   │
                               │             [Pass: Code 0]        [Fail: Code != 0]         │
                               │                   │                     │                   │
                               │                   ▼                     ▼                   │
                               │   ┌────────────────────────┐  ┌─────────────────────────┐  │
                               │   │ 4a. Commit to Git Repo │  │ 4b. Discard Staging     │  │
                               │   │     Atomic os.replace  │  │     Preserve Old Config │  │
                               │   │     Log DEPLOY_SUCCESS │  │     Log VALIDATE_FAILED │  │
                               │   │     Return HTTP 200 OK │  │     Return HTTP 422 Err │  │
                               │   └────────────────────────┘  └─────────────────────────┘  │
                               └─────────────────────────────────────────────────────────────┘
```

---

## Quickstart

### 1. Start the Server
```bash
# Set your secure token (or rely on default in dev)
export ULPF_CONFIG_SERVER_TOKEN="your-secure-secret-token"
export CONFIG_SERVER_PORT=8080

python3 config-server/server.py
```

### 2. Run Automated Tests
```bash
python3 -m unittest discover -s config-server/tests -v
```

---

## API Reference

All `/api/v1/*` endpoints require the header:
```http
Authorization: Bearer <your-token>
```
*(or `X-API-Key: <your-token>`)*

---

### 1. Health Check (Public)
```bash
curl -i http://localhost:8080/health
```
**Response (200 OK)**:
```json
{
  "status": "healthy",
  "service": "ulpf-vector-config-server",
  "version": "1.0.0",
  "uptime_seconds": 12.4,
  "vector_binary": "/home/paul/projects/sih2/test-suite/bin/bin/vector",
  "instances_count": 3
}
```

---

### 2. Fetch Active Config (Collector Ingestion)
```bash
curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/api/v1/configs/collector-a
```
**Response (200 OK)**:
```http
HTTP/1.0 200 OK
Content-Type: application/x-yaml; charset=utf-8
ETag: "8b0de21208bc25a226c43bdede33227c7cd76ce5"
X-Config-Commit: 8b0de21208bc25a226c43bdede33227c7cd76ce5

sources:
  syslog_files:
    type: file
    ...
```

**Subsequent Poll with Cache Verification**:
```bash
curl -i -H "Authorization: Bearer $TOKEN" \
     -H 'If-None-Match: "8b0de21208bc25a226c43bdede33227c7cd76ce5"' \
     http://localhost:8080/api/v1/configs/collector-a
```
**Response (304 Not Modified)**:
```http
HTTP/1.0 304 Not Modified
ETag: "8b0de21208bc25a226c43bdede33227c7cd76ce5"
```

---

### 3. Dry-Run Validate a Configuration
Test whether candidate YAML passes `vector validate` without committing or deploying:
```bash
curl -i -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/x-yaml" \
     --data-binary "@collector/collector-a/vector.yaml" \
     http://localhost:8080/api/v1/configs/collector-a/validate
```
**Response (200 OK if valid, 422 if invalid)**:
```json
{
  "valid": true,
  "instance_id": "collector-a",
  "exit_code": 0,
  "output": "Validated",
  "error": "",
  "duration_ms": 24.5
}
```

---

### 4. Deploy New Configuration
Validates in staging first. If valid, commits to Git and updates the active configuration file atomically:
```bash
curl -i -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/x-yaml" \
     -H "X-Author: Security Team <sec@corp.local>" \
     -H "X-Commit-Message: Add Palo Alto CEF port filter" \
     --data-binary "@collector/collector-a/vector.yaml" \
     http://localhost:8080/api/v1/configs/collector-a
```
**Response on Success (200 OK)**:
```json
{
  "status": "success",
  "phase": "deployed",
  "message": "Configuration validated and deployed successfully.",
  "instance_id": "collector-a",
  "commit_sha": "4a7b12f8c5e631980a32194b6d08129034afc781",
  "validation_duration_ms": 22.8
}
```

**Response on Failure (422 Unprocessable Entity - Active Config Preserved)**:
```json
{
  "status": "error",
  "phase": "validation",
  "message": "Validation failed: configuration rejected. Existing running configuration remains active.",
  "instance_id": "collector-a",
  "active_commit_sha": "8b0de21208bc25a226c43bdede33227c7cd76ce5",
  "exit_code": 78,
  "output": "",
  "error": "x duplicate sink id found: kafka_out",
  "duration_ms": 19.4
}
```

---

### 5. Inspect Git History
```bash
curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/api/v1/configs/collector-a/history
```
**Response (200 OK)**:
```json
{
  "instance_id": "collector-a",
  "count": 2,
  "history": [
    {
      "commit_sha": "4a7b12f8c5e631980a32194b6d08129034afc781",
      "author": "Security Team <sec@corp.local>",
      "timestamp": "2026-10-04T07:35:00+00:00",
      "epoch": 1791099300,
      "message": "[collector-a] Add Palo Alto CEF port filter"
    },
    {
      "commit_sha": "8b0de21208bc25a226c43bdede33227c7cd76ce5",
      "author": "ULPF Config Manager <ulpf-admin@ntro.gov.in>",
      "timestamp": "2026-10-04T07:20:00+00:00",
      "epoch": 1791098400,
      "message": "[collector-a] Initial configuration deployment"
    }
  ]
}
```

---

### 6. Atomic Rollback to a Previous Commit
Reverts instance configuration to a historical Git commit SHA with pre-validation:
```bash
curl -i -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"commit_sha": "8b0de21208bc25a226c43bdede33227c7cd76ce5", "message": "Roll back to baseline"}' \
     http://localhost:8080/api/v1/configs/collector-a/rollback
```
**Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Successfully rolled back collector-a to commit 8b0de212",
  "instance_id": "collector-a",
  "rolled_back_to_sha": "8b0de21208bc25a226c43bdede33227c7cd76ce5",
  "new_commit_sha": "f12c98e104a37b60d9128031e402b8001fa32098"
}
```

---

### 7. Inspect Line-by-Line Diffs
```bash
curl -i -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8080/api/v1/configs/collector-a/diff?from=8b0de212&to=4a7b12f8"
```

---

### 8. View Audit Logs
```bash
curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/api/v1/audit/logs?limit=10
```

---

## Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `CONFIG_SERVER_HOST` | `0.0.0.0` | Host IP to bind server |
| `CONFIG_SERVER_PORT` | `8080` | Port to bind server |
| `ULPF_CONFIG_SERVER_TOKEN` | `ulpf-secret-token-admin-2026` | Bearer token / API Key for authentication |
| `ULPF_REPO_DIR` | `config-server/repo` | Path to Git repository directory |
| `ULPF_ACTIVE_DIR` | `config-server/active` | Path to live deployed configs |
| `ULPF_STAGING_DIR` | `config-server/staging` | Isolated sandbox for pre-deployment validation |
| `ULPF_LOG_FILE` | `config-server/audit.log` | Path to structured audit log file |
| `VECTOR_BIN_PATH` | (Auto-detected) | Explicit path to Vector binary |
