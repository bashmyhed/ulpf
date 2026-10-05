# ULPF Config Management System

Centralized configuration control for all Vector collectors and the central parser. A bad config can never reach a machine.

## Architecture

```
┌─────────────┐     push (HTTPS)      ┌─────────────────┐
│   Author    │ ─────────────────────► │  Bare Git Repo  │
└─────────────┘                        │  (config-repo)  │
                                       │  + pre-receive  │
                                       └────────┬────────┘
                                                │ git read
                                                ▼
                                       ┌─────────────────┐
                                       │  Config Server  │
                                       │  (Go, :8080)    │
                                       │  • Bundle build │
                                       │  • Validation   │
                                       │  • /config      │
                                       │  • /ack         │
                                       │  • /status      │
                                       └────────┬────────┘
                                                │ HTTP
                        ┌───────────────────────┼───────────────────────┐
                        ▼                       ▼                       ▼
               ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
               │ Collector A   │      │ Collector B   │      │ Collector C   │
               │ + config-agent│      │ + config-agent│      │ + config-agent│
               └───────────────┘      └───────────────┘      └───────────────┘
                        │                       │                       │
                        ▼                       ▼                       ▼
               ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
               │  Vector       │      │  Vector       │      │  Vector       │
               └───────────────┘      └───────────────┘      └───────────────┘
```

## Components

### 1. Bare Git Repository (`/opt/ulpf-config.git`)

**Location**: `/home/paul/projects/sih2/config-repo/` (dev) → mounted at `/opt/ulpf-config.git` in containers

**Authentication**: HTTP Basic Auth via Caddy/nginx (not implemented in dev)

**Pre-receive Hook**: Validates every push
```bash
# Runs on every push
vector validate --no-environment --config-dir <config-dir>
# + envelope validation script
```

**Repo Layout**:
```
config-repo/
├── global/
│   └── vector.yaml              # Shared Vector settings (api, etc.)
├── sites/
│   └── kol-dc1/
│       ├── collector-a/vector.yaml
│       ├── collector-b/vector.yaml
│       ├── collector-c/vector.yaml
│       └── central/vector.yaml  # Central parser config
└── machines/
    ├── collector-a-01/vector.yaml   # Machine-specific overrides
    ├── collector-b-01/vector.yaml
    ├── collector-c-01/vector.yaml
    └── central-01/vector.yaml
```

**Merge Priority** (low → high):
1. `global/vector.yaml`
2. `sites/<site>/<collector>/vector.yaml`
3. `machines/<machine>/vector.yaml`

### 2. Config Server (Go)

**Binary**: `config-server` (in `config-server/` dir)

**Endpoints**:
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | none | Health check, returns HEAD SHA |
| GET | `/config` | agent token | Returns bundle or 304 if unchanged |
| POST | `/ack` | agent token | Agent reports apply result |
| GET | `/status` | admin token | Fleet status dashboard |

**Query Parameters** (GET /config):
```
?site_id=kol-dc1&machine_id=collector-a-01&collector_type=collector-a&since_sha=<sha>
```

**Response** (ConfigBundle):
```json
{
  "sha": "f02d2bb64311d8155d83a13544eb0d0f1dff9ceb",
  "site_id": "kol-dc1",
  "machine_id": "collector-a-01",
  "collector_type": "collector-a",
  "files": {
    "global/vector.yaml": "...",
    "sites/kol-dc1/collector-a/vector.yaml": "...",
    "machines/collector-a-01/vector.yaml": "..."
  },
  "env_vars": {
    "KAFKA_BOOTSTRAP": "kafka:9092",
    "MINIO_ENDPOINT": "http://minio:9000",
    ...
  },
  "generated_at": "2026-10-05T16:19:42+05:30"
}
```

**Ack Payload**:
```json
{
  "machine_id": "collector-a-01",
  "site_id": "kol-dc1",
  "collector_type": "collector-a",
  "applied_sha": "f02d2bb...",
  "status": "applied",  // or "failed", "rolled_back"
  "error": "optional error message",
  "timestamp": "2026-10-05T11:06:06Z"
}
```

**Environment Variables**:
```
GIT_REPO_PATH=/opt/ulpf-config.git
SECRETS_DIR=/etc/ulpf/secrets
ADDR=:8080
STATUS_FILE=/data/fleet-status.json
ADMIN_TOKEN=admin-token
AGENT_TOKENS=collector-a-token:collector-a-01:kol-dc1,...
```

### 3. Config Agent (Go)

**Binary**: `config-agent` (embedded in each collector container)

**Lifecycle**:
```
poll (30s) ──► GET /config?since_sha=X
                │
                ├─ 304 Not Modified ──► wait
                │
                └─ 200 OK ──► stage bundle
                             │
                             ├─ vector validate --config-dir <stage>
                             │      │
                             │      └─ FAIL ──► POST /ack {status: failed}
                             │
                             ├─ atomic swap (symlink)
                             │
                             ├─ SIGHUP Vector PID
                             │      │
                             │      └─ FAIL ──► rollback ──► POST /ack {status: rolled_back}
                             │
                             └─ SUCCESS ──► POST /ack {status: applied}
```

**Environment Variables**:
```
CONFIG_SERVER_URL=http://config-server:8080
AGENT_TOKEN=collector-a-token
SITE_ID=kol-dc1
MACHINE_ID=collector-a-01
COLLECTOR_TYPE=collector-a
VECTOR_CONFIG_DIR=/etc/vector
STAGING_DIR=/staging
BACKUP_DIR=/backup
VECTOR_PID_FILE=/run/vector.pid
POLL_INTERVAL=30s
```

