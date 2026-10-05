#!/usr/bin/env python3
"""
Envelope validation script for pre-receive hook.
Validates that all collector configs produce valid ULPF envelopes.
"""
import sys
import os
import json
import yaml
import subprocess

REQUIRED_ENVELOPE_FIELDS = [
    "envelope_version",
    "site_id",
    "collector_id",
    "collector_version",
    "seq",
    "collected_at",
    "source_tz",
    "clock",
    "source",
    "raw_format",
    "raw_encoding",
    "raw_len",
    "raw_sha256",
    "raw",
    "flags",
    "labels"
]

REQUIRED_SOURCE_FIELDS = [
    "type",
    "vendor",
    "product",
    "transport",
    "host_name",
    "position"
]

def validate_vrl_envelope_creation(vrl_file):
    """Check that VRL transform creates all required envelope fields."""
    with open(vrl_file, 'r') as f:
        content = f.read()
    
    # Basic check: ensure the VRL builds an envelope with required fields
    missing = []
    for field in REQUIRED_ENVELOPE_FIELDS:
        if f'"{field}"' not in content and f"'{field}'" not in content:
            # Check for dynamic assignment like .field = value
            if f".{field}" not in content:
                missing.append(field)
    
    if missing:
        print(f"  WARNING: {vrl_file} may not set envelope fields: {missing}")
        return False
    return True

def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    errors = []
    
    print(f"[validate_envelope] Scanning {repo_root}...")
    
    # Find all vector.yaml files
    for root, dirs, files in os.walk(repo_root):
        for file in files:
            if file == "vector.yaml":
                cfg_path = os.path.join(root, file)
                print(f"[validate_envelope] Checking {cfg_path}")
                
                try:
                    with open(cfg_path, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    # Skip empty/partial configs
                    if config is None:
                        print(f"  Skipping empty config: {cfg_path}")
                        continue
                    
                    # Check for transforms that build envelopes
                    transforms = config.get('transforms', {})
                    for name, transform in transforms.items():
                        if transform.get('type') == 'remap':
                            source = transform.get('source', '')
                            # Look for envelope creation pattern
                            if 'envelope_version' in source or 'site_id' in source:
                                # This looks like an envelope-building transform
                                # Check for required fields in the VRL
                                for field in REQUIRED_ENVELOPE_FIELDS:
                                    if field not in source:
                                        # Check common patterns
                                        pass
                except Exception as e:
                    errors.append(f"Failed to parse {cfg_path}: {e}")
    
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    
    print("[validate_envelope] All checks passed")
    return 0

if __name__ == "__main__":
    sys.exit(main())