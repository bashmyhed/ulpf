"""
Automated Test Suite for ULPF Vector Configuration Server
Tests:
- Authentication & Timing-Safe Security
- Pre-Deployment Validation (Pass & Fail)
- Zero-Disruption Fallback Guarantee (Broken configs rejected, active config preserved)
- Git Versioning & Commit History
- ETag / HTTP 304 Polling
- Atomic Rollback Execution
- Path Sanitization
"""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path

# Add parent directory to path
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from server import create_server
from config import API_TOKEN

# Valid sample Vector configuration
VALID_CONFIG = """
sources:
  sample_in:
    type: demo_logs
    format: syslog
    interval: 1.0

sinks:
  sample_out:
    type: blackhole
    inputs:
      - sample_in
"""

VALID_CONFIG_V2 = """
sources:
  sample_in:
    type: demo_logs
    format: apache_common
    interval: 2.0

sinks:
  sample_out:
    type: blackhole
    inputs:
      - sample_in
"""

# Invalid Vector configuration (broken syntax & unresolvable DAG input)
INVALID_CONFIG = """
sources:
  broken_in:
    type: demo_logs
    format: invalid_format_xyz_123

sinks:
  broken_out:
    type: blackhole
    inputs:
      - nonexistent_source
"""


class TestConfigServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up isolated temporary directories for test run
        cls.test_dir = Path(tempfile.mkdtemp(prefix="ulpf_test_cfg_"))
        cls.repo_dir = cls.test_dir / "repo"
        cls.active_dir = cls.test_dir / "active"
        cls.staging_dir = cls.test_dir / "staging"
        cls.log_file = cls.test_dir / "audit.log"

        os.environ["ULPF_REPO_DIR"] = str(cls.repo_dir)
        os.environ["ULPF_ACTIVE_DIR"] = str(cls.active_dir)
        os.environ["ULPF_STAGING_DIR"] = str(cls.staging_dir)
        os.environ["ULPF_LOG_FILE"] = str(cls.log_file)

        # Reload config module to pick up temporary directories
        import config
        config.REPO_DIR = cls.repo_dir
        config.ACTIVE_DIR = cls.active_dir
        config.STAGING_DIR = cls.staging_dir
        config.LOG_FILE = cls.log_file

        # Start server on dynamic port
        cls.port = 18889
        cls.server = create_server(host="127.0.0.1", port=cls.port, repo_dir=cls.repo_dir, active_dir=cls.active_dir)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _req(
        self,
        method: str,
        path: str,
        data: bytes = None,
        headers: dict = None,
        token: str = API_TOKEN
    ):
        """Helper to issue HTTP requests with optional authentication."""
        req_headers = {}
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(self._url(path), data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
                return resp.status, resp.headers, body
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, e.headers, body

    # ──────────────────────────────────────────────────────────────────────────
    # Tests
    # ──────────────────────────────────────────────────────────────────────────

    def test_01_health_check_public(self):
        """Public health check should return 200 without authentication."""
        code, _, body = self._req("GET", "/health", token=None)
        self.assertEqual(code, 200)
        data = json.loads(body.decode())
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "ulpf-vector-config-server")

    def test_02_authentication_enforcement(self):
        """API endpoints must reject requests with missing or invalid tokens."""
        # Missing token
        code, _, body = self._req("GET", "/api/v1/instances", token=None)
        self.assertEqual(code, 401)
        data = json.loads(body.decode())
        self.assertEqual(data["code"], "UNAUTHORIZED")

        # Invalid token
        code, _, body = self._req("GET", "/api/v1/instances", token="invalid-token-xyz")
        self.assertEqual(code, 401)

    def test_03_dry_run_validation(self):
        """Dry-run validation endpoint tests Vector config without deploying."""
        # Valid config
        code, _, body = self._req(
            "POST",
            "/api/v1/configs/collector-test/validate",
            data=VALID_CONFIG.encode(),
            headers={"Content-Type": "application/x-yaml"}
        )
        self.assertEqual(code, 200)
        data = json.loads(body.decode())
        self.assertTrue(data["valid"])
        self.assertEqual(data["exit_code"], 0)

        # Invalid config
        code, _, body = self._req(
            "POST",
            "/api/v1/configs/collector-test/validate",
            data=INVALID_CONFIG.encode(),
            headers={"Content-Type": "application/x-yaml"}
        )
        self.assertEqual(code, 422)
        data = json.loads(body.decode())
        self.assertFalse(data["valid"])
        self.assertNotEqual(data["exit_code"], 0)

    def test_04_successful_deployment_and_git_commit(self):
        """Valid configuration must be committed to Git and deployed to active directory."""
        inst = "collector-alpha"
        code, _, body = self._req(
            "POST",
            f"/api/v1/configs/{inst}",
            data=VALID_CONFIG.encode(),
            headers={
                "Content-Type": "application/x-yaml",
                "X-Author": "Alice DevOps <alice@corp.local>",
                "X-Commit-Message": "Deploy initial valid syslog topology"
            }
        )
        self.assertEqual(code, 200)
        data = json.loads(body.decode())
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["phase"], "deployed")
        commit_sha = data["commit_sha"]
        self.assertTrue(len(commit_sha) >= 40)

        # Verify active file exists on disk
        active_file = self.active_dir / inst / "vector.yaml"
        self.assertTrue(active_file.exists())
        self.assertEqual(active_file.read_text().strip(), VALID_CONFIG.strip())

        # Verify GET /api/v1/configs/{inst} returns the active config
        code, headers, get_body = self._req("GET", f"/api/v1/configs/{inst}")
        self.assertEqual(code, 200)
        self.assertEqual(get_body.decode().strip(), VALID_CONFIG.strip())
        self.assertEqual(headers.get("ETag"), f'"{commit_sha}"')
        self.assertEqual(headers.get("X-Config-Commit"), commit_sha)

    def test_05_zero_disruption_fallback_guarantee(self):
        """
        CRITICAL REQUIREMENT:
        When an invalid configuration is submitted, it MUST be rejected,
        and the system MUST continue running on the old valid configuration.
        """
        inst = "collector-alpha"

        # 1. Fetch current active configuration and commit SHA
        code, _, original_body = self._req("GET", f"/api/v1/configs/{inst}")
        self.assertEqual(code, 200)
        original_config_text = original_body.decode()

        sha_file = self.active_dir / inst / ".commit_sha"
        original_sha = sha_file.read_text().strip()

        # 2. Attempt to deploy corrupted/invalid configuration
        code, _, error_body = self._req(
            "POST",
            f"/api/v1/configs/{inst}",
            data=INVALID_CONFIG.encode(),
            headers={
                "Content-Type": "application/x-yaml",
                "X-Commit-Message": "Attempt broken deploy"
            }
        )
        self.assertEqual(code, 422)
        err_data = json.loads(error_body.decode())
        self.assertEqual(err_data["status"], "error")
        self.assertEqual(err_data["phase"], "validation")
        self.assertIn("Validation failed", err_data["message"])

        # 3. VERIFY FALLBACK GUARANTEE: Active configuration is UNTOUCHED
        code, headers, current_body = self._req("GET", f"/api/v1/configs/{inst}")
        self.assertEqual(code, 200)
        self.assertEqual(current_body.decode(), original_config_text)
        self.assertEqual(headers.get("X-Config-Commit"), original_sha)

        active_disk_file = self.active_dir / inst / "vector.yaml"
        self.assertEqual(active_disk_file.read_text(), original_config_text)

    def test_06_etag_and_304_caching(self):
        """Collectors polling with If-None-Match should receive 304 Not Modified when unchanged."""
        inst = "collector-alpha"
        code, headers, _ = self._req("GET", f"/api/v1/configs/{inst}")
        etag = headers.get("ETag")

        # Request with matching ETag
        code, _, body = self._req(
            "GET",
            f"/api/v1/configs/{inst}",
            headers={"If-None-Match": etag}
        )
        self.assertEqual(code, 304)
        self.assertEqual(len(body), 0)

    def test_07_rollback_functionality(self):
        """Operators can roll back to any historical commit with pre-validation."""
        inst = "collector-beta"

        # Deploy V1
        code, _, body1 = self._req("POST", f"/api/v1/configs/{inst}", data=VALID_CONFIG.encode())
        self.assertEqual(code, 200)
        sha1 = json.loads(body1.decode())["commit_sha"]

        # Deploy V2
        code, _, body2 = self._req("POST", f"/api/v1/configs/{inst}", data=VALID_CONFIG_V2.encode())
        self.assertEqual(code, 200)
        sha2 = json.loads(body2.decode())["commit_sha"]
        self.assertNotEqual(sha1, sha2)

        # Verify active is now V2
        code, _, active_body = self._req("GET", f"/api/v1/configs/{inst}")
        self.assertIn("apache_common", active_body.decode())

        # Execute Rollback to sha1
        rollback_payload = json.dumps({"commit_sha": sha1, "message": "Revert to v1"}).encode()
        code, _, rb_body = self._req(
            "POST",
            f"/api/v1/configs/{inst}/rollback",
            data=rollback_payload,
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(code, 200)
        rb_data = json.loads(rb_body.decode())
        self.assertEqual(rb_data["status"], "success")

        # Verify active is now back to V1
        code, _, current_body = self._req("GET", f"/api/v1/configs/{inst}")
        self.assertIn("syslog", current_body.decode())
        self.assertNotIn("apache_common", current_body.decode())

    def test_08_git_history_and_diff(self):
        """Git history and diff endpoints return structured commit records."""
        inst = "collector-beta"
        code, _, body = self._req("GET", f"/api/v1/configs/{inst}/history")
        self.assertEqual(code, 200)
        data = json.loads(body.decode())
        self.assertGreaterEqual(len(data["history"]), 2)

        # Diff
        h = data["history"]
        sha_latest = h[0]["commit_sha"]
        sha_prev = h[1]["commit_sha"]
        code, _, diff_body = self._req("GET", f"/api/v1/configs/{inst}/diff?from={sha_prev}&to={sha_latest}")
        self.assertEqual(code, 200)
        diff_data = json.loads(diff_body.decode())
        self.assertIn("diff", diff_data)

    def test_09_security_path_traversal_prevention(self):
        """Attempts to traverse directories in instance_id must be rejected."""
        traversal_attempts = [
            "/api/v1/configs/..%2f..%2fetc%2fpasswd",
            "/api/v1/configs/foo/bar",
            "/api/v1/configs/!@#$%^"
        ]
        for path in traversal_attempts:
            code, _, _ = self._req("GET", path)
            self.assertIn(code, (400, 404))


if __name__ == "__main__":
    unittest.main()
