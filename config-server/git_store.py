"""
ULPF Git Versioning Engine for Vector Configurations
Maintains an immutable Git repository for all collector and central configurations.
"""
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

from config import REPO_DIR
from audit_logger import logger


class GitStore:
    def __init__(self, repo_dir: Path = REPO_DIR):
        self.repo_dir = Path(repo_dir).resolve()
        self.instances_dir = self.repo_dir / "instances"
        self._ensure_repo()

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Helper to run a git command in the repository directory."""
        cmd = ["git", "-C", str(self.repo_dir)] + list(args)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\nStderr: {res.stderr}\nStdout: {res.stdout}")
        return res

    def _ensure_repo(self):
        """Initialize the git repository if not already initialized."""
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self.instances_dir.mkdir(parents=True, exist_ok=True)

        git_dir = self.repo_dir / ".git"
        if not git_dir.exists():
            logger.info(f"Initializing new Git config repository at {self.repo_dir}")
            subprocess.run(["git", "init", str(self.repo_dir)], check=True, capture_output=True)
            self._run_git("config", "user.name", "ULPF Config Manager")
            self._run_git("config", "user.email", "ulpf-admin@ntro.gov.in")
            
            # Initial commit
            readme = self.repo_dir / "README.md"
            if not readme.exists():
                readme.write_text("# ULPF Vector Configuration Repository\nManaged automatically by ULPF Config Server.\n", encoding="utf-8")
                self._run_git("add", "README.md")
                self._run_git("commit", "-m", "Initial commit: repository created")

    def commit_config(
        self,
        instance_id: str,
        content: str,
        author: str = "Admin <admin@ulpf.local>",
        message: str = "Update configuration"
    ) -> str:
        """
        Write configuration for instance_id and commit it to git.
        Returns the new commit SHA (or current commit SHA if content didn't change).
        """
        inst_dir = self.instances_dir / instance_id
        inst_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = inst_dir / "vector.yaml"

        # Check existing content
        old_content = cfg_file.read_text(encoding="utf-8") if cfg_file.exists() else None
        if old_content == content:
            # No changes
            res = self._run_git("log", "-n", "1", "--pretty=format:%H", "--", f"instances/{instance_id}/vector.yaml", check=False)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()

        # Write new content
        cfg_file.write_text(content, encoding="utf-8")
        rel_path = f"instances/{instance_id}/vector.yaml"

        self._run_git("add", rel_path)
        
        # Check if there is anything staged to commit
        diff_res = self._run_git("diff", "--cached", "--quiet", check=False)
        if diff_res.returncode == 0:
            # Nothing changed
            res = self._run_git("rev-parse", "HEAD")
            return res.stdout.strip()

        # Format commit author
        if "<" not in author or ">" not in author:
            clean_author = f"{author} <{author.lower().replace(' ', '_')}@ulpf.local>"
        else:
            clean_author = author

        commit_msg = f"[{instance_id}] {message}"
        self._run_git("commit", "-m", commit_msg, f"--author={clean_author}")
        
        # Return new commit SHA
        sha_res = self._run_git("rev-parse", "HEAD")
        return sha_res.stdout.strip()

    def get_current_commit(self, instance_id: str) -> Optional[str]:
        """Get the latest commit SHA for a specific instance."""
        rel_path = f"instances/{instance_id}/vector.yaml"
        res = self._run_git("log", "-n", "1", "--pretty=format:%H", "--", rel_path, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return None

    def get_commit_content(self, instance_id: str, commit_sha: str) -> Optional[str]:
        """Retrieve the content of instance configuration at a specific commit SHA."""
        rel_path = f"instances/{instance_id}/vector.yaml"
        res = self._run_git("show", f"{commit_sha}:{rel_path}", check=False)
        if res.returncode == 0:
            return res.stdout
        return None

    def get_history(self, instance_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve commit history for a specific instance."""
        rel_path = f"instances/{instance_id}/vector.yaml"
        fmt = "%H%x09%an%x09%ae%x09%at%x09%s"
        res = self._run_git("log", f"-n{limit}", f"--pretty=format:{fmt}", "--", rel_path, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return []

        history = []
        for line in res.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 5:
                commit_sha, author_name, author_email, epoch_ts, msg = parts[0], parts[1], parts[2], parts[3], parts[4]
                try:
                    iso_time = datetime.fromtimestamp(int(epoch_ts), timezone.utc).isoformat()
                except Exception:
                    iso_time = ""
                history.append({
                    "commit_sha": commit_sha,
                    "author": f"{author_name} <{author_email}>",
                    "timestamp": iso_time,
                    "epoch": int(epoch_ts),
                    "message": msg
                })
        return history

    def get_diff(self, instance_id: str, commit_a: str, commit_b: Optional[str] = None) -> str:
        """Get git diff for an instance between two commits or commit and working tree."""
        rel_path = f"instances/{instance_id}/vector.yaml"
        if commit_b:
            res = self._run_git("diff", f"{commit_a}..{commit_b}", "--", rel_path, check=False)
        else:
            res = self._run_git("diff", commit_a, "--", rel_path, check=False)
        return res.stdout

    def list_instances(self) -> List[str]:
        """List all instances that have directories in repo/instances."""
        if not self.instances_dir.exists():
            return []
        return sorted([
            d.name for d in self.instances_dir.iterdir()
            if d.is_dir() and (d / "vector.yaml").exists()
        ])
