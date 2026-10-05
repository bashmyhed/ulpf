#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ULPF Agent Installation & Configuration Generator
# ──────────────────────────────────────────────────────────────────────────────
# Purpose: Interactive setup wizard to configure and generate tailored
#          Vector collector agent deployments with custom VRL classification
#          rules conforming to the ULPF Envelope specification.
#
# Usage:
#   Interactive:  ./install-agent.sh
#   Non-interactive / Flags:
#     ./install-agent.sh --name agent-kol-01 --site kol-dc1 --kafka localhost:9092 --vendors 1,2,5
# ──────────────────────────────────────────────────────────────────────────────

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
RED="\033[0;31m"
MAGENTA="\033[0;35m"
DIM="\033[2m"
RESET="\033[0m"

# Default Values
AGENT_NAME=""
SITE_ID="kol-dc1"
KAFKA_BROKER="localhost:9092"
KAFKA_TOPIC="ulpf-raw-logs"
CONFIG_SERVER_URL="http://localhost:8080"
INGEST_MODE="file" # file, syslog, dual
SELECTED_VENDORS="A"
INTERACTIVE=true

print_banner() {
  cat << "EOF"
================================================================================
   _   _ _     ____  _____      _                    _   
  | | | | |   |  _ \|  ___|    / \   __ _  ___ _ __ | |_ 
  | | | | |   | |_) | |_      / _ \ / _` |/ _ \ '_ \| __|
  | |_| | |___|  __/|  _|    / ___ \ (_| |  __/ | | | |_ 
   \___/|_____|_|   |_|     /_/   \_\__, |\___|_| |_|\__|
                                    |___/                 
  Universal Log Parser Framework — Agent Deployment Generator
================================================================================
EOF
}

show_help() {
  cat << EOF
Usage: ./install-agent.sh [OPTIONS]

Options:
  --name <name>         Agent identifier (e.g. agent-kol-01)
  --site <site_id>      Site identifier (default: kol-dc1)
  --kafka <host:port>   Kafka broker bootstrap (default: localhost:9092)
  --topic <topic>       Kafka destination topic (default: ulpf-raw-logs)
  --config-server <url> Config Server URL (default: http://localhost:8080)
  --mode <mode>         Ingest mode: file | syslog | dual (default: file)
  --vendors <list>      Vendor options (e.g. "1,2,5" or "P1", "P2", "P3", "A")
  --non-interactive     Run in non-interactive mode using provided/default values
  -h, --help            Show this help message

Presets:
  A   - All supported vendors (Universal Agent)
  P1  - Network & Firewall Preset (Cisco ASA, Palo Alto CEF, QRadar LEEF, Linux Auth)
  P2  - Cloud & App Preset (Nginx, CloudTrail, Kubernetes, IoT Sensor, Postgres)
  P3  - Windows Endpoint Preset (Windows Security, Sysmon, PowerShell)

Examples:
  ./install-agent.sh
  ./install-agent.sh --name agent-del-02 --site del-dc2 --kafka 192.168.1.100:9092 --vendors P1
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      AGENT_NAME="$2"
      INTERACTIVE=false
      shift 2
      ;;
    --site)
      SITE_ID="$2"
      shift 2
      ;;
    --kafka)
      KAFKA_BROKER="$2"
      shift 2
      ;;
    --topic)
      KAFKA_TOPIC="$2"
      shift 2
      ;;
    --config-server)
      CONFIG_SERVER_URL="$2"
      shift 2
      ;;
    --mode)
      INGEST_MODE="$2"
      shift 2
      ;;
    --vendors)
      SELECTED_VENDORS="$2"
      shift 2
      ;;
    --non-interactive)
      INTERACTIVE=false
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown argument: $1${RESET}"
      show_help
      exit 1
      ;;
  esac
done

if [[ "$INTERACTIVE" == "true" ]]; then
  print_banner

  echo -e "${CYAN}Configure your agent parameters below. Press [Enter] to accept defaults.${RESET}\n"

  # 1. Agent Name
  while true; do
    read -rp "$(echo -e "${BOLD}1. Agent Identifier/Name${RESET} [e.g. agent-mumbai-01, agent-edge-01]: ")" input_name
    AGENT_NAME="${input_name:-agent-edge-01}"
    # Sanitize name
    AGENT_NAME="$(echo "${AGENT_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-_' '-' | sed 's/^-//;s/-$//')"
    if [[ -n "$AGENT_NAME" ]]; then
      break
    fi
  done
  echo -e "   → Configured Agent Name: ${GREEN}${AGENT_NAME}${RESET}\n"

  # 2. Site ID
  read -rp "$(echo -e "${BOLD}2. Site ID${RESET} (kol-dc1 / del-dc2 / mum-dc3 / custom) [default: ${SITE_ID}]: ")" input_site
  SITE_ID="${input_site:-$SITE_ID}"
  echo -e "   → Configured Site ID: ${GREEN}${SITE_ID}${RESET}\n"

  # 3. Kafka Broker IP
  read -rp "$(echo -e "${BOLD}3. Kafka Broker Address${RESET} (host:port) [default: ${KAFKA_BROKER}]: ")" input_kafka
  KAFKA_BROKER="${input_kafka:-$KAFKA_BROKER}"
  echo -e "   → Configured Kafka Broker: ${GREEN}${KAFKA_BROKER}${RESET}\n"

  # 4. Kafka Topic
  read -rp "$(echo -e "${BOLD}4. Kafka Raw Ingestion Topic${RESET} [default: ${KAFKA_TOPIC}]: ")" input_topic
  KAFKA_TOPIC="${input_topic:-$KAFKA_TOPIC}"
  echo -e "   → Configured Raw Topic: ${GREEN}${KAFKA_TOPIC}${RESET}\n"

  # 5. Remote Config Server
  read -rp "$(echo -e "${BOLD}5. Config Server URL${RESET} (for remote config sync) [default: ${CONFIG_SERVER_URL}]: ")" input_cs
  CONFIG_SERVER_URL="${input_cs:-$CONFIG_SERVER_URL}"
  echo -e "   → Configured Config Server: ${GREEN}${CONFIG_SERVER_URL}${RESET}\n"

  # 6. Ingestion Source Mode
  echo -e "${BOLD}6. Log Ingestion Mode:${RESET}"
  echo "   [1] Local directory tailing (monitors log files on disk, e.g. /logs/*.log)"
  echo "   [2] Syslog Network Listener (UDP & TCP listeners on port 514 / 1514)"
  echo "   [3] Dual Mode (Tails local directory + listens for incoming network syslog)"
  read -rp "   Choose ingestion mode [1-3, default: 1]: " input_mode
  case "${input_mode}" in
    2) INGEST_MODE="syslog" ;;
    3) INGEST_MODE="dual" ;;
    *) INGEST_MODE="file" ;;
  esac
  echo -e "   → Selected Ingestion Mode: ${GREEN}${INGEST_MODE}${RESET}\n"

  # 7. Vendors & Log Format Selection
  echo -e "${BOLD}7. Supported Log Providers & VRL Classification Transforms:${RESET}"
  echo -e "   ${MAGENTA}Presets:${RESET}"
  echo "     [A]  All Supported Providers (Universal Ingestion Engine)"
  echo "     [P1] Network & Firewall Preset (Cisco ASA, Palo Alto CEF, QRadar LEEF, Linux Auth)"
  echo "     [P2] Cloud & Application Preset (Nginx JSON, CloudTrail, K8s Audit, IoT, Postgres)"
  echo "     [P3] Windows Endpoint Preset (Windows Security, Sysmon, PowerShell EVTX XML)"
  echo -e "   ${MAGENTA}Individual Providers:${RESET}"
  echo "     [1]  Cisco ASA Firewall (%ASA-* Syslog RFC 3164)"
  echo "     [2]  Linux Auth & System Syslog (auth.log / SSH / PAM RFC 3164)"
  echo "     [3]  Palo Alto Networks NGFW (CEF:0|... Common Event Format)"
  echo "     [4]  IBM QRadar SIEM (LEEF:1.0/2.0 Log Event Extended Format)"
  echo "     [5]  NGINX Web Server (JSON Access Logs)"
  echo "     [6]  AWS CloudTrail (JSON API Activity Logs)"
  echo "     [7]  Kubernetes Audit (JSON K8s Audit Events)"
  echo "     [8]  IoT Sensor Gateways (JSON Telemetry)"
  echo "     [9]  PostgreSQL Database (CSV Audit Logs)"
  echo "     [10] Windows Security & Sysmon (EVTX XML Logs)"
  echo "     [11] Generic Application JSON (Structured JSON files)"
  echo "     [12] Generic Plain Syslog (RFC 3164 / 5424 Fallback)"
  echo ""
  read -rp "$(echo -e "   Enter choice (${CYAN}e.g. A, or P1, or 1,2,5${RESET}) [default: A]: ")" input_vendors
  SELECTED_VENDORS="${input_vendors:-A}"
fi

# Fallback for empty agent name in non-interactive
if [[ -z "$AGENT_NAME" ]]; then
  AGENT_NAME="agent-custom-01"
fi

# Determine active vendor flags
HAS_ALL=false
HAS_CISCO=false
HAS_LINUX=false
HAS_PALOALTO=false
HAS_QRADAR=false
HAS_NGINX=false
HAS_CLOUDTRAIL=false
HAS_K8S=false
HAS_IOT=false
HAS_POSTGRES=false
HAS_WINDOWS=false
HAS_APP_JSON=false
HAS_GENERIC_SYSLOG=true

UPPER_SELECTION="$(echo "$SELECTED_VENDORS" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"

if [[ "$UPPER_SELECTION" == "A" || "$UPPER_SELECTION" == "ALL" ]]; then
  HAS_ALL=true
  HAS_CISCO=true
  HAS_LINUX=true
  HAS_PALOALTO=true
  HAS_QRADAR=true
  HAS_NGINX=true
  HAS_CLOUDTRAIL=true
  HAS_K8S=true
  HAS_IOT=true
  HAS_POSTGRES=true
  HAS_WINDOWS=true
  HAS_APP_JSON=true
elif [[ "$UPPER_SELECTION" == "P1" ]]; then
  HAS_CISCO=true
  HAS_LINUX=true
  HAS_PALOALTO=true
  HAS_QRADAR=true
elif [[ "$UPPER_SELECTION" == "P2" ]]; then
  HAS_NGINX=true
  HAS_CLOUDTRAIL=true
  HAS_K8S=true
  HAS_IOT=true
  HAS_POSTGRES=true
  HAS_APP_JSON=true
elif [[ "$UPPER_SELECTION" == "P3" ]]; then
  HAS_WINDOWS=true
else
  IFS=',' read -ra V_ARR <<< "$SELECTED_VENDORS"
  for v in "${V_ARR[@]}"; do
    case "$v" in
      1) HAS_CISCO=true ;;
      2) HAS_LINUX=true ;;
      3) HAS_PALOALTO=true ;;
      4) HAS_QRADAR=true ;;
      5) HAS_NGINX=true ;;
      6) HAS_CLOUDTRAIL=true ;;
      7) HAS_K8S=true ;;
      8) HAS_IOT=true ;;
      9) HAS_POSTGRES=true ;;
      10) HAS_WINDOWS=true ;;
      11) HAS_APP_JSON=true ;;
      12) HAS_GENERIC_SYSLOG=true ;;
      p1|P1) HAS_CISCO=true; HAS_LINUX=true; HAS_PALOALTO=true; HAS_QRADAR=true ;;
      p2|P2) HAS_NGINX=true; HAS_CLOUDTRAIL=true; HAS_K8S=true; HAS_IOT=true; HAS_POSTGRES=true ;;
      p3|P3) HAS_WINDOWS=true ;;
      a|A) HAS_ALL=true; HAS_CISCO=true; HAS_LINUX=true; HAS_PALOALTO=true; HAS_QRADAR=true; HAS_NGINX=true; HAS_CLOUDTRAIL=true; HAS_K8S=true; HAS_IOT=true; HAS_POSTGRES=true; HAS_WINDOWS=true; HAS_APP_JSON=true ;;
    esac
  done
fi

TARGET_DIR="${SCRIPT_DIR}/deployment/${AGENT_NAME}"
echo -e "\n${BLUE}================================================================================${RESET}"
echo -e "${BOLD}Generating Agent Configuration under:${RESET} ${GREEN}${TARGET_DIR}${RESET}"
echo -e "${BLUE}================================================================================${RESET}"

mkdir -p "${TARGET_DIR}/config"
mkdir -p "${TARGET_DIR}/logs/syslog"
mkdir -p "${TARGET_DIR}/logs/cef"
mkdir -p "${TARGET_DIR}/logs/raw"
mkdir -p "${TARGET_DIR}/logs/json"
mkdir -p "${TARGET_DIR}/logs/csv"
mkdir -p "${TARGET_DIR}/logs/xml"
mkdir -p "${TARGET_DIR}/logs/debug"
mkdir -p "${TARGET_DIR}/sample-logs"

# ──────────────────────────────────────────────────────────────────────────────
# Generate VRL Transform Code
# ──────────────────────────────────────────────────────────────────────────────
VRL_SOURCE=$(cat << 'VRL_HEAD_EOF'
# ── 1. Validate payload ────────────────────────────────────────────────
raw_msg = string!(.message)
if length(raw_msg) == 0 { abort }

# Skip CSV header rows if present
if starts_with(raw_msg, "timestamp,") { abort }

# ── 2. Compute raw metrics ─────────────────────────────────────────────
raw_sha256 = sha2(raw_msg)
raw_len    = length(raw_msg)
coll_time  = to_unix_timestamp(now(), unit: "milliseconds")
site_id    = get_env_var("SITE_ID") ?? "__SITE_ID__"
agent_id   = get_env_var("AGENT_ID") ?? "__AGENT_NAME__"
fpath      = string(.file_path) ?? "/logs/generic.log"

src_type   = "unknown.syslog"
vendor     = "Unknown"
product    = "Unknown"
raw_format = "plain"
extra_src  = {}
classified = false

VRL_HEAD_EOF
)

# Replace placeholders
VRL_SOURCE="${VRL_SOURCE/__SITE_ID__/${SITE_ID}}"
VRL_SOURCE="${VRL_SOURCE/__AGENT_NAME__/${AGENT_NAME}}"

# Append Vendor Branches
if [[ "$HAS_PALOALTO" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── Palo Alto CEF ──────────────────────────────────────────────────────
if !classified && starts_with(raw_msg, "CEF:") {
  src_type   = "fw.paloalto"
  vendor     = "PaloAlto"
  product    = "PAN-OS"
  raw_format = "cef"
  extra_src  = { "cef": { "version": "0", "device_vendor": "PaloAlto", "device_product": "PAN-OS" } }
  classified = true
}
EOF
)
fi

if [[ "$HAS_QRADAR" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── IBM QRadar LEEF ────────────────────────────────────────────────────
if !classified && (starts_with(raw_msg, "LEEF:") || contains(raw_msg, "LEEF:1.0") || contains(raw_msg, "LEEF:2.0")) {
  src_type   = "siem.qradar"
  vendor     = "IBM"
  product    = "QRadar"
  raw_format = "leef"
  extra_src  = { "leef": { "version": "1.0", "delimiter": "\t" } }
  classified = true
}
EOF
)
fi

if [[ "$HAS_CISCO" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── Cisco ASA Syslog ───────────────────────────────────────────────────
if !classified && (starts_with(raw_msg, "%ASA-") || match(raw_msg, r'^%[A-Z0-9]+-[0-9]-[0-9]+:')) {
  src_type   = "fw.cisco.asa"
  vendor     = "Cisco"
  product    = "ASA"
  raw_format = "syslog3164"
  extra_src  = { "syslog": { "rfc": "3164", "facility": "local4", "framing": "newline" } }
  classified = true
}
EOF
)
fi

if [[ "$HAS_WINDOWS" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── Windows EVTX XML / Sysmon / PowerShell ─────────────────────────────
if !classified && (starts_with(raw_msg, "<") || contains(raw_msg, "<Event") || contains(raw_msg, "EventID")) {
  raw_format = "evtx_xml"
  vendor     = "Microsoft"
  if contains(raw_msg, "Sysmon") {
    src_type = "windows.sysmon"
    product  = "Sysmon"
    extra_src = { "evtx": { "channel": "Microsoft-Windows-Sysmon/Operational", "provider": "Microsoft-Windows-Sysmon" } }
  } else if contains(raw_msg, "PowerShell") {
    src_type = "windows.powershell"
    product  = "PowerShell"
    extra_src = { "evtx": { "channel": "Microsoft-Windows-PowerShell/Operational", "provider": "PowerShell" } }
  } else {
    src_type = "windows.security"
    product  = "Security-Auditing"
    extra_src = { "evtx": { "channel": "Security", "provider": "Microsoft-Windows-Security-Auditing" } }
  }
  classified = true
}
EOF
)
fi

# JSON Group
JSON_VENDORS=""
if [[ "$HAS_K8S" == "true" ]]; then
  JSON_VENDORS+=$(cat << 'EOF'
  if contains(raw_msg, "\"apiVersion\"") && contains(raw_msg, "audit.k8s.io") {
    src_type = "k8s.audit"
    vendor   = "CNCF"
    product  = "Kubernetes"
    extra_src = { "k8s": { "cluster": "k8s-prod-01" } }
    classified = true
  }
EOF
)
fi

if [[ "$HAS_CLOUDTRAIL" == "true" ]]; then
  JSON_VENDORS+=$(cat << 'EOF'
  if !classified && contains(raw_msg, "\"eventSource\"") && contains(raw_msg, "amazonaws.com") {
    src_type = "cloud.aws.cloudtrail"
    vendor   = "AWS"
    product  = "CloudTrail"
    extra_src = { "cloud": { "provider": "aws", "region": "us-east-1" } }
    classified = true
  }
EOF
)
fi

if [[ "$HAS_NGINX" == "true" ]]; then
  JSON_VENDORS+=$(cat << 'EOF'
  if !classified && contains(raw_msg, "\"remote_addr\"") && contains(raw_msg, "\"request_method\"") {
    src_type = "web.nginx.access"
    vendor   = "F5"
    product  = "nginx"
    extra_src = { "web": { "log_format_name": "json" } }
    classified = true
  }
EOF
)
fi

if [[ "$HAS_IOT" == "true" ]]; then
  JSON_VENDORS+=$(cat << 'EOF'
  if !classified && contains(raw_msg, "\"device_id\"") && contains(raw_msg, "\"sensor_type\"") {
    src_type = "iot.sensor"
    vendor   = "Generic"
    product  = "SensorGateway"
    extra_src = { "iot": { "protocol": "http" } }
    classified = true
  }
EOF
)
fi

if [[ -n "$JSON_VENDORS" || "$HAS_APP_JSON" == "true" ]]; then
VRL_SOURCE+=$(cat << EOF

# ── JSON Structured Logs ───────────────────────────────────────────────
if !classified && (starts_with(raw_msg, "{") || starts_with(raw_msg, "[")) {
  raw_format = "json"
${JSON_VENDORS}
  if !classified {
    src_type = "app.json"
    vendor   = "Generic"
    product  = "App"
    classified = true
  }
}
EOF
)
fi

if [[ "$HAS_POSTGRES" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── PostgreSQL CSV Logs ────────────────────────────────────────────────
if !classified && contains(raw_msg, ",") {
  src_type   = "db.postgres"
  vendor     = "PostgreSQL"
  product    = "PostgreSQL"
  raw_format = "csv"
  extra_src  = { "db": { "engine": "postgresql", "audit_mechanism": "csv" } }
  classified = true
}
EOF
)
fi

if [[ "$HAS_LINUX" == "true" ]]; then
VRL_SOURCE+=$(cat << 'EOF'

# ── Linux Auth / Standard Syslog (RFC 3164) ────────────────────────────
if !classified && match(raw_msg, r'^[A-Z][a-z]{2}\s+\d') {
  src_type   = "linux.auth"
  vendor     = "Linux"
  product    = "OpenSSH"
  raw_format = "syslog3164"
  extra_src  = { "os": "linux", "syslog": { "rfc": "3164", "facility": "auth", "framing": "newline" } }
  classified = true
}
EOF
)
fi

# Fallback & ULPF Envelope Building
VRL_SOURCE+=$(cat << 'VRL_TAIL_EOF'

# ── 3. Build ULPF Envelope (metadataGuide Section 2 & 3) ───────────────
. = {
  "envelope_version": 1,
  "site_id": site_id,
  "agent_id": agent_id,
  "collector_id": agent_id,
  "agent_version": "1.0.0",
  "collector_version": "1.0.0",
  "seq": coll_time,
  "collected_at": coll_time,
  "source_tz": "+05:30",
  "clock": {
    "synced": true,
    "skew_ms": 0
  },
  "source": {
    "type": src_type,
    "vendor": vendor,
    "product": product,
    "product_version": "unknown",
    "transport": "file",
    "host_name": get_hostname() ?? agent_id,
    "host_ip": null,
    "sender_ip": null,
    "sender_port": null,
    "host_id": null,
    "position": {
      "path": fpath,
      "inode": null,
      "offset": null,
      "line_no": null
    }
  },
  "raw_format": raw_format,
  "raw_encoding": "utf-8",
  "raw_len": raw_len,
  "raw_sha256": raw_sha256,
  "raw": raw_msg,
  "flags": {
    "truncated": false,
    "multiline_joined": false,
    "decoded_from": null,
    "redacted": false,
    "duplicate_suspect": false
  },
  "labels": {
    "env": get_env_var("INSTANCE_ENV") ?? "production",
    "site": site_id,
    "tier": agent_id
  }
}

# Attach extra source attributes if detected
if is_object(extra_src.cef) { .source.cef = extra_src.cef }
if is_object(extra_src.leef) { .source.leef = extra_src.leef }
if is_object(extra_src.syslog) { .source.syslog = extra_src.syslog }
if is_object(extra_src.os) { .source.os = extra_src.os }
if is_object(extra_src.k8s) { .source.k8s = extra_src.k8s }
if is_object(extra_src.cloud) { .source.cloud = extra_src.cloud }
if is_object(extra_src.web) { .source.web = extra_src.web }
if is_object(extra_src.iot) { .source.iot = extra_src.iot }
if is_object(extra_src.db) { .source.db = extra_src.db }
if is_object(extra_src.evtx) { .source.evtx = extra_src.evtx }
VRL_TAIL_EOF
)

# ──────────────────────────────────────────────────────────────────────────────
# Build Sources Block
# ──────────────────────────────────────────────────────────────────────────────
SOURCES_YAML="sources:\n"
SOURCES_YAML+="  host_sys:\n"
SOURCES_YAML+="    type: host_metrics\n"
SOURCES_YAML+="    scrape_interval_secs: 15\n\n"
SOURCES_YAML+="  internal_metrics:\n"
SOURCES_YAML+="    type: internal_metrics\n\n"

INPUTS_LIST=""

if [[ "$INGEST_MODE" == "file" || "$INGEST_MODE" == "dual" ]]; then
  SOURCES_YAML+="  log_files:\n"
  SOURCES_YAML+="    type: file\n"
  SOURCES_YAML+="    include:\n"
  SOURCES_YAML+="      - /logs/**/*.log\n"
  SOURCES_YAML+="      - /logs/**/*.json\n"
  SOURCES_YAML+="      - /logs/**/*.csv\n"
  SOURCES_YAML+="      - /logs/**/*.txt\n"
  SOURCES_YAML+="    read_from: beginning\n"
  SOURCES_YAML+="    ignore_checkpoints: false\n"
  SOURCES_YAML+="    file_key: file_path\n\n"
  INPUTS_LIST+="      - log_files\n"
fi

if [[ "$INGEST_MODE" == "syslog" || "$INGEST_MODE" == "dual" ]]; then
  SOURCES_YAML+="  syslog_udp:\n"
  SOURCES_YAML+="    type: syslog\n"
  SOURCES_YAML+="    mode: udp\n"
  SOURCES_YAML+="    address: 0.0.0.0:1514\n\n"
  SOURCES_YAML+="  syslog_tcp:\n"
  SOURCES_YAML+="    type: syslog\n"
  SOURCES_YAML+="    mode: tcp\n"
  SOURCES_YAML+="    address: 0.0.0.0:1514\n\n"
  INPUTS_LIST+="      - syslog_udp\n"
  INPUTS_LIST+="      - syslog_tcp\n"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Build Sinks Block
# ──────────────────────────────────────────────────────────────────────────────
SINKS_YAML="sinks:\n"
SINKS_YAML+="  kafka_out:\n"
SINKS_YAML+="    type: kafka\n"
SINKS_YAML+="    inputs:\n"
SINKS_YAML+="      - envelope_${AGENT_NAME//-/_}\n"
SINKS_YAML+="    bootstrap_servers: \"\${KAFKA_BOOTSTRAP:-${KAFKA_BROKER}}\"\n"
SINKS_YAML+="    topic: \"\${KAFKA_TOPIC:-${KAFKA_TOPIC}}\"\n"
SINKS_YAML+="    encoding:\n"
SINKS_YAML+="      codec: json\n"
SINKS_YAML+="    buffer:\n"
SINKS_YAML+="      type: memory\n"
SINKS_YAML+="      max_events: 1000\n"
SINKS_YAML+="      when_full: block\n\n"
SINKS_YAML+="  prom_exporter:\n"
SINKS_YAML+="    type: prometheus_exporter\n"
SINKS_YAML+="    inputs:\n"
SINKS_YAML+="      - host_sys\n"
SINKS_YAML+="      - internal_metrics\n"
SINKS_YAML+="    address: \"0.0.0.0:9090\"\n\n"
SINKS_YAML+="  local_debug:\n"
SINKS_YAML+="    type: file\n"
SINKS_YAML+="    inputs:\n"
SINKS_YAML+="      - envelope_${AGENT_NAME//-/_}\n"
SINKS_YAML+="    path: /logs/debug/enveloped-sent.ndjson\n"
SINKS_YAML+="    encoding:\n"
SINKS_YAML+="      codec: json\n"

# ──────────────────────────────────────────────────────────────────────────────
# Write deployment files
# ──────────────────────────────────────────────────────────────────────────────

# Copy static config-agent binary if available
mkdir -p "${TARGET_DIR}/bin"
if [[ -f "${SCRIPT_DIR}/config-agent/ulpf-config-agent" ]]; then
  cp "${SCRIPT_DIR}/config-agent/ulpf-config-agent" "${TARGET_DIR}/bin/config-agent"
  chmod +x "${TARGET_DIR}/bin/config-agent"
fi

# 1. vector.yaml (Single Standalone File)
cat << EOF > "${TARGET_DIR}/vector.yaml"
# ──────────────────────────────────────────────────────────────────────────────
# ULPF Agent Configuration — ${AGENT_NAME}
# Site ID: ${SITE_ID}
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ──────────────────────────────────────────────────────────────────────────────

api:
  enabled: true
  address: "0.0.0.0:8686"
  playground: false

$(echo -e "$SOURCES_YAML")
transforms:
  envelope_${AGENT_NAME//-/_}:
    type: remap
    inputs:
$(echo -e "$INPUTS_LIST" | sed 's/[ \t]*$//')
    source: |
$(echo "$VRL_SOURCE" | sed 's/^/      /')

$(echo -e "$SINKS_YAML")
EOF

# 2. Modular split under config/
cat << EOF > "${TARGET_DIR}/config/sources.yaml"
$(echo -e "$SOURCES_YAML")
EOF

cat << EOF > "${TARGET_DIR}/config/transform.yaml"
transforms:
  envelope_${AGENT_NAME//-/_}:
    type: remap
    inputs:
$(echo -e "$INPUTS_LIST" | sed 's/[ \t]*$//')
    source: |
$(echo "$VRL_SOURCE" | sed 's/^/      /')
EOF

cat << EOF > "${TARGET_DIR}/config/sinks.yaml"
$(echo -e "$SINKS_YAML")
EOF

cat << EOF > "${TARGET_DIR}/config/env.yaml"
# Environment Variable Documentation & Defaults
AGENT_ID: "${AGENT_NAME}"
SITE_ID: "${SITE_ID}"
KAFKA_BOOTSTRAP: "${KAFKA_BROKER}"
KAFKA_TOPIC: "${KAFKA_TOPIC}"
CONFIG_SERVER_URL: "${CONFIG_SERVER_URL}"
INSTANCE_ENV: "production"
EOF

# 3. .env file
cat << EOF > "${TARGET_DIR}/.env"
AGENT_ID=${AGENT_NAME}
COLLECTOR_ID=${AGENT_NAME}
SITE_ID=${SITE_ID}
KAFKA_BOOTSTRAP=${KAFKA_BROKER}
KAFKA_TOPIC=${KAFKA_TOPIC}
CONFIG_SERVER_URL=${CONFIG_SERVER_URL}
INSTANCE_ENV=production
VECTOR_CONFIG_DIR=/etc/vector
LOG_DIR=./logs
EOF

# 4. docker-compose.yml
cat << EOF > "${TARGET_DIR}/docker-compose.yml"
services:
  ${AGENT_NAME}:
    image: timberio/vector:0.40.0-alpine
    container_name: ulpf-${AGENT_NAME}
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./vector.yaml:/etc/vector/vector.yaml:ro
      - ./logs:/logs:rw
    ports:
      - "8686:8686"
      - "9090:9090"
$(if [[ "$INGEST_MODE" == "syslog" || "$INGEST_MODE" == "dual" ]]; then
cat << 'PORT_EOF'
      - "1514:1514/udp"
      - "1514:1514/tcp"
PORT_EOF
fi)
    extra_hosts:
      - "host.docker.internal:host-gateway"
    command: ["--config", "/etc/vector/vector.yaml"]
EOF

# 5. run.sh management script
cat << 'RUN_EOF' > "${TARGET_DIR}/run.sh"
#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DIR}"

ACTION="${1:-start}"

case "${ACTION}" in
  start|up)
    echo "Starting agent container via Docker Compose..."
    docker compose up -d
    echo "Agent started. Monitoring logs (Ctrl+C to detach):"
    docker compose logs -f
    ;;
  stop|down)
    echo "Stopping agent container..."
    docker compose down
    ;;
  status)
    echo "=== Container Status ==="
    docker compose ps
    echo -e "\n=== Vector Metrics (Preview) ==="
    curl -s http://localhost:8686/metrics | head -n 20 || echo "Vector metrics API not reachable on port 8686"
    ;;
  validate)
    echo "Validating Vector configuration..."
    docker run --rm -v "${DIR}/vector.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml
    echo "[OK] Configuration is valid."
    ;;
  test-send)
    echo "Injecting sample log lines into ./logs/syslog/test.log..."
    mkdir -p ./logs/syslog
    cat ./sample-logs/test-samples.log >> ./logs/syslog/test.log
    echo "Done! Check ./logs/debug/enveloped-sent.ndjson in 2 seconds:"
    sleep 2
    if [[ -f ./logs/debug/enveloped-sent.ndjson ]]; then
      tail -n 3 ./logs/debug/enveloped-sent.ndjson | jq . || tail -n 3 ./logs/debug/enveloped-sent.ndjson
    else
      echo "No output yet. Ensure agent is running via ./run.sh start"
    fi
    ;;
  native)
    echo "Running Vector locally using installed binary..."
    vector --config vector.yaml
    ;;
  *)
    echo "Usage: ./run.sh [start | stop | status | validate | test-send | native]"
    exit 1
    ;;
esac
RUN_EOF
chmod +x "${TARGET_DIR}/run.sh"

# 6. Sample log lines for immediate testing
cat << 'SAMPLES_EOF' > "${TARGET_DIR}/sample-logs/test-samples.log"
%ASA-4-106023: Deny inbound UDP from 198.51.100.22/51412 to 192.0.2.1/53 on interface outside
Oct 05 18:22:01 edge-server sshd[1234]: Accepted publickey for admin from 192.168.1.10 port 49152 ssh2
CEF:0|PaloAlto|PAN-OS|10.1.0|TRAFFIC|allow|1|src=192.168.1.10 dst=8.8.8.8 spt=5353 dpt=53 proto=udp act=allow
LEEF:2.0|IBM|QRadar|7.4.0|AuthSuccess|devTime=2026-10-05T18:22:01Z	src=10.0.1.5	usrName=secops
{"remote_addr":"10.0.2.15","time_local":"05/Oct/2026:18:22:01 +0000","request":"GET /api/v1/health HTTP/1.1","status":200,"body_bytes_sent":512,"request_method":"GET","http_user_agent":"Mozilla/5.0"}
{"eventVersion":"1.08","eventTime":"2026-10-05T18:22:01Z","eventSource":"iam.amazonaws.com","eventName":"GetUser","awsRegion":"us-east-1","sourceIPAddress":"10.0.3.22","userIdentity":{"type":"IAMUser","userName":"sec-admin"}}
{"kind":"Event","apiVersion":"audit.k8s.io/v1","level":"Metadata","stage":"ResponseComplete","requestURI":"/api/v1/namespaces/default/pods","verb":"get","user":{"username":"kubernetes-admin"},"responseStatus":{"code":200}}
{"device_id":"sensor-gate-42","sensor_type":"temperature","value":24.5,"unit":"C","status":"ok","timestamp":1791211328}
2026-10-05 18:22:01 UTC,app_user,production_db,1234,"127.0.0.1:54321",LOG,00000,"statement: SELECT 1;",,,,,,,
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Name="Microsoft-Windows-Sysmon"/><EventID>1</EventID><TimeCreated SystemTime="2026-10-05T18:22:01Z"/><Computer>DC-WIN01.corp.local</Computer></System><EventData><Data Name="Image">C:\Windows\System32\cmd.exe</Data><Data Name="User">CORP\Administrator</Data></EventData></Event>
SAMPLES_EOF

# 7. README.md
cat << EOF > "${TARGET_DIR}/README.md"
# ULPF Collector Agent — ${AGENT_NAME}

- **Agent Name**: \`${AGENT_NAME}\`
- **Site ID**: \`${SITE_ID}\`
- **Kafka Broker**: \`${KAFKA_BROKER}\`
- **Destination Topic**: \`${KAFKA_TOPIC}\`
- **Config Server**: \`${CONFIG_SERVER_URL}\`
- **Ingestion Mode**: \`${INGEST_MODE}\`

---

## Directory Layout

\`\`\`
deployment/${AGENT_NAME}/
├── vector.yaml             # Complete consolidated Vector configuration
├── config/                 # Modular configuration directory
│   ├── sources.yaml        # Tail/network inputs
│   ├── transform.yaml      # VRL envelope & vendor classifier
│   ├── sinks.yaml          # Kafka output & debug NDJSON
│   └── env.yaml            # Environment variable reference
├── .env                    # Runtime environment variables
├── docker-compose.yml      # Docker service definition
├── run.sh                  # Management script (start/stop/status/validate/test)
├── sample-logs/            # Test logs matching selected vendors
└── logs/                   # Log directory watched by Vector
    ├── syslog/
    ├── cef/
    ├── json/
    ├── xml/
    ├── csv/
    └── debug/
\`\`\`

---

## Quickstart

### 1. Validate the Configuration
\`\`\`bash
./run.sh validate
\`\`\`

### 2. Start the Agent in Docker
\`\`\`bash
./run.sh start
\`\`\`

### 3. Inject Test Logs & Verify Ingestion
\`\`\`bash
./run.sh test-send
\`\`\`

### 4. Check Health & Metrics
\`\`\`bash
./run.sh status
curl -s http://localhost:8686/metrics | grep vector_events_in_total
\`\`\`

### 5. Running Natively (Without Docker)
\`\`\`bash
vector --config vector.yaml
\`\`\`
EOF

# ──────────────────────────────────────────────────────────────────────────────
# Automated Validation using Docker Vector
# ──────────────────────────────────────────────────────────────────────────────
echo -e "\n${CYAN}Running syntax validation on generated Vector configuration...${RESET}"
if command -v docker &>/dev/null && docker info &>/dev/null; then
  if docker run --rm -v "${TARGET_DIR}/vector.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml; then
    echo -e "${GREEN}✔ Vector configuration validated successfully!${RESET}"
  else
    echo -e "${YELLOW}⚠ Vector validate returned warnings or errors. Check syntax.${RESET}"
  fi
else
  echo -e "${DIM}Docker daemon not active or not installed; skipped runtime validation.${RESET}"
fi

echo -e "\n${GREEN}================================================================================${RESET}"
echo -e "${GREEN}${BOLD}Agent Deployment Package Generated Successfully!${RESET}"
echo -e "${GREEN}================================================================================${RESET}"
echo -e "Location: ${CYAN}${TARGET_DIR}${RESET}"
echo -e "\nNext Steps:"
echo -e "  1. Review generated config:  ${BOLD}cat ${TARGET_DIR}/vector.yaml${RESET}"
echo -e "  2. Start the agent:          ${BOLD}cd ${TARGET_DIR} && ./run.sh start${RESET}"
echo -e "  3. Test with sample logs:    ${BOLD}cd ${TARGET_DIR} && ./run.sh test-send${RESET}"
echo -e "${GREEN}================================================================================${RESET}\n"
