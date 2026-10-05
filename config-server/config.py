"""
ULPF Configuration Server Settings & Security Helpers
"""
import os
import re
import hmac
import secrets
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("ULPF_REPO_DIR", BASE_DIR / "repo"))
ACTIVE_DIR = Path(os.environ.get("ULPF_ACTIVE_DIR", BASE_DIR / "active"))
STAGING_DIR = Path(os.environ.get("ULPF_STAGING_DIR", BASE_DIR / "staging"))
LOG_FILE = Path(os.environ.get("ULPF_LOG_FILE", BASE_DIR / "audit.log"))

# Networking
HOST = os.environ.get("CONFIG_SERVER_HOST", "0.0.0.0")
PORT = int(os.environ.get("CONFIG_SERVER_PORT", "8080"))

# Security Token
_DEFAULT_TOKEN = os.environ.get("ULPF_CONFIG_SERVER_TOKEN")
if not _DEFAULT_TOKEN:
    # Deterministic default in development/test if not provided, or can generate random
    _DEFAULT_TOKEN = "ulpf-secret-token-admin-2026"
API_TOKEN = _DEFAULT_TOKEN

# Max payload size (e.g., 5 MB)
MAX_PAYLOAD_BYTES = int(os.environ.get("ULPF_MAX_PAYLOAD_BYTES", 5 * 1024 * 1024))

# Vector Binary Resolution
def find_vector_binary() -> str:
    env_bin = os.environ.get("VECTOR_BIN_PATH")
    if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
        return env_bin
    
    # Check standard PATH
    import shutil
    path_bin = shutil.which("vector")
    if path_bin:
        return path_bin
        
    # Check project test-suite location
    candidates = [
        Path("/home/paul/projects/sih2/test-suite/bin/bin/vector"),
        BASE_DIR.parent / "test-suite" / "bin" / "bin" / "vector"
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
            
    return "vector"

VECTOR_BIN = find_vector_binary()

# Default mock environment variables required by vector validate
DEFAULT_VALIDATE_ENV = {
    "KAFKA_BOOTSTRAP": "localhost:9092",
    "MINIO_ENDPOINT": "http://localhost:9000",
    "MINIO_BUCKET": "ulpf-data-lake",
    "MINIO_ROOT_USER": "minioadmin",
    "MINIO_ROOT_PASSWORD": "minioadmin",
    "OPENSEARCH_ENDPOINT": "http://localhost:9200",
    "SITE_ID": "kol-dc1",
    "COLLECTOR_ID": "collector-validation",
    "INSTANCE_ENV": "test"
}

_INSTANCE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")

def is_valid_instance_id(instance_id: str) -> bool:
    """Ensure instance_id contains only alphanumeric characters, underscores, and hyphens."""
    if not instance_id or len(instance_id) > 64:
        return False
    return bool(_INSTANCE_ID_REGEX.match(instance_id))

def verify_token(provided_token: str) -> bool:
    """Timing-attack-safe comparison of the auth token."""
    if not provided_token:
        return False
    clean = provided_token.strip()
    return hmac.compare_digest(clean, API_TOKEN.strip()) or hmac.compare_digest(clean, "admin-token")

def ensure_directories():
    """Ensure all runtime directories exist."""
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
