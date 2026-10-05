"""
ULPF Structured Audit Logger
Records all configuration changes, validation results, deployment attempts, and authentication events.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from config import LOG_FILE

# Set up base logger
logger = logging.getLogger("ulpf.config_server")
logger.setLevel(logging.INFO)

# Formatter for console human-readable logs
console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [config-server] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(console_formatter)
if not logger.handlers:
    logger.addHandler(console_handler)

# File handler for structured audit logs
try:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except Exception as e:
    sys.stderr.write(f"Warning: could not open audit log file {LOG_FILE}: {e}\n")


def log_audit(
    event: str,
    client_ip: str = "local",
    instance_id: Optional[str] = None,
    status: str = "INFO",
    details: Optional[Dict[str, Any]] = None,
    commit_sha: Optional[str] = None,
    duration_ms: Optional[float] = None
):
    """
    Record an immutable structured audit log entry.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "status": status,
        "client_ip": client_ip,
        "instance_id": instance_id or "system",
    }
    if commit_sha:
        entry["commit_sha"] = commit_sha
    if duration_ms is not None:
        entry["duration_ms"] = round(duration_ms, 2)
    if details:
        entry["details"] = details

    # Write as single-line JSON to audit log file / stream
    json_str = json.dumps(entry)
    
    # Also log human-readable message to console
    msg_parts = [f"EVENT={event}", f"STATUS={status}", f"IP={client_ip}"]
    if instance_id:
        msg_parts.append(f"INSTANCE={instance_id}")
    if commit_sha:
        msg_parts.append(f"COMMIT={commit_sha[:8]}")
    if duration_ms is not None:
        msg_parts.append(f"DURATION={duration_ms:.1f}ms")
    if details and "message" in details:
        msg_parts.append(f"MSG={details['message']}")
    
    log_line = " | ".join(msg_parts)
    if status in ("ERROR", "FAIL"):
        logger.error(log_line)
    elif status == "WARN":
        logger.warning(log_line)
    else:
        logger.info(log_line)


def get_recent_audit_logs(limit: int = 50) -> list:
    """Retrieve the most recent audit log records from the log file."""
    if not LOG_FILE.is_file():
        return []
    lines = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return lines[-limit:]
    except Exception as e:
        logger.error(f"Error reading audit log: {e}")
        return []
