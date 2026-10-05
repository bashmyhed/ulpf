"""
ULPF Lightweight Secure Vector Configuration Management Server
Pure Python 3 standard library HTTP server with Git versioning,
pre-deployment validation gate, zero-disruption fallback, and structured audit logs.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs
import urllib.request

# Internal modules
from config import (
    HOST, PORT, API_TOKEN, ACTIVE_DIR, REPO_DIR, MAX_PAYLOAD_BYTES,
    VECTOR_BIN, is_valid_instance_id, verify_token, ensure_directories
)
from audit_logger import logger, log_audit, get_recent_audit_logs
from git_store import GitStore
from validator import validate_vector_config, validate_partial_vector_config

START_TIME = time.time()
PROJECT_ROOT = Path(__file__).resolve().parent.parent

COLLECTOR_DIRS = {
    "agent-a": PROJECT_ROOT / "collector" / "collector-a",
    "agent-a-01": PROJECT_ROOT / "collector" / "collector-a",
    "collector-a": PROJECT_ROOT / "collector" / "collector-a",
    "collector-a-01": PROJECT_ROOT / "collector" / "collector-a",
    "agent-b": PROJECT_ROOT / "collector" / "collector-b",
    "agent-b-01": PROJECT_ROOT / "collector" / "collector-b",
    "collector-b": PROJECT_ROOT / "collector" / "collector-b",
    "collector-b-01": PROJECT_ROOT / "collector" / "collector-b",
    "agent-c": PROJECT_ROOT / "collector" / "collector-c",
    "agent-c-01": PROJECT_ROOT / "collector" / "collector-c",
    "collector-c": PROJECT_ROOT / "collector" / "collector-c",
    "collector-c-01": PROJECT_ROOT / "collector" / "collector-c",
    "server": PROJECT_ROOT / "central",
    "server-parser": PROJECT_ROOT / "central",
    "server-parser-01": PROJECT_ROOT / "central",
    "central": PROJECT_ROOT / "central",
    "central-parser": PROJECT_ROOT / "central",
    "central-01": PROJECT_ROOT / "central",
}

AGENT_METADATA = [
    {
        "id": "agent-a",
        "name": "Agent A",
        "badge": "Syslog / CEF / LEEF",
        "type": "agent-a",
        "site": "Site A",
        "site_id": "kol-dc1",
    },
    {
        "id": "agent-b",
        "name": "Agent B",
        "badge": "JSON / CSV / CloudTrail",
        "type": "agent-b",
        "site": "Site B",
        "site_id": "del-dc2",
    },
    {
        "id": "agent-c",
        "name": "Agent C",
        "badge": "Windows EVTX / XML",
        "type": "agent-c",
        "site": "Site C",
        "site_id": "mum-dc3",
    },
    {
        "id": "server-parser",
        "name": "Server Parser",
        "badge": "OCSF Normalizer & Router",
        "type": "server",
        "site": "Server Central",
        "site_id": "kol-dc1",
    },
]

COLLECTOR_METADATA = AGENT_METADATA

def _list_collector_files(collector_id: str) -> list:
    c_dir = COLLECTOR_DIRS.get(collector_id)
    if not c_dir or not c_dir.is_dir():
        return []
    files = []
    if (c_dir / "vector.yaml").is_file():
        files.append("vector.yaml")
    cfg_dir = c_dir / "config"
    if cfg_dir.is_dir():
        for f in sorted(cfg_dir.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                rel = str(f.relative_to(c_dir))
                if rel not in files:
                    files.append(rel)
    if (c_dir / "README.md").is_file() and "README.md" not in files:
        files.append("README.md")
    return files

def _get_collector_file_path(collector_id: str, rel_path: str) -> Optional[Path]:
    c_dir = COLLECTOR_DIRS.get(collector_id)
    if not c_dir or not c_dir.is_dir():
        return None
    if ".." in rel_path or rel_path.startswith("/") or "\\" in rel_path:
        return None
    target = (c_dir / rel_path).resolve()
    try:
        if not str(target).startswith(str(c_dir.resolve())):
            return None
    except Exception:
        return None
    return target



class ConfigServerHandler(BaseHTTPRequestHandler):
    server_version = "ULPF-ConfigServer/1.0"

    def __init__(self, *args, **kwargs):
        self.git_store: GitStore = kwargs.pop("git_store", None)
        self.active_dir: Path = kwargs.pop("active_dir", ACTIVE_DIR)
        super().__init__(*args, **kwargs)

    # Disable default BaseHTTPRequestHandler noisy log output; we use structured audit_logger
    def log_message(self, format, *args):
        pass

    # ──────────────────────────────────────────────────────────────────────────
    # Helper Utilities
    # ──────────────────────────────────────────────────────────────────────────

    def _client_ip(self) -> str:
        """Extract client IP, respecting X-Forwarded-For if behind a reverse proxy."""
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_PUT(self):
        self.do_POST()

    def _send_json(self, status_code: int, data: Any, extra_headers: Optional[Dict[str, str]] = None):
        """Send a JSON HTTP response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status_code: int, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Send a standardized error JSON response."""
        data = {
            "status": "error",
            "code": error_code,
            "message": message
        }
        if details:
            data["details"] = details
        self._send_json(status_code, data)

    def _read_body(self) -> Optional[bytes]:
        """Read request body while enforcing maximum payload size."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_CONTENT_LENGTH", "Invalid Content-Length header")
            return None

        if content_length > MAX_PAYLOAD_BYTES:
            self._send_error_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "PAYLOAD_TOO_LARGE", f"Payload exceeds {MAX_PAYLOAD_BYTES} bytes limit")
            return None

        return self.rfile.read(content_length)

    def _authenticate(self) -> bool:
        """Validate Bearer token or X-API-Key header with timing-safe comparison."""
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif not auth_header:
            token = self.headers.get("X-API-Key", "").strip()

        if not verify_token(token):
            log_audit(
                event="AUTH_FAILURE",
                client_ip=self._client_ip(),
                status="WARN",
                details={"path": self.path}
            )
            self._send_error_json(HTTPStatus.UNAUTHORIZED, "UNAUTHORIZED", "Missing or invalid authorization token")
            return False
        return True

    def _get_active_config_path(self, instance_id: str) -> Path:
        return self.active_dir / instance_id / "vector.yaml"

    def _get_active_sha(self, instance_id: str) -> Optional[str]:
        sha_file = self.active_dir / instance_id / ".commit_sha"
        if sha_file.exists():
            return sha_file.read_text(encoding="utf-8").strip()
        # Fall back to GitStore latest commit
        return self.git_store.get_current_commit(instance_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Request Routing
    # ──────────────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # 1. Public Health Check
        if path in ("/health", ""):
            uptime_s = round(time.time() - START_TIME, 1)
            self._send_json(HTTPStatus.OK, {
                "status": "healthy",
                "service": "ulpf-vector-config-server",
                "version": "1.0.0",
                "uptime_seconds": uptime_s,
                "vector_binary": VECTOR_BIN,
                "instances_count": len(self.git_store.list_instances())
            })
            return

        # Authentication Required for all /api/* routes
        if not self._authenticate():
            return

        # 2. List Instances
        if path == "/api/v1/instances":
            instances = []
            for inst in self.git_store.list_instances():
                sha = self._get_active_sha(inst)
                cfg_path = self._get_active_config_path(inst)
                mtime = cfg_path.stat().st_mtime if cfg_path.exists() else None
                mtime_iso = datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else None
                instances.append({
                    "instance_id": inst,
                    "active_commit_sha": sha,
                    "last_modified": mtime_iso,
                    "config_size_bytes": cfg_path.stat().st_size if cfg_path.exists() else 0
                })
            self._send_json(HTTPStatus.OK, {"instances": instances})
            return

        # 2b. Agents & Collectors Fleet Endpoint: GET /api/v1/agents or /api/v1/collectors
        if path in ("/api/v1/collectors", "/api/v1/agents"):
            self._send_json(HTTPStatus.OK, {"agents": AGENT_METADATA, "collectors": AGENT_METADATA})
            return

        # 2c. Agent/Collector Files List: GET /api/v1/agents/{id}/files or /collectors/{id}/files
        m = re.match(r"^/api/v1/(?:collectors|agents)/([a-zA-Z0-9_\-]+)/files$", path)
        if m:
            collector_id = m.group(1)
            files = _list_collector_files(collector_id)
            self._send_json(HTTPStatus.OK, {
                "agent_id": collector_id,
                "collector_id": collector_id,
                "files": files,
                "count": len(files)
            })
            return

        # 2d. Agent/Collector Single File Fetch: GET /api/v1/agents/{id}/file or /collectors/{id}/file
        m = re.match(r"^/api/v1/(?:collectors|agents)/([a-zA-Z0-9_\-]+)/file$", path)
        if m:
            collector_id = m.group(1)
            rel_path = query.get("path", ["vector.yaml"])[0]
            f_path = _get_collector_file_path(collector_id, rel_path)
            if not f_path or not f_path.is_file():
                self._send_error_json(HTTPStatus.NOT_FOUND, "FILE_NOT_FOUND", f"File '{rel_path}' not found for collector '{collector_id}'")
                return
            content = f_path.read_text(encoding="utf-8", errors="replace")
            self._send_json(HTTPStatus.OK, {
                "collector_id": collector_id,
                "path": rel_path,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "modified": datetime.fromtimestamp(f_path.stat().st_mtime, timezone.utc).isoformat()
            })
            return

        # 2e. Pipeline Health Endpoint: GET /api/v1/health or /api/health
        if path in ("/api/v1/health", "/api/health"):
            try:
                limit = int(query.get("limit", [1000])[0])
                req = urllib.request.Request(
                    "http://localhost:9200/ulpf-health/_search",
                    data=json.dumps({
                        "size": min(limit, 1000),
                        "sort": [{"minute": {"order": "desc", "unmapped_type": "long"}}],
                        "query": {"match_all": {}}
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                rows = [h["_source"] for h in data.get("hits", {}).get("hits", [])]
                self._send_json(HTTPStatus.OK, {
                    "rows": rows,
                    "count": len(rows),
                    "evidence": "verified on live stack",
                    "note": "Most recent indexed windows from ulpf-health."
                })
            except Exception as e:
                self._send_error_json(HTTPStatus.SERVICE_UNAVAILABLE, "HEALTH_UNAVAILABLE", str(e))
            return

        # 3. Audit Logs Endpoint
        if path == "/api/v1/audit/logs":
            limit = int(query.get("limit", [50])[0])
            logs = get_recent_audit_logs(limit=min(limit, 200))
            self._send_json(HTTPStatus.OK, {"logs": logs, "count": len(logs)})
            return

        # 4. Instance History: GET /api/v1/configs/{id}/history
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)/history$", path)
        if m:
            instance_id = m.group(1)
            limit = int(query.get("limit", [20])[0])
            history = self.git_store.get_history(instance_id, limit=limit)
            self._send_json(HTTPStatus.OK, {
                "instance_id": instance_id,
                "history": history,
                "count": len(history)
            })
            return

        # 5. Instance Diff: GET /api/v1/configs/{id}/diff?from=SHA1&to=SHA2
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)/diff$", path)
        if m:
            instance_id = m.group(1)
            commit_a = query.get("from", ["HEAD"])[0]
            commit_b = query.get("to", [None])[0]
            diff_text = self.git_store.get_diff(instance_id, commit_a, commit_b)
            self._send_json(HTTPStatus.OK, {
                "instance_id": instance_id,
                "from": commit_a,
                "to": commit_b,
                "diff": diff_text
            })
            return

        # 6. Fetch Active Config: GET /api/v1/configs/{id}
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)$", path)
        if m:
            instance_id = m.group(1)
            cfg_path = self._get_active_config_path(instance_id)

            if not cfg_path.is_file():
                self._send_error_json(
                    HTTPStatus.NOT_FOUND,
                    "CONFIG_NOT_FOUND",
                    f"No active configuration found for instance '{instance_id}'"
                )
                return

            active_sha = self._get_active_sha(instance_id) or "initial"
            etag = f'"{active_sha}"'

            # HTTP 304 Caching support for lightweight collector polling
            if_none_match = self.headers.get("If-None-Match")
            if if_none_match and if_none_match.strip() == etag:
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.send_header("ETag", etag)
                self.end_headers()
                return

            config_bytes = cfg_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/x-yaml; charset=utf-8")
            self.send_header("Content-Length", str(len(config_bytes)))
            self.send_header("ETag", etag)
            self.send_header("X-Config-Commit", active_sha)
            self.end_headers()
            self.wfile.write(config_bytes)

            log_audit(
                event="CONFIG_FETCH",
                client_ip=self._client_ip(),
                instance_id=instance_id,
                commit_sha=active_sha
            )
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "NOT_FOUND", f"Route not found: {path}")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if not self._authenticate():
            return

        # 1. Pre-deployment Validation Only: POST /api/v1/configs/{id}/validate
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)/validate$", path)
        if m:
            instance_id = m.group(1)
            raw_body = self._read_body()
            if raw_body is None:
                return

            content = self._parse_config_payload(raw_body)
            if content is None:
                return

            val_res = validate_vector_config(content, instance_id=instance_id)
            status_code = HTTPStatus.OK if val_res.valid else HTTPStatus.UNPROCESSABLE_ENTITY

            log_audit(
                event="CONFIG_VALIDATE_TEST",
                client_ip=self._client_ip(),
                instance_id=instance_id,
                status="PASS" if val_res.valid else "FAIL",
                duration_ms=val_res.duration_ms,
                details={"exit_code": val_res.exit_code, "error": val_res.error or val_res.output}
            )

            self._send_json(status_code, {
                "valid": val_res.valid,
                "instance_id": instance_id,
                "exit_code": val_res.exit_code,
                "output": val_res.output,
                "error": val_res.error,
                "duration_ms": round(val_res.duration_ms, 2)
            })
            return

        # 1b. Agent/Collector Validation: POST /api/v1/agents/{id}/validate or /collectors/{id}/validate
        m = re.match(r"^/api/v1/(?:collectors|agents)/([a-zA-Z0-9_\-]+)/validate$", path)
        if m:
            collector_id = m.group(1)
            raw_body = self._read_body()
            if raw_body is None:
                return
            content = None
            rel_path = "vector.yaml"
            try:
                body_json = json.loads(raw_body.decode("utf-8"))
                if isinstance(body_json, dict):
                    content = body_json.get("content") or body_json.get("config")
                    rel_path = body_json.get("path", rel_path)
                elif isinstance(body_json, str):
                    content = body_json
            except Exception:
                pass
            if content is None:
                content = self._parse_config_payload(raw_body)
            if content is None:
                return

            if rel_path == "vector.yaml" or rel_path.endswith("/vector.yaml"):
                val_res = validate_vector_config(content, instance_id=collector_id)
            else:
                val_res = validate_partial_vector_config(content, rel_path=rel_path, instance_id=collector_id)

            status_code = HTTPStatus.OK if val_res.valid else HTTPStatus.UNPROCESSABLE_ENTITY
            self._send_json(status_code, {
                "valid": val_res.valid,
                "agent_id": collector_id,
                "collector_id": collector_id,
                "exit_code": val_res.exit_code,
                "output": val_res.output,
                "error": val_res.error,
                "duration_ms": round(val_res.duration_ms, 2)
            })
            return

        # 1c. Agent/Collector Save File: POST /api/v1/agents/{id}/file or /collectors/{id}/file
        m = re.match(r"^/api/v1/(?:collectors|agents)/([a-zA-Z0-9_\-]+)/file$", path)
        if m:
            collector_id = m.group(1)
            raw_body = self._read_body()
            if raw_body is None:
                return
            parsed_q = parse_qs(parsed.query)
            rel_path = parsed_q.get("path", [None])[0]
            content = ""
            author = "Operator <operator@ulpf.local>"
            message = "Dashboard file update"

            try:
                body_json = json.loads(raw_body.decode("utf-8"))
                if isinstance(body_json, dict):
                    rel_path = body_json.get("path", rel_path)
                    content = body_json.get("content", "")
                    author = body_json.get("author", author)
                    message = body_json.get("message", message)
                else:
                    content = raw_body.decode("utf-8")
            except Exception:
                content = raw_body.decode("utf-8", errors="replace")

            if not rel_path:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "MISSING_PATH", "Path parameter required")
                return

            f_path = _get_collector_file_path(collector_id, rel_path)
            if not f_path:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_PATH", f"Invalid path '{rel_path}'")
                return

            val_res = None
            if rel_path == "vector.yaml" or rel_path.endswith("/vector.yaml"):
                val_res = validate_vector_config(content, instance_id=collector_id)
                if not val_res.valid:
                    self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                        "status": "error",
                        "phase": "validation",
                        "message": "Vector validate rejected configuration. Existing file preserved.",
                        "error": val_res.error or val_res.output,
                        "duration_ms": round(val_res.duration_ms, 2)
                    })
                    return
            elif rel_path.endswith(".yaml") or rel_path.endswith(".yml"):
                val_res = validate_partial_vector_config(content, rel_path=rel_path, instance_id=collector_id)
                if not val_res.valid:
                    self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                        "status": "error",
                        "phase": "validation",
                        "message": f"Validation failed for '{rel_path}'. Existing file preserved.",
                        "error": val_res.error or val_res.output,
                        "duration_ms": round(val_res.duration_ms, 2)
                    })
                    return

            f_path.parent.mkdir(parents=True, exist_ok=True)
            f_path.write_text(content, encoding="utf-8")

            # Commit to Git
            sha = self.git_store.commit_config(collector_id, content, author=author, message=f"[{rel_path}] {message}")

            self._send_json(HTTPStatus.OK, {
                "status": "success",
                "message": f"Successfully updated '{rel_path}'",
                "collector_id": collector_id,
                "path": rel_path,
                "commit_sha": sha,
                "validation": {
                    "valid": val_res.valid if val_res else True,
                    "output": val_res.output if val_res else "",
                    "duration_ms": round(val_res.duration_ms, 2) if val_res else 0
                } if val_res else None
            })
            return

        # 2. Rollback to Commit: POST /api/v1/configs/{id}/rollback
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)/rollback$", path)
        if m:
            instance_id = m.group(1)
            raw_body = self._read_body()
            if raw_body is None:
                return

            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "Rollback payload must be JSON")
                return

            target_sha = payload.get("commit_sha")
            if not target_sha:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "MISSING_COMMIT_SHA", "Field 'commit_sha' is required")
                return

            hist_content = self.git_store.get_commit_content(instance_id, target_sha)
            if hist_content is None:
                self._send_error_json(
                    HTTPStatus.NOT_FOUND,
                    "COMMIT_NOT_FOUND",
                    f"Commit '{target_sha}' not found for instance '{instance_id}'"
                )
                return

            # Safety Gate: Validate historical content before re-deploying
            val_res = validate_vector_config(hist_content, instance_id=instance_id)
            if not val_res.valid:
                log_audit(
                    event="ROLLBACK_REJECTED",
                    client_ip=self._client_ip(),
                    instance_id=instance_id,
                    status="FAIL",
                    commit_sha=target_sha,
                    details={"message": "Historical config failed current vector validation", "error": val_res.error}
                )
                self._send_error_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "ROLLBACK_VALIDATION_FAILED",
                    f"Historical commit {target_sha} failed validation and cannot be deployed.",
                    {"error": val_res.error or val_res.output}
                )
                return

            # Commit the rollback action to Git as a new explicit commit
            author = payload.get("author", f"Operator <operator@{self._client_ip()}>")
            msg = payload.get("message", f"Rollback to commit {target_sha[:8]}")
            new_sha = self.git_store.commit_config(instance_id, hist_content, author=author, message=msg)

            # Atomic Deployment to active folder
            self._deploy_active_file(instance_id, hist_content, new_sha)

            log_audit(
                event="ROLLBACK_SUCCESS",
                client_ip=self._client_ip(),
                instance_id=instance_id,
                status="SUCCESS",
                commit_sha=new_sha,
                details={"rolled_back_to": target_sha}
            )

            self._send_json(HTTPStatus.OK, {
                "status": "success",
                "message": f"Successfully rolled back {instance_id} to commit {target_sha[:8]}",
                "instance_id": instance_id,
                "rolled_back_to_sha": target_sha,
                "new_commit_sha": new_sha
            })
            return

        # 3. Deploy New Config: POST /api/v1/configs/{id}
        m = re.match(r"^/api/v1/configs/([a-zA-Z0-9_\-]+)$", path)
        if m:
            instance_id = m.group(1)
            raw_body = self._read_body()
            if raw_body is None:
                return

            content, author, message = self._extract_deploy_metadata(raw_body)
            if content is None:
                return

            # ── PHASE 1: Pre-Deployment Validation Gate ────────────────────────
            val_res = validate_vector_config(content, instance_id=instance_id)

            if not val_res.valid:
                # Validation Failed: Zero Disruption Guarantee
                # The active configuration is NEVER touched. The old version keeps running.
                current_sha = self._get_active_sha(instance_id)
                log_audit(
                    event="VALIDATION_FAILED",
                    client_ip=self._client_ip(),
                    instance_id=instance_id,
                    status="FAIL",
                    commit_sha=current_sha,
                    duration_ms=val_res.duration_ms,
                    details={
                        "message": "vector validate failed; existing active config preserved untouched",
                        "error": val_res.error or val_res.output
                    }
                )

                self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                    "status": "error",
                    "phase": "validation",
                    "message": "Validation failed: configuration rejected. Existing running configuration remains active.",
                    "instance_id": instance_id,
                    "active_commit_sha": current_sha,
                    "exit_code": val_res.exit_code,
                    "output": val_res.output,
                    "error": val_res.error,
                    "duration_ms": round(val_res.duration_ms, 2)
                })
                return

            # ── PHASE 2: Git Versioning Commit ────────────────────────────────
            log_audit(
                event="VALIDATION_PASSED",
                client_ip=self._client_ip(),
                instance_id=instance_id,
                status="PASS",
                duration_ms=val_res.duration_ms
            )

            new_sha = self.git_store.commit_config(
                instance_id=instance_id,
                content=content,
                author=author,
                message=message
            )

            # ── PHASE 3: Atomic Deployment to Active Store ─────────────────────
            self._deploy_active_file(instance_id, content, new_sha)

            log_audit(
                event="DEPLOY_SUCCESS",
                client_ip=self._client_ip(),
                instance_id=instance_id,
                status="SUCCESS",
                commit_sha=new_sha,
                duration_ms=val_res.duration_ms,
                details={"message": message, "author": author}
            )

            self._send_json(HTTPStatus.OK, {
                "status": "success",
                "phase": "deployed",
                "message": "Configuration validated and deployed successfully.",
                "instance_id": instance_id,
                "commit_sha": new_sha,
                "validation_duration_ms": round(val_res.duration_ms, 2)
            })
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "NOT_FOUND", f"Route not found: {path}")

    # ──────────────────────────────────────────────────────────────────────────
    # Deployment Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_config_payload(self, raw_bytes: bytes) -> Optional[str]:
        """Extract config text from either raw YAML or JSON wrapper."""
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                data = json.loads(raw_bytes.decode("utf-8"))
                if isinstance(data, dict):
                    if "content" in data:
                        return data["content"]
                    if "config" in data:
                        return data["config"]
                    return ""
                return str(data)
            except Exception:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "Payload is not valid JSON")
                return None
        # Default: raw YAML / plain text
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_ENCODING", "Payload must be UTF-8 encoded text")
            return None

    def _extract_deploy_metadata(self, raw_bytes: bytes) -> Tuple[Optional[str], str, str]:
        """Extract config content, author, and commit message from request."""
        content_type = self.headers.get("Content-Type", "")
        default_author = f"Operator <operator@{self._client_ip()}>"
        default_msg = "Deploy configuration update via HTTP API"

        if "application/json" in content_type:
            try:
                data = json.loads(raw_bytes.decode("utf-8"))
                cfg = data.get("content") or data.get("config")
                if not cfg:
                    self._send_error_json(HTTPStatus.BAD_REQUEST, "MISSING_CONFIG", "Field 'content' or 'config' required in JSON body")
                    return None, "", ""
                author = data.get("author") or default_author
                msg = data.get("message") or default_msg
                return cfg, author, msg
            except Exception:
                self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "Payload is not valid JSON")
                return None, "", ""

        # Raw YAML body
        try:
            cfg = raw_bytes.decode("utf-8")
            author = self.headers.get("X-Author") or default_author
            msg = self.headers.get("X-Commit-Message") or default_msg
            return cfg, author, msg
        except UnicodeDecodeError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "INVALID_ENCODING", "Payload must be UTF-8 encoded text")
            return None, "", ""

    def _deploy_active_file(self, instance_id: str, content: str, commit_sha: str):
        """
        Atomically write configuration to the active directory using POSIX rename.
        Guarantees that readers/watchers never observe partial or corrupted files.
        """
        inst_dir = self.active_dir / instance_id
        inst_dir.mkdir(parents=True, exist_ok=True)

        target_file = inst_dir / "vector.yaml"
        tmp_file = inst_dir / f"vector.yaml.tmp_{os.getpid()}"

        # Write to temporary file first
        tmp_file.write_text(content, encoding="utf-8")
        # Atomic replace
        tmp_file.replace(target_file)

        # Record commit sha in .commit_sha
        sha_file = inst_dir / ".commit_sha"
        sha_file.write_text(commit_sha, encoding="utf-8")


def create_server(host: str = HOST, port: int = PORT, repo_dir: Path = REPO_DIR, active_dir: Path = ACTIVE_DIR) -> HTTPServer:
    """Create and configure the ThreadingHTTPServer instance."""
    ensure_directories()
    git_store = GitStore(repo_dir=repo_dir)

    def handler_factory(*args, **kwargs):
        return ConfigServerHandler(*args, git_store=git_store, active_dir=active_dir, **kwargs)

    server = ThreadingHTTPServer((host, port), handler_factory)
    return server


def main():
    parser = argparse.ArgumentParser(description="ULPF Vector Configuration Management Server")
    parser.add_argument("--host", default=HOST, help=f"Host address to bind (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    parser.add_argument("--repo-dir", default=str(REPO_DIR), help="Path to config git repository")
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port, repo_dir=Path(args.repo_dir))
    logger.info(f"ULPF Vector Config Server listening on http://{args.host}:{args.port}")
    logger.info(f"Git Repository Path: {args.repo_dir}")
    logger.info(f"Vector Binary: {VECTOR_BIN}")
    logger.info(f"Security: Bearer token authentication ENABLED (Token: {API_TOKEN[:6]}...{API_TOKEN[-4:]})")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down configuration server...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