**Directories**:
- `/staging/<sha>/` - Staged bundle during apply
- `/backup/backup-<timestamp>/` - Previous configs for rollback (keeps last 3)
- `/etc/vector/` - Active config (symlink to staging)
- `/run/vector.pid` - Vector PID for SIGHUP

## Deployment

### Docker Compose Services

```yaml
config-server:
  build: ./config-server
  ports: ["8080:8080"]
  volumes:
    - ./config-repo:/opt/ulpf-config.git:ro
    - ./config-server/secrets:/etc/ulpf/secrets:ro
    - config-server-data:/data

collector-a:
  build: ./collector/collector-a
  volumes:
    - collector-a-config:/etc/vector
    - collector-a-staging:/staging
    - collector-a-backup:/backup
  environment:
    - CONFIG_SERVER_URL=http://config-server:8080
    - AGENT_TOKEN=collector-a-token
    - SITE_ID=kol-dc1
    - MACHINE_ID=collector-a-01
    - COLLECTOR_TYPE=collector-a
    - VECTOR_CONFIG_DIR=/etc/vector
    - STAGING_DIR=/staging
    - BACKUP_DIR=/backup
    - VECTOR_PID_FILE=/run/vector.pid
```

### Starting the Stack

```bash
# Full stack with config management
docker compose up -d

# Check config server
curl http://localhost:8080/health

# Verify fleet status
curl -H "Authorization: Bearer admin-token" \
  http://localhost:8080/status?site_id=kol-dc1
```

## Operations

### Adding a New Collector Config

```bash
# 1. Clone repo
git clone http://config.ulpf.internal/ulpf-config.git
cd ulpf-config

# 2. Add/modify config
vim sites/kol-dc1/collector-a/vector.yaml

# 3. Push (validates automatically)
git push origin main
```

### Machine-Specific Override

```bash
# Create override
echo 'sources:
  syslog_files:
    include:
      - /custom/path/*.log' > machines/collector-a-01/vector.yaml

git add machines/collector-a-01/vector.yaml
git commit -m "Override log path for collector-a-01"
git push
```

### Rollback

```bash
# On central server
cd /opt/ulpf-config.git
git revert HEAD
git push origin main

# Agents pick up on next poll (30s)
```

### View Fleet Status

```bash
curl -H "Authorization: Bearer admin-token" \
  http://config-server:8080/status?site_id=kol-dc1
```

Response:
```json
{
  "site_id": "kol-dc1",
  "machines": [
    {
      "machine_id": "collector-a-01",
      "collector_type": "collector-a",
      "current_sha": "f02d2bb...",
      "status": "current",
      "last_ack": "2026-10-05T11:06:06Z"
    },
    {
      "machine_id": "collector-b-01",
      "collector_type": "collector-b",
      "current_sha": "f02d2bb...",
      "status": "behind",
      "last_ack": "2026-10-05T10:55:00Z"
    }
  ],
  "head_sha": "f02d2bb..."
}
```

Status values:
- `current` - Applied HEAD SHA
- `behind` - Applied older SHA
- `failed` - Last apply failed
- `unknown` - No ack received yet

## Security (Dev vs Production)

| Aspect | Dev | Production |
|--------|-----|------------|
| Git Auth | None | Basic Auth + TLS |
| Config Server Auth | Bearer tokens (hardcoded) | mTLS or rotated tokens |
| Agent Credentials | Env var | File-based secrets |
| Bundle Signing | None | ed25519 (planned) |

## Testing Locally

```bash
# Build images
docker compose build

# Start
docker compose up -d

# Test config fetch
docker exec ulpf-config-server curl -H "Authorization: Bearer collector-a-token" \
  "http://localhost:8080/config?site_id=kol-dc1&machine_id=collector-a-01&collector_type=collector-a"

# Check Vector is running with managed config
docker exec ulpf-collector-a ls -la /etc/vector/
# Should show symlink to /staging/<sha>/

# View Vector logs
docker logs ulpf-collector-a | grep -E "config-agent|Vector"
```

## Troubleshooting

**Config server returns "bundle validation failed"**:
- Check merged YAML has valid sources/sinks/transforms
- Verify env var substitution worked: `docker logs ulpf-config-server | grep "Merged YAML"`

**Agent fails to apply**:
- Check staging dir: `docker exec ulpf-collector-a ls /staging/`
- Check validation output in agent logs: `docker logs ulpf-collector-a | grep "Failed to apply"`

**Vector duplicate component errors**:
- Ensure entrypoint uses `--config-dir /etc/vector` not `--config /etc/vector/vector.yaml`
- Verify `/etc/vector` is a symlink (not a directory with multiple files)

**Agent not picking up new config**:
- Check current SHA: `docker exec ulpf-collector-a cat /etc/vector/.applied_sha`
- Force re-fetch by deleting SHA file and restarting agent

## File Locations

| File | Purpose |
|------|---------|
| `/home/paul/projects/sih2/config-repo/` | Bare git repo (dev) |
| `/home/paul/projects/sih2/config-server/` | Config server source |
| `/home/paul/projects/sih2/config-agent/` | Config agent source |
| `/home/paul/projects/sih2/collector/*/entrypoint.sh` | Updated to start config-agent |
| `/home/paul/projects/sih2/central/entrypoint.sh` | Updated to start config-agent |
| `/home/paul/projects/sih2/docker-compose.yml` | All services defined |