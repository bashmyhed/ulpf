"""
ULPF Pre-Deployment Configuration Validator
Uses Vector's native `vector validate` engine to verify syntax, VRL logic, and topology.
"""
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import NamedTuple, Optional, Dict

from config import STAGING_DIR, VECTOR_BIN, DEFAULT_VALIDATE_ENV
from audit_logger import logger


class ValidationResult(NamedTuple):
    valid: bool
    output: str
    error: str
    duration_ms: float
    exit_code: int


def validate_vector_config(
    content: str,
    instance_id: str = "staging",
    custom_env: Optional[Dict[str, str]] = None,
    timeout_sec: float = 15.0
) -> ValidationResult:
    """
    Validates a proposed Vector configuration string using `vector validate --no-environment`.
    
    1. Writes configuration to an isolated staging file.
    2. Runs vector validate with mock/standard environment variables.
    3. Guarantees staging file cleanup.
    4. Returns a ValidationResult with pass/fail and detailed error diagnostics.
    """
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    stage_id = uuid.uuid4().hex[:10]
    stage_file = STAGING_DIR / f"{instance_id}_{stage_id}.yaml"
    
    # Merge environment variables
    env = os.environ.copy()
    env.update(DEFAULT_VALIDATE_ENV)
    if custom_env:
        env.update(custom_env)

    start_time = time.perf_counter()
    try:
        stage_file.write_text(content, encoding="utf-8")
        
        cmd = [VECTOR_BIN, "validate", "--no-environment", str(stage_file)]
        
        res = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        
        is_valid = (res.returncode == 0)
        
        output = res.stdout.strip()
        error = res.stderr.strip()
        
        # If output or error contains the temporary staging file name, sanitize it for clarity
        stage_str = str(stage_file)
        if stage_str in output:
            output = output.replace(stage_str, f"{instance_id}/vector.yaml")
        if stage_str in error:
            error = error.replace(stage_str, f"{instance_id}/vector.yaml")

        return ValidationResult(
            valid=is_valid,
            output=output,
            error=error,
            duration_ms=duration_ms,
            exit_code=res.returncode
        )

    except subprocess.TimeoutExpired:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return ValidationResult(
            valid=False,
            output="",
            error=f"Validation timed out after {timeout_sec}s",
            duration_ms=duration_ms,
            exit_code=124
        )
    except FileNotFoundError:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return ValidationResult(
            valid=False,
            output="",
            error=f"Vector binary not found at '{VECTOR_BIN}'. Ensure Vector is installed.",
            duration_ms=duration_ms,
            exit_code=127
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return ValidationResult(
            valid=False,
            output="",
            error=f"Internal validation execution error: {str(e)}",
            duration_ms=duration_ms,
            exit_code=1
        )
    finally:
        # Guarantee cleanup of temporary staging file
        try:
            if stage_file.exists():
                stage_file.unlink()
        except Exception as e:
            logger.warning(f"Could not remove staging file {stage_file}: {e}")


def validate_partial_vector_config(
    content: str,
    rel_path: str,
    instance_id: str = "staging",
    custom_env: Optional[Dict[str, str]] = None,
    timeout_sec: float = 15.0
) -> ValidationResult:
    """
    Validates a partial Vector configuration file (e.g. config/transforms/*.yaml,
    sources.yaml, sinks.yaml, env.yaml, or markdown).
    """
    import yaml

    start_time = time.perf_counter()
    if rel_path.endswith(".md"):
        return ValidationResult(
            valid=True,
            output=f"Markdown documentation file '{rel_path}' is valid.",
            error="",
            duration_ms=(time.perf_counter() - start_time) * 1000.0,
            exit_code=0
        )

    try:
        data = yaml.safe_load(content)
    except Exception as ye:
        return ValidationResult(
            valid=False,
            output="",
            error=f"YAML syntax error in '{rel_path}': {str(ye)}",
            duration_ms=(time.perf_counter() - start_time) * 1000.0,
            exit_code=1
        )

    if not isinstance(data, dict):
        if rel_path.endswith("env.yaml") or rel_path.endswith(".env"):
            return ValidationResult(
                valid=True,
                output=f"Environment specification in '{rel_path}' loaded.",
                error="",
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
                exit_code=0
            )
        return ValidationResult(
            valid=False,
            output="",
            error=f"Configuration in '{rel_path}' must be a YAML mapping/dictionary.",
            duration_ms=(time.perf_counter() - start_time) * 1000.0,
            exit_code=1
        )

    # If it's already a full config with sources and sinks, run full validator
    if "sources" in data and "sinks" in data:
        return validate_vector_config(content, instance_id=instance_id, custom_env=custom_env, timeout_sec=timeout_sec)

    # If it defines transforms, wrap with mock source and mock sink to validate VRL and syntax
    if "transforms" in data:
        mock_doc = {
            "sources": {
                "_validation_src": {
                    "type": "demo_logs",
                    "format": "json"
                }
            },
            "transforms": {},
            "sinks": {
                "_validation_sink": {
                    "type": "blackhole",
                    "inputs": []
                }
            }
        }
        for t_name, t_body in data["transforms"].items():
            if isinstance(t_body, dict):
                t_copy = dict(t_body)
                inputs = t_copy.get("inputs", [])
                if isinstance(inputs, list):
                    mapped_inputs = []
                    for inp in inputs:
                        if inp in data["transforms"]:
                            mapped_inputs.append(inp)
                        else:
                            mapped_inputs.append("_validation_src")
                    t_copy["inputs"] = mapped_inputs if mapped_inputs else ["_validation_src"]
                else:
                    t_copy["inputs"] = ["_validation_src"]
                mock_doc["transforms"][t_name] = t_copy
                mock_doc["sinks"]["_validation_sink"]["inputs"].append(t_name)

        wrapped_yaml = yaml.dump(mock_doc)
        res = validate_vector_config(wrapped_yaml, instance_id=instance_id, custom_env=custom_env, timeout_sec=timeout_sec)
        clean_out = res.output.replace("_validation_src", "").replace("_validation_sink", "").strip()
        clean_err = res.error.replace("_validation_src", "").replace("_validation_sink", "").strip()
        return ValidationResult(
            valid=res.valid,
            output=clean_out or f"Transform logic and VRL in '{rel_path}' validated successfully.",
            error=clean_err,
            duration_ms=res.duration_ms,
            exit_code=res.exit_code
        )

    # If it defines sources, wrap with blackhole sink
    if "sources" in data:
        mock_doc = {
            "sources": data["sources"],
            "sinks": {
                "_validation_sink": {
                    "type": "blackhole",
                    "inputs": list(data["sources"].keys())
                }
            }
        }
        wrapped_yaml = yaml.dump(mock_doc)
        res = validate_vector_config(wrapped_yaml, instance_id=instance_id, custom_env=custom_env, timeout_sec=timeout_sec)
        return ValidationResult(
            valid=res.valid,
            output=res.output or f"Sources in '{rel_path}' validated successfully.",
            error=res.error,
            duration_ms=res.duration_ms,
            exit_code=res.exit_code
        )

    # If it defines sinks, wrap with mock source
    if "sinks" in data:
        mock_doc = {
            "sources": {
                "_validation_src": {
                    "type": "demo_logs",
                    "format": "json"
                }
            },
            "sinks": {}
        }
        for s_name, s_body in data["sinks"].items():
            if isinstance(s_body, dict):
                s_copy = dict(s_body)
                s_copy["inputs"] = ["_validation_src"]
                mock_doc["sinks"][s_name] = s_copy
        wrapped_yaml = yaml.dump(mock_doc)
        res = validate_vector_config(wrapped_yaml, instance_id=instance_id, custom_env=custom_env, timeout_sec=timeout_sec)
        return ValidationResult(
            valid=res.valid,
            output=res.output or f"Sinks in '{rel_path}' validated successfully.",
            error=res.error,
            duration_ms=res.duration_ms,
            exit_code=res.exit_code
        )

    # General YAML configuration (e.g. env.yaml, custom metadata)
    return ValidationResult(
        valid=True,
        output=f"Configuration in '{rel_path}' parsed as valid YAML.",
        error="",
        duration_ms=(time.perf_counter() - start_time) * 1000.0,
        exit_code=0
    )
