# ULPF `source.type` Registry

**Version:** 1.0  
**Spec base:** [metadataGuide.md](../metadataGuide.md) §5

This is the canonical registry of all `source.type` values used in this ULPF deployment.  
Collectors **must** use exactly these strings — no variants, no abbreviations.

---

## Registry Table

| `source.type` | Vendor | Product | Transport | `raw_format` | Collector | Emulator |
|---------------|--------|---------|-----------|-------------|-----------|---------|
| `fw.cisco.asa` | Cisco | ASA | file | `syslog3164` | collector-a | `cisco_asa_syslog.py` |
| `linux.auth` | Linux | PAM/sshd | file | `syslog3164` | collector-a | `linux_auth.py` |
| `fw.paloalto` | Palo Alto Networks | PAN-OS | file | `cef` | collector-a | `firewall_cef.py` |
| `siem.qradar` | IBM | QRadar | file | `leef` | collector-a | `leef_qradar.py` |
| `web.nginx.access` | nginx | nginx | file | `json` | collector-b | `nginx_access.py` |
| `cloud.aws.cloudtrail` | Amazon | CloudTrail | file | `json` | collector-b | `cloudtrail_json.py` |
| `k8s.audit` | CNCF | Kubernetes | file | `json` | collector-b | `k8s_audit.py` |
| `iot.sensor` | Generic | Sensor | file / mqtt | `json` | collector-b | `iot_sensor.py` |
| `db.postgres` | PostgreSQL Global Dev Group | PostgreSQL | file | `csv` | collector-b | `db_postgres.py` |
| `windows.security` | Microsoft | Windows | file | `evtx_xml` | collector-c | `windows_event.py` |
| `windows.sysmon` | Microsoft | Sysmon | file | `evtx_xml` | collector-c | `windows_event.py` |

---

## Naming Convention

```
<category>.<vendor_short>.<product_short>
```

| Level | Examples |
|-------|---------|
| category | `fw`, `linux`, `siem`, `web`, `cloud`, `k8s`, `iot`, `db`, `windows` |
| vendor_short | `cisco`, `paloalto`, `qradar`, `nginx`, `aws`, `postgres` |
| product_short | `asa`, `cloudtrail`, `audit`, `security`, `sysmon` |

Rules:
- All lowercase, dot-delimited
- No spaces, underscores, or hyphens in the type string itself
- Maximum 4 segments (e.g. `cloud.aws.cloudtrail` is 3 — fine)
- Must be stable across software versions (version goes in `source.product_version`)

---

## Source-specific Metadata Sub-object Per Type

| `source.type` | Nested key inside `source.*` | Sub-object doc |
|---------------|------------------------------|----------------|
| `fw.cisco.asa` | `source.syslog` | [envelope-spec.md §2.1](envelope-spec.md#21-sourcesyslog--for-raw_format-syslog3164) |
| `linux.auth` | `source.syslog` | [envelope-spec.md §2.1](envelope-spec.md#21-sourcesyslog--for-raw_format-syslog3164) |
| `fw.paloalto` | `source.cef` | [envelope-spec.md §2.2](envelope-spec.md#22-sourcecef--for-raw_format-cef) |
| `siem.qradar` | `source.leef` | [envelope-spec.md §2.3](envelope-spec.md#23-sourceleef--for-raw_format-leef) |
| `web.nginx.access` | `source.web` | [envelope-spec.md §2.7](envelope-spec.md#27-sourceweb--for-http-access-logs) |
| `cloud.aws.cloudtrail` | `source.cloud` | [envelope-spec.md §2.6](envelope-spec.md#26-sourcecloud--for-cloud-provider-logs) |
| `k8s.audit` | `source.k8s` | [envelope-spec.md §2.5](envelope-spec.md#25-sourcek8s--for-kubernetes-audit-logs) |
| `iot.sensor` | `source.iot` | [envelope-spec.md §2.8](envelope-spec.md#28-sourceiot--for-iot-sensor-telemetry) |
| `db.postgres` | `source.db` | [envelope-spec.md §2.9](envelope-spec.md#29-sourcedb--for-database-logs) |
| `windows.security` | `source.evtx` | [envelope-spec.md §2.4](envelope-spec.md#24-sourceevtx--for-raw_format-evtx_xml) |
| `windows.sysmon` | `source.evtx` | [envelope-spec.md §2.4](envelope-spec.md#24-sourceevtx--for-raw_format-evtx_xml) |

---

## Adding a New Source Type

When onboarding a new log source:

1. Choose a `source.type` following the naming convention above
2. Add a row to this registry
3. Update the collector config (Vector VRL transform) to set the correct `source.type` and source-specific nested object
4. Add a routing rule in `vector-central-parser.yaml` under `route_source_type`
5. Write or adapt an OCSF parser transform for the new type
6. Add the type to `validate_ocsf.py` known types list
7. Add an emulator under `test-suite/emulators/` if one does not exist

See [metadataGuide.md §9](../metadataGuide.md) for the full onboarding checklist.
