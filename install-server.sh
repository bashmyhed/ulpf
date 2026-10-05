#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# ULPF Central Server & Processing Pipeline Generator
# ──────────────────────────────────────────────────────────────────────────────
# Purpose: Interactive setup wizard to configure and generate tailored
#          central server deployments (Vector Normalizer, OCSF v1.3.0 Engine,
#          Modular Sinks, OpenSearch, MinIO Data Lake, ML Anomaly Worker,
#          and optional bundled Edge Collection Agents).
#
# Alignment: NTRO Problem Statement 26156 (Lossless Universal Log Parsing)
#
# Usage:
#   Interactive:  ./install-server.sh
#   Non-interactive / Flags:
#     ./install-server.sh --name server-central-01 --site kol-dc1 --sinks P1,P3 --with-agent --agent-vendors P1
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

# Default Server Configuration Values
SERVER_NAME="server-central-01"
SITE_ID="kol-dc1"
DEPLOY_MODE="distributed" # distributed (external infra) or standalone (embedded infra)
KAFKA_BROKER="localhost:9092"
KAFKA_TOPIC="ulpf-raw-logs"
OPENSEARCH_URL="http://localhost:9200"
OPENSEARCH_INDEX="ulpf-ocsf"
MINIO_ENDPOINT="http://localhost:9000"
MINIO_BUCKET="ulpf-data-lake"
MINIO_USER="minioadmin"
MINIO_PASSWORD="minioadmin"
WITH_ML=true
WITH_CONFIG_SERVER=true
SELECTED_SINKS="D" # D=Default core, A=All, P1=SIEM, P2=DataLake, P3=BigData/SOAR, or 1,2,3...

# Default Agent Configuration Values (Optional)
BUNDLE_AGENT=false
AGENT_NAME="agent-local-01"
AGENT_MODE="file" # file, syslog, dual
AGENT_VENDORS="A"

INTERACTIVE=true

print_banner() {
  cat << "EOF"
================================================================================
   _   _ _     ____  _____   ____                                 
  | | | | |   |  _ \|  ___| / ___|  ___ _ ____   _____ _ __       
  | | | | |   | |_) | |_    \___ \ / _ \ '__\ \ / / _ \ '__|      
  | |_| | |___|  __/|  _|    ___) |  __/ |   \ V /  __/ |         
   \___/|_____|_|   |_|     |____/ \___|_|    \_/ \___|_|         
                                                                  
  Universal Log Parser Framework — Central Server & Sinks Generator
================================================================================
EOF
}

show_help() {
  cat << EOF
Usage: ./install-server.sh [OPTIONS]

Server Options:
  --name <name>            Server identifier / directory name (default: server-central-01)
  --site <site_id>         Primary site identifier (default: kol-dc1)
  --mode <mode>            Infrastructure mode: distributed | standalone (default: distributed)
  --kafka <host:port>      Kafka broker bootstrap address (default: localhost:9092)
  --raw-topic <topic>      Kafka raw log ingestion topic (default: ulpf-raw-logs)
  --opensearch <url>       OpenSearch/Elasticsearch SIEM endpoint (default: http://localhost:9200)
  --opensearch-index <idx> Index prefix pattern (default: ulpf-ocsf)
  --minio-endpoint <url>   MinIO / S3 endpoint (default: http://localhost:9000)
  --minio-bucket <bucket>  MinIO / S3 bucket name (default: ulpf-data-lake)
  --minio-user <user>      MinIO access key (default: minioadmin)
  --minio-password <pass>  MinIO secret key (default: minioadmin)
  --with-ml | --no-ml      Enable / disable ML anomaly worker (default: with-ml)
  --with-config-server | --no-config-server
                           Enable / disable fleet config server (default: with-config-server)

Modular Sinks Options:
  --sinks <selection>      Sink choices: D (Core only), A (All), P1 (SIEM), P2 (Data Lake),
                           P3 (Big Data/SOAR), or comma-separated list: 1,2,3...
                           1: Splunk HEC, 2: Elasticsearch, 3: ClickHouse OLAP,
                           4: AWS S3 Lake, 5: GCP Lake, 6: Azure Blob Lake,
                           7: Downstream Kafka, 8: Syslog Forwarder, 9: SOAR Webhook,
                           10: Airgap WORM Archive, 11: Prometheus Exporter

Agent Options (Optional Bundled Edge Collector):
  --with-agent             Bundle an edge/local collection agent
  --no-agent               Do not bundle an agent (default)
  --agent-name <name>      Agent identifier (default: agent-local-01)
  --agent-mode <mode>      Agent ingestion mode: file | syslog | dual (default: file)
  --agent-vendors <list>   Agent vendor selection: A, P1, P2, P3, or comma-separated 1-12

General Options:
  --non-interactive        Run without interactive prompts
  -h, --help               Show this help message

Examples:
  ./install-server.sh
  ./install-server.sh --name server-del-02 --site del-dc2 --sinks 1,3,7,11 --with-agent --agent-vendors P1
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      SERVER_NAME="$2"
      INTERACTIVE=false
      shift 2
      ;;
    --site)
      SITE_ID="$2"
      shift 2
      ;;
    --mode)
      DEPLOY_MODE="$2"
      shift 2
      ;;
    --kafka)
      KAFKA_BROKER="$2"
      shift 2
      ;;
    --raw-topic)
      KAFKA_TOPIC="$2"
      shift 2
      ;;
    --opensearch)
      OPENSEARCH_URL="$2"
      shift 2
      ;;
    --opensearch-index)
      OPENSEARCH_INDEX="$2"
      shift 2
      ;;
    --minio-endpoint)
      MINIO_ENDPOINT="$2"
      shift 2
      ;;
    --minio-bucket)
      MINIO_BUCKET="$2"
      shift 2
      ;;
    --minio-user)
      MINIO_USER="$2"
      shift 2
      ;;
    --minio-password)
      MINIO_PASSWORD="$2"
      shift 2
      ;;
    --with-ml)
      WITH_ML=true
      shift
      ;;
    --no-ml)
      WITH_ML=false
      shift
      ;;
    --with-config-server)
      WITH_CONFIG_SERVER=true
      shift
      ;;
    --no-config-server)
      WITH_CONFIG_SERVER=false
      shift
      ;;
    --sinks)
      SELECTED_SINKS="$2"
      shift 2
      ;;
    --with-agent)
      BUNDLE_AGENT=true
      shift
      ;;
    --no-agent)
      BUNDLE_AGENT=false
      shift
      ;;
    --agent-name)
      AGENT_NAME="$2"
      BUNDLE_AGENT=true
      shift 2
      ;;
    --agent-mode)
      AGENT_MODE="$2"
      BUNDLE_AGENT=true
      shift 2
      ;;
    --agent-vendors)
      AGENT_VENDORS="$2"
      BUNDLE_AGENT=true
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

  echo -e "${CYAN}Configure your central server parameters below. Press [Enter] to accept defaults.${RESET}\n"

  # ── Part 1: Server Core Infrastructure ─────────────────────────────────────
  echo -e "${BOLD}=== PART 1: Server Core Parameters ===${RESET}"

  # 1. Server Name
  while true; do
    read -rp "$(echo -e "${BOLD}1. Server Identifier/Name${RESET} [default: ${SERVER_NAME}]: ")" input_name
    SERVER_NAME="${input_name:-$SERVER_NAME}"
    SERVER_NAME="$(echo "${SERVER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-_' '-' | sed 's/^-//;s/-$//')"
    if [[ -n "$SERVER_NAME" ]]; then
      break
    fi
  done
  echo -e "   → Server Deployment Directory: ${GREEN}deployment/${SERVER_NAME}/${RESET}\n"

  # 2. Site ID
  read -rp "$(echo -e "${BOLD}2. Primary Site ID${RESET} (kol-dc1 / del-dc2 / mum-dc3 / custom) [default: ${SITE_ID}]: ")" input_site
  SITE_ID="${input_site:-$SITE_ID}"
  echo -e "   → Primary Site ID: ${GREEN}${SITE_ID}${RESET}\n"

  # 3. Deployment Topology Mode
  echo -e "${BOLD}3. Deployment Topology Mode:${RESET}"
  echo "   [1] Distributed Server Pipeline (Vector Normalizer + Sinks + ML Worker connecting to Kafka/OpenSearch/MinIO) [Default]"
  echo "   [2] Complete Standalone Server Stack (Spins up dedicated Kafka + OpenSearch + Dashboards + MinIO + Vector + ML Worker)"
  read -rp "   Choose topology mode [1-2, default: 1]: " input_topo
  case "${input_topo}" in
    2)
      DEPLOY_MODE="standalone"
      KAFKA_BROKER="kafka:9092"
      OPENSEARCH_URL="http://opensearch:9200"
      MINIO_ENDPOINT="http://minio:9000"
      ;;
    *)
      DEPLOY_MODE="distributed"
      ;;
  esac
  echo -e "   → Selected Topology: ${GREEN}${DEPLOY_MODE}${RESET}\n"

  # 4. Kafka Broker Address
  read -rp "$(echo -e "${BOLD}4. Kafka Broker Address${RESET} (host:port) [default: ${KAFKA_BROKER}]: ")" input_kafka
  KAFKA_BROKER="${input_kafka:-$KAFKA_BROKER}"
  echo -e "   → Kafka Broker: ${GREEN}${KAFKA_BROKER}${RESET}\n"

  # 5. Kafka Raw Ingestion Topic
  read -rp "$(echo -e "${BOLD}5. Kafka Raw Ingestion Topic${RESET} [default: ${KAFKA_TOPIC}]: ")" input_topic
  KAFKA_TOPIC="${input_topic:-$KAFKA_TOPIC}"
  echo -e "   → Raw Logs Topic: ${GREEN}${KAFKA_TOPIC}${RESET}\n"

  # 6. OpenSearch SIEM Endpoint
  read -rp "$(echo -e "${BOLD}6. OpenSearch / Elasticsearch SIEM Endpoint${RESET} [default: ${OPENSEARCH_URL}]: ")" input_os
  OPENSEARCH_URL="${input_os:-$OPENSEARCH_URL}"
  echo -e "   → SIEM Endpoint: ${GREEN}${OPENSEARCH_URL}${RESET}\n"

  # 7. MinIO / S3 Raw Data Lake
  read -rp "$(echo -e "${BOLD}7. MinIO / S3 Raw Lake Endpoint${RESET} [default: ${MINIO_ENDPOINT}]: ")" input_minio
  MINIO_ENDPOINT="${input_minio:-$MINIO_ENDPOINT}"
  read -rp "   MinIO Bucket Name [default: ${MINIO_BUCKET}]: " input_bucket
  MINIO_BUCKET="${input_bucket:-$MINIO_BUCKET}"
  echo -e "   → MinIO Lake: ${GREEN}${MINIO_ENDPOINT}/${MINIO_BUCKET}${RESET}\n"

  # 8. ML Worker
  read -rp "$(echo -e "${BOLD}8. Enable Real-Time ML Anomaly Detection Worker?${RESET} [Y/n, default: Y]: ")" input_ml
  if [[ "${input_ml,,}" == "n" || "${input_ml,,}" == "no" ]]; then
    WITH_ML=false
  else
    WITH_ML=true
  fi
  echo -e "   → ML Anomaly Worker: ${GREEN}${WITH_ML}${RESET}\n"

  # 9. Remote Config Server
  read -rp "$(echo -e "${BOLD}9. Enable Central Fleet Config Server?${RESET} (port 8080) [Y/n, default: Y]: ")" input_cs
  if [[ "${input_cs,,}" == "n" || "${input_cs,,}" == "no" ]]; then
    WITH_CONFIG_SERVER=false
  else
    WITH_CONFIG_SERVER=true
  fi
  echo -e "   → Fleet Config Server: ${GREEN}${WITH_CONFIG_SERVER}${RESET}\n"

  # ── Part 2: Output Sinks Selection ─────────────────────────────────────────
  echo -e "${BOLD}=== PART 2: Supported Output Sinks (NTRO PS 26156) ===${RESET}"
  echo -e "   ${CYAN}Core Sinks Included by Default:${RESET}"
  echo "     ✔ OpenSearch SIEM (OCSF v1.3.0 index pattern: ${OPENSEARCH_INDEX}-YYYY.MM.DD)"
  echo "     ✔ MinIO Raw Data Lake (Gzip-compressed raw envelope forensic preservation)"
  echo "     ✔ Local OCSF Stream File (/output/ocsf-events.ndjson)"
  echo "     ✔ ML Feedback Stream (Topic: ulpf-ml-ocsf)"
  echo ""
  echo -e "   ${MAGENTA}Modular Sinks Presets:${RESET}"
  echo "     [D]  Core Sinks Only (Default recommended)"
  echo "     [A]  All Enterprise Sinks (1–11 below)"
  echo "     [P1] SIEM Integration Preset (Splunk HEC, External Elasticsearch, Syslog/CEF Forwarder)"
  echo "     [P2] Multi-Cloud Data Lake Preset (AWS S3, Google Cloud Storage, Azure Blob Storage)"
  echo "     [P3] Big Data & SOC Automation Preset (ClickHouse OLAP, Downstream Kafka, SOAR Webhook, Prometheus)"
  echo ""
  echo -e "   ${MAGENTA}Individual Enterprise Sinks:${RESET}"
  echo "     [1]  Splunk Enterprise & Cloud HEC (HTTP Event Collector)"
  echo "     [2]  Elasticsearch 7.x/8.x / Elastic Security SIEM"
  echo "     [3]  ClickHouse Columnar Big Data OLAP (Petabyte scale, billions/day)"
  echo "     [4]  AWS S3 / MinIO Forensic Data Lake (Athena / Trino / Spark)"
  echo "     [5]  Google Cloud Storage Lake (Chronicle SIEM / BigQuery)"
  echo "     [6]  Azure Blob Storage Lake (Microsoft Sentinel SIEM)"
  echo "     [7]  Downstream Kafka / Redpanda Streaming Bus"
  echo "     [8]  TCP/TLS Syslog Forwarder for Legacy SIEMs (QRadar / ArcSight / CEF / LEEF)"
  echo "     [9]  SOAR Automation Webhook (Cortex XSOAR, Splunk SOAR, Tines)"
  echo "     [10] Air-Gapped Immutable WORM Archive"
  echo "     [11] Prometheus Telemetry & EPS Metrics Exporter (port 9598)"
  echo ""
  read -rp "$(echo -e "   Enter choice (${CYAN}e.g. D, or A, or P1, or 1,3,7,11${RESET}) [default: D]: ")" input_sinks
  SELECTED_SINKS="${input_sinks:-D}"
  echo -e "   → Selected Sinks: ${GREEN}${SELECTED_SINKS}${RESET}\n"

  # ── Part 3: Optional Edge/Local Collection Agent ───────────────────────────
  echo -e "${BOLD}=== PART 3: Optional Edge/Local Collection Agent ===${RESET}"
  read -rp "$(echo -e "   Would you like to bundle a local/edge collection agent with this server? [y/N, default: N]: ")" input_agent
  if [[ "${input_agent,,}" == "y" || "${input_agent,,}" == "yes" ]]; then
    BUNDLE_AGENT=true
    echo -e "   → Agent bundling enabled.\n"

    read -rp "$(echo -e "   ${BOLD}3a. Agent Identifier/Name${RESET} [default: ${AGENT_NAME}]: ")" input_aname
    AGENT_NAME="${input_aname:-$AGENT_NAME}"
    AGENT_NAME="$(echo "${AGENT_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-_' '-' | sed 's/^-//;s/-$//')"

    echo -e "   ${BOLD}3b. Agent Ingestion Mode:${RESET}"
    echo "       [1] Local directory tailing (monitors log files on disk, e.g. /logs/*.log)"
    echo "       [2] Syslog Network Listener (UDP & TCP listeners on port 514 / 1514)"
    echo "       [3] Dual Mode (Tails local directory + listens for incoming network syslog)"
    read -rp "       Choose mode [1-3, default: 1]: " input_amode
    case "${input_amode}" in
      2) AGENT_MODE="syslog" ;;
      3) AGENT_MODE="dual" ;;
      *) AGENT_MODE="file" ;;
    esac

    echo -e "   ${BOLD}3c. Supported Log Providers & Transforms for Agent:${RESET}"
    echo "       [A]  All Supported Providers (Universal Ingestion Engine)"
    echo "       [P1] Network & Firewall Preset (Cisco ASA, Palo Alto CEF, QRadar LEEF, Linux Auth)"
    echo "       [P2] Cloud & Application Preset (Nginx JSON, CloudTrail, K8s Audit, IoT, Postgres)"
    echo "       [P3] Windows Endpoint Preset (Windows Security, Sysmon, PowerShell EVTX XML)"
    echo "       Or enter comma-separated numbers (1-12)"
    read -rp "       Enter vendor choice [default: A]: " input_avendors
    AGENT_VENDORS="${input_avendors:-A}"
  else
    BUNDLE_AGENT=false
    echo -e "   → No agent bundled. Server-only deployment.\n"
  fi
fi

# Fallback for server name
if [[ -z "$SERVER_NAME" ]]; then
  SERVER_NAME="server-central-01"
fi

# ── Evaluate Selected Sinks Flags ─────────────────────────────────────────────
UPPER_SINKS="$(echo "$SELECTED_SINKS" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"

SINK_SPLUNK=false
SINK_ELASTIC=false
SINK_CLICKHOUSE=false
SINK_S3_LAKE=false
SINK_GCP=false
SINK_AZURE=false
SINK_KAFKA=false
SINK_SYSLOG=false
SINK_SOAR=false
SINK_AIRGAP=false
SINK_PROMETHEUS=false

if [[ "$UPPER_SINKS" == "A" || "$UPPER_SINKS" == "ALL" ]]; then
  SINK_SPLUNK=true; SINK_ELASTIC=true; SINK_CLICKHOUSE=true; SINK_S3_LAKE=true
  SINK_GCP=true; SINK_AZURE=true; SINK_KAFKA=true; SINK_SYSLOG=true
  SINK_SOAR=true; SINK_AIRGAP=true; SINK_PROMETHEUS=true
elif [[ "$UPPER_SINKS" != "D" && "$UPPER_SINKS" != "NONE" ]]; then
  IFS=',' read -ra SINK_ITEMS <<< "$UPPER_SINKS"
  for item in "${SINK_ITEMS[@]}"; do
    case "$item" in
      P1)
        SINK_SPLUNK=true; SINK_ELASTIC=true; SINK_SYSLOG=true
        ;;
      P2)
        SINK_S3_LAKE=true; SINK_GCP=true; SINK_AZURE=true
        ;;
      P3)
        SINK_CLICKHOUSE=true; SINK_KAFKA=true; SINK_SOAR=true; SINK_PROMETHEUS=true
        ;;
      1) SINK_SPLUNK=true ;;
      2) SINK_ELASTIC=true ;;
      3) SINK_CLICKHOUSE=true ;;
      4) SINK_S3_LAKE=true ;;
      5) SINK_GCP=true ;;
      6) SINK_AZURE=true ;;
      7) SINK_KAFKA=true ;;
      8) SINK_SYSLOG=true ;;
      9) SINK_SOAR=true ;;
      10) SINK_AIRGAP=true ;;
      11) SINK_PROMETHEUS=true ;;
    esac
  done
fi

TARGET_DIR="${SCRIPT_DIR}/deployment/${SERVER_NAME}"
mkdir -p "${TARGET_DIR}/config/transforms"
mkdir -p "${TARGET_DIR}/config/sinks"
mkdir -p "${TARGET_DIR}/modules/sinks"
mkdir -p "${TARGET_DIR}/modules/env"
mkdir -p "${TARGET_DIR}/output"

echo -e "\n${BLUE}Generating deployment structure under ${BOLD}${TARGET_DIR}${RESET}...\n"

# Copy modular sink library for reference
cp -r "${SCRIPT_DIR}/central/modules/"* "${TARGET_DIR}/modules/" 2>/dev/null || true

# ── Generate .env ─────────────────────────────────────────────────────────────
cat << EOF > "${TARGET_DIR}/.env"
# ──────────────────────────────────────────────────────────────────────────────
# ULPF Server Deployment Environment — ${SERVER_NAME}
# ──────────────────────────────────────────────────────────────────────────────
SERVER_NAME=${SERVER_NAME}
SITE_ID=${SITE_ID}
DEPLOY_MODE=${DEPLOY_MODE}

# Kafka Message Broker
KAFKA_BOOTSTRAP=${KAFKA_BROKER}
KAFKA_TOPIC=${KAFKA_TOPIC}
KAFKA_ML_TOPIC=ulpf-ml-ocsf

# OpenSearch SIEM
OPENSEARCH_ENDPOINT=${OPENSEARCH_URL}
OPENSEARCH_INDEX=${OPENSEARCH_INDEX}

# MinIO / S3 Raw Data Lake
MINIO_ENDPOINT=${MINIO_ENDPOINT}
MINIO_BUCKET=${MINIO_BUCKET}
MINIO_ROOT_USER=${MINIO_USER}
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}

# Config Server
CONFIG_SERVER_URL=http://localhost:8080
ADMIN_TOKEN=admin-token
CENTRAL_TOKEN=central-token

# Modular Sinks Configuration Variables
$(if [[ "$SINK_SPLUNK" == "true" ]]; then
cat << 'SPLUNK_ENV'
SPLUNK_HEC_ENDPOINT=https://splunk.corp.internal:8088
SPLUNK_HEC_TOKEN=00000000-0000-0000-0000-000000000000
SPLUNK_INDEX=ocsf_security
SPLUNK_TLS_VERIFY=false
SPLUNK_ENV
fi)
$(if [[ "$SINK_ELASTIC" == "true" ]]; then
cat << 'ELASTIC_ENV'
ELASTICSEARCH_ENDPOINT=http://elasticsearch:9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=changeme
ELASTICSEARCH_INDEX=ulpf-ocsf-%Y.%m.%d
ELASTIC_ENV
fi)
$(if [[ "$SINK_CLICKHOUSE" == "true" ]]; then
cat << 'CH_ENV'
CLICKHOUSE_ENDPOINT=http://clickhouse:8123
CLICKHOUSE_DATABASE=ulpf
CLICKHOUSE_TABLE=ocsf_events
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CH_ENV
fi)
$(if [[ "$SINK_S3_LAKE" == "true" ]]; then
cat << 'S3_ENV'
S3_DATA_LAKE_BUCKET=ulpf-data-lake
S3_DATA_LAKE_ENDPOINT=http://minio:9000
S3_DATA_LAKE_REGION=us-east-1
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_ENV
fi)
$(if [[ "$SINK_GCP" == "true" ]]; then
cat << 'GCP_ENV'
GCP_DATA_LAKE_BUCKET=ulpf-gcp-lake
GOOGLE_APPLICATION_CREDENTIALS=/etc/vector/gcp-credentials.json
GCP_ENV
fi)
$(if [[ "$SINK_AZURE" == "true" ]]; then
cat << 'AZURE_ENV'
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=ulpflake;AccountKey=dummy;EndpointSuffix=core.windows.net
AZURE_CONTAINER_NAME=ulpf-ocsf-lake
AZURE_ENV
fi)
$(if [[ "$SINK_KAFKA" == "true" ]]; then
cat << 'KAFKA_DOWN_ENV'
DOWNSTREAM_KAFKA_BROKERS=kafka.downstream.internal:9092
DOWNSTREAM_KAFKA_TOPIC=ulpf.ocsf.normalized
DOWNSTREAM_KAFKA_COMPRESSION=gzip
KAFKA_DOWN_ENV
fi)
$(if [[ "$SINK_SYSLOG" == "true" ]]; then
cat << 'SYSLOG_ENV'
SYSLOG_SIEM_HOST=siem-collector.internal:514
SYSLOG_SIEM_MODE=tcp
SYSLOG_ENV
fi)
$(if [[ "$SINK_SOAR" == "true" ]]; then
cat << 'SOAR_ENV'
SOAR_WEBHOOK_URL=https://soar.corp.internal/api/v1/alerts
SOAR_AUTH_TOKEN=changeme
SOAR_BATCH_SIZE=50
SOAR_TIMEOUT_SECS=15
SOAR_ENV
fi)
$(if [[ "$SINK_AIRGAP" == "true" ]]; then
cat << 'AIRGAP_ENV'
AIRGAP_ARCHIVE_ROOT=/output/archive
AIRGAP_ENV
fi)
$(if [[ "$SINK_PROMETHEUS" == "true" ]]; then
cat << 'PROM_ENV'
PROMETHEUS_EXPORTER_PORT=9598
PROM_ENV
fi)
$(if [[ "$BUNDLE_AGENT" == "true" ]]; then
cat << AGENT_ENV
AGENT_ID=${AGENT_NAME}
COLLECTOR_ID=${AGENT_NAME}
AGENT_MODE=${AGENT_MODE}
AGENT_VENDORS=${AGENT_VENDORS}
AGENT_TOKEN=collector-agent-token
AGENT_ENV
fi)
EOF

# ── Generate vector-central.yaml ──────────────────────────────────────────────
# Build the unified Vector central parser configuration
python3 - << PYEOF
import os

target_file = "${TARGET_DIR}/vector-central.yaml"

with open("${SCRIPT_DIR}/central/vector.yaml.before-ml", "r") as f:
    base = f.read()

# Replace missing env var defaults so --no-environment validates cleanly
base = base.replace('\${KAFKA_BOOTSTRAP}', '\${KAFKA_BOOTSTRAP:-${KAFKA_BROKER}}')
base = base.replace('\${MINIO_BUCKET}', '\${MINIO_BUCKET:-${MINIO_BUCKET}}')
base = base.replace('\${MINIO_ENDPOINT}', '\${MINIO_ENDPOINT:-${MINIO_ENDPOINT}}')
base = base.replace('\${MINIO_ROOT_USER}', '\${MINIO_ROOT_USER:-${MINIO_USER}}')
base = base.replace('\${MINIO_ROOT_PASSWORD}', '\${MINIO_ROOT_PASSWORD:-${MINIO_PASSWORD}}')
base = base.replace('\${OPENSEARCH_ENDPOINT}', '\${OPENSEARCH_ENDPOINT:-${OPENSEARCH_URL}}')

# Ensure timestamp: coll_time is included in every transform for dashboard compatibility
base = base.replace('"@timestamp":   coll_time,', '"@timestamp":   coll_time,\n        "timestamp":    coll_time,')

# Add healthcheck disabled to minio_raw_lake for offline validation
base = base.replace("minio_raw_lake:\n    type: aws_s3", "minio_raw_lake:\n    type: aws_s3\n    healthcheck:\n      enabled: false")

# Insert ML Kafka sink if enabled
ml_enabled = "${WITH_ML}" == "true"
if ml_enabled:
    ml_sink = """
  # ── ML Event Feed (Downstream Anomaly Worker) ───────────────────────────
  ml_ocsf_kafka:
    type: kafka
    inputs:
      - parse_cisco_asa
      - parse_linux_auth
      - parse_paloalto_cef
      - parse_qradar_leef
      - parse_nginx_access
      - parse_cloudtrail
      - parse_k8s_audit
      - parse_iot_sensor
      - parse_postgres_db
      - parse_windows_evtx
      - parse_unknown
    bootstrap_servers: "\${KAFKA_BOOTSTRAP:-${KAFKA_BROKER}}"
    topic: "\${KAFKA_ML_TOPIC:-ulpf-ml-ocsf}"
    compression: "gzip"
    encoding:
      codec: json
    buffer:
      type: memory
      max_events: 5000
      when_full: block
"""
    base = base + ml_sink

# Append any selected modular sinks
sink_flags = {
    "01_splunk_hec_siem.yaml": "${SINK_SPLUNK}" == "true",
    "02_elasticsearch_siem.yaml": "${SINK_ELASTIC}" == "true",
    "03_clickhouse_bigdata.yaml": "${SINK_CLICKHOUSE}" == "true",
    "04_s3_data_lake.yaml": "${SINK_S3_LAKE}" == "true",
    "05_gcp_cloud_storage.yaml": "${SINK_GCP}" == "true",
    "06_azure_blob_storage.yaml": "${SINK_AZURE}" == "true",
    "07_kafka_streaming_bus.yaml": "${SINK_KAFKA}" == "true",
    "08_syslog_forwarder_siem.yaml": "${SINK_SYSLOG}" == "true",
    "09_http_webhook_soar.yaml": "${SINK_SOAR}" == "true",
    "10_airgap_local_archive.yaml": "${SINK_AIRGAP}" == "true",
    "11_prometheus_metrics.yaml": "${SINK_PROMETHEUS}" == "true",
}

sinks_dir = "${SCRIPT_DIR}/central/modules/sinks"
appended_sinks = []
appended_sources = []

for mod_name, is_enabled in sink_flags.items():
    if not is_enabled:
        continue
    mod_path = os.path.join(sinks_dir, mod_name)
    if not os.path.exists(mod_path):
        continue
    with open(mod_path, 'r') as mf:
        lines = mf.readlines()
    
    current_sec = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            continue
        if line.startswith('sources:'):
            current_sec = 'sources'
            continue
        elif line.startswith('sinks:'):
            current_sec = 'sinks'
            continue
        
        if current_sec == 'sinks':
            appended_sinks.append(line.rstrip())
        elif current_sec == 'sources':
            appended_sources.append(line.rstrip())

if appended_sources:
    base = base.replace("sources:\n", "sources:\n" + "\n".join(appended_sources) + "\n")

if appended_sinks:
    base = base + "\n" + "\n".join(appended_sinks) + "\n"

with open(target_file, "w") as f:
    f.write(base)

print("   ✔ Successfully assembled unified vector-central.yaml")
PYEOF

# Copy modular transforms and sinks into config/ for split maintenance
cp -r "${SCRIPT_DIR}/central/config/transforms/"* "${TARGET_DIR}/config/transforms/" 2>/dev/null || true
cp "${SCRIPT_DIR}/central/config/sources.yaml" "${TARGET_DIR}/config/sources.yaml" 2>/dev/null || true
cp "${SCRIPT_DIR}/central/config/sinks.yaml" "${TARGET_DIR}/config/sinks/00_core_sinks.yaml" 2>/dev/null || true

# ── Generate docker-compose.yml ───────────────────────────────────────────────
cat << EOF > "${TARGET_DIR}/docker-compose.yml"
services:

  # ── Vector Central Parser & Normalizer Engine ──────────────────────────────
  server-parser:
    image: timberio/vector:0.40.0-alpine
    container_name: ulpf-${SERVER_NAME}
    hostname: ${SERVER_NAME}
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./vector-central.yaml:/etc/vector/vector.yaml:ro
      - ./output:/output:rw
    ports:
      - "8686:8686"
$(if [[ "$SINK_PROMETHEUS" == "true" ]]; then
cat << 'PROM_PORT'
      - "9598:9598"
PROM_PORT
fi)
    command: ["--config", "/etc/vector/vector.yaml"]
    extra_hosts:
      - "host.docker.internal:host-gateway"

$(if [[ "$WITH_ML" == "true" ]]; then
cat << 'ML_SVC'
  # ── Machine Learning Anomaly Detection Worker ──────────────────────────────
  ml-worker:
    build:
      context: ../../ml
    container_name: ulpf-ml-worker
    command:
      - ulpf-ml
      - worker
      - --models
      - /app/models
      - --state
      - /state/worker.sqlite
    env_file:
      - .env
    volumes:
      - ml-state:/state
    restart: on-failure
    mem_limit: 768m
    cpus: 1.0
ML_SVC
fi)

$(if [[ "$WITH_CONFIG_SERVER" == "true" ]]; then
cat << 'CS_SVC'
  # ── Central Fleet Config Server ────────────────────────────────────────────
  config-server:
    build:
      context: ../../config-server
    container_name: ulpf-config-server
    ports:
      - "8080:8080"
    volumes:
      - ../../config-repo:/opt/ulpf-config.git:ro
      - config-server-data:/data
    environment:
      - ADMIN_TOKEN=admin-token
      - AGENT_TOKENS=central-token:server-parser:kol-dc1,collector-agent-token:agent-local-01:kol-dc1
    restart: unless-stopped
CS_SVC
fi)

$(if [[ "$DEPLOY_MODE" == "standalone" ]]; then
cat << 'STANDALONE_INFRA'
  # ── Dedicated Kafka Broker (KRaft Mode) ────────────────────────────────────
  kafka:
    image: apache/kafka:3.7.0
    container_name: ulpf-kafka
    hostname: kafka
    ports:
      - "9092:9092"
    environment:
      - KAFKA_NODE_ID=1
      - KAFKA_PROCESS_ROLES=broker,controller
      - KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
      - KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      - KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:9093
      - KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_AUTO_CREATE_TOPICS_ENABLE=true
      - CLUSTER_ID=ulpf-standalone-kafka-001
    volumes:
      - kafka-data:/var/lib/kafka/data

  # ── Dedicated OpenSearch ───────────────────────────────────────────────────
  opensearch:
    image: opensearchproject/opensearch:2.12.0
    container_name: ulpf-opensearch
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - opensearch-data:/usr/share/opensearch/data

  # ── Dedicated OpenSearch Dashboards ────────────────────────────────────────
  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:2.12.0
    container_name: ulpf-dashboards
    ports:
      - "5601:5601"
    environment:
      - 'OPENSEARCH_HOSTS=["http://opensearch:9200"]'
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    depends_on:
      - opensearch

  # ── Dedicated MinIO S3 Object Lake ─────────────────────────────────────────
  minio:
    image: minio/minio:RELEASE.2024-08-03T04-33-23Z
    container_name: ulpf-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio-data:/data
STANDALONE_INFRA
fi)

$(if [[ "$BUNDLE_AGENT" == "true" ]]; then
cat << BUNDLED_AGENT_SVC
  # ── Bundled Edge Collection Agent ──────────────────────────────────────────
  collector-agent:
    image: timberio/vector:0.40.0-alpine
    container_name: ulpf-${AGENT_NAME}
    hostname: ${AGENT_NAME}
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./vector-agent.yaml:/etc/vector/vector.yaml:ro
      - ./logs:/logs:rw
    ports:
      - "8687:8686"
$(if [[ "$AGENT_MODE" == "syslog" || "$AGENT_MODE" == "dual" ]]; then
cat << 'AGENT_SYS_PORT'
      - "1514:1514/udp"
      - "1514:1514/tcp"
AGENT_SYS_PORT
fi)
    command: ["--config", "/etc/vector/vector.yaml"]
    extra_hosts:
      - "host.docker.internal:host-gateway"
BUNDLED_AGENT_SVC
fi)

volumes:
  output-data:
$(if [[ "$WITH_ML" == "true" ]]; then echo "  ml-state:"; fi)
$(if [[ "$WITH_CONFIG_SERVER" == "true" ]]; then echo "  config-server-data:"; fi)
$(if [[ "$DEPLOY_MODE" == "standalone" ]]; then
cat << 'STANDALONE_VOLS'
  kafka-data:
  opensearch-data:
  minio-data:
STANDALONE_VOLS
fi)
EOF

# ── Generate Bundled Agent Config (If Enabled) ────────────────────────────────
if [[ "$BUNDLE_AGENT" == "true" ]]; then
  echo -e "   ${BLUE}Generating bundled agent configuration...${RESET}"
  mkdir -p "${TARGET_DIR}/logs/syslog"
  mkdir -p "${TARGET_DIR}/logs/cef"
  mkdir -p "${TARGET_DIR}/logs/json"
  mkdir -p "${TARGET_DIR}/logs/xml"
  mkdir -p "${TARGET_DIR}/logs/csv"
  mkdir -p "${TARGET_DIR}/logs/debug"
  mkdir -p "${TARGET_DIR}/sample-logs"

  # Invoke install-agent.sh in non-interactive mode targeting temporary location or generate agent yaml
  ./install-agent.sh \
    --name "${AGENT_NAME}" \
    --site "${SITE_ID}" \
    --kafka "${KAFKA_BROKER}" \
    --topic "${KAFKA_TOPIC}" \
    --config-server "http://localhost:8080" \
    --mode "${AGENT_MODE}" \
    --vendors "${AGENT_VENDORS}" \
    --non-interactive >/dev/null 2>&1 || true

  # Copy generated agent artifacts into server directory
  if [[ -f "${SCRIPT_DIR}/deployment/${AGENT_NAME}/vector.yaml" ]]; then
    cp "${SCRIPT_DIR}/deployment/${AGENT_NAME}/vector.yaml" "${TARGET_DIR}/vector-agent.yaml"
    cp -r "${SCRIPT_DIR}/deployment/${AGENT_NAME}/sample-logs/"* "${TARGET_DIR}/sample-logs/" 2>/dev/null || true
    rm -rf "${SCRIPT_DIR}/deployment/${AGENT_NAME}"
    echo "   ✔ Bundled agent configuration created: vector-agent.yaml"
  fi
fi

# ── Generate run.sh Management Script ─────────────────────────────────────────
cat << 'RUN_EOF' > "${TARGET_DIR}/run.sh"
#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DIR}"

ACTION="${1:-start}"

case "${ACTION}" in
  start|up)
    echo "Starting ULPF Central Server stack via Docker Compose..."
    docker compose up -d
    echo ""
    echo "Stack services started. Current status:"
    docker compose ps
    echo ""
    echo "To follow logs: ./run.sh logs"
    ;;
  stop|down)
    echo "Stopping ULPF Central Server stack..."
    docker compose down
    ;;
  restart)
    echo "Restarting stack..."
    docker compose restart
    ;;
  status)
    echo "=== Container Status ==="
    docker compose ps
    echo ""
    echo "=== Vector Central Engine API ==="
    curl -s http://localhost:8686/health || echo "Vector API unreachable on port 8686"
    ;;
  logs)
    docker compose logs -f "${2:-server-parser}"
    ;;
  validate)
    echo "Validating Vector Central configuration..."
    docker run --rm -v "${DIR}/vector-central.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml
    echo "[OK] vector-central.yaml is valid."
    if [[ -f "${DIR}/vector-agent.yaml" ]]; then
      echo "Validating Bundled Vector Agent configuration..."
      docker run --rm -v "${DIR}/vector-agent.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml
      echo "[OK] vector-agent.yaml is valid."
    fi
    ;;
  test-event)
    echo "Checking /output/ocsf-events.ndjson for live normalized events..."
    if [[ -f "${DIR}/output/ocsf-events.ndjson" ]]; then
      tail -n 3 "${DIR}/output/ocsf-events.ndjson" | jq . || tail -n 3 "${DIR}/output/ocsf-events.ndjson"
    else
      echo "No output yet. Ensure server-parser is running via ./run.sh start and receiving logs from Kafka."
    fi
    ;;
  *)
    echo "Usage: ./run.sh [start | stop | restart | status | logs | validate | test-event]"
    exit 1
    ;;
esac
RUN_EOF
chmod +x "${TARGET_DIR}/run.sh"

# ── Generate README.md ────────────────────────────────────────────────────────
cat << EOF > "${TARGET_DIR}/README.md"
# ULPF Central Server Deployment — ${SERVER_NAME}

- **Server Identifier**: \`${SERVER_NAME}\`
- **Primary Site**: \`${SITE_ID}\`
- **Deployment Mode**: \`${DEPLOY_MODE}\`
- **Kafka Broker**: \`${KAFKA_BROKER}\`
- **Raw Log Topic**: \`${KAFKA_TOPIC}\`
- **OpenSearch SIEM**: \`${OPENSEARCH_URL}\`
- **MinIO S3 Raw Lake**: \`${MINIO_ENDPOINT}/${MINIO_BUCKET}\`
- **ML Anomaly Worker**: \`${WITH_ML}\`
- **Fleet Config Server**: \`${WITH_CONFIG_SERVER}\`
- **Bundled Agent**: \`${BUNDLE_AGENT}\`

---

## Active Modular Sinks

| Sink ID | Sink Module Name | Status | Destination / Purpose |
| :--- | :--- | :--- | :--- |
| **Core** | OpenSearch SIEM | **ACTIVE** | \`${OPENSEARCH_URL}\` (\`${OPENSEARCH_INDEX}-YYYY.MM.DD\`) |
| **Core** | MinIO S3 Raw Lake | **ACTIVE** | \`${MINIO_ENDPOINT}/${MINIO_BUCKET}\` (Forensic preservation) |
| **Core** | Local OCSF NDJSON | **ACTIVE** | \`./output/ocsf-events.ndjson\` |
| **Core** | ML Feedback Stream | **$([ "$WITH_ML" == "true" ] && echo "ACTIVE" || echo "DISABLED")** | Topic \`ulpf-ml-ocsf\` |
| **01** | Splunk HEC SIEM | **$([ "$SINK_SPLUNK" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Splunk Enterprise / Cloud HEC JSON streaming |
| **02** | Elasticsearch SIEM | **$([ "$SINK_ELASTIC" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | External Elasticsearch 7.x/8.x cluster bulk indexing |
| **03** | ClickHouse Big Data OLAP | **$([ "$SINK_CLICKHOUSE" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | High-speed columnar analytics (billions of events/day) |
| **04** | AWS S3 Forensic Lake | **$([ "$SINK_S3_LAKE" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | External AWS S3 / MinIO data lake for Athena/Spark |
| **05** | Google Cloud Storage | **$([ "$SINK_GCP" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | GCS bucket for Google Chronicle SIEM & BigQuery |
| **06** | Azure Blob Storage | **$([ "$SINK_AZURE" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Azure Blob container for Microsoft Sentinel SIEM |
| **07** | Downstream Kafka Bus | **$([ "$SINK_KAFKA" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Secondary Kafka topic for inter-SOC federation & ML |
| **08** | Syslog Forwarder | **$([ "$SINK_SYSLOG" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | TCP/TLS forwarding to legacy SIEMs (ArcSight/QRadar) |
| **09** | SOAR Webhook | **$([ "$SINK_SOAR" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Automated webhook dispatch to Cortex XSOAR / Splunk SOAR |
| **10** | Air-Gapped WORM Archive | **$([ "$SINK_AIRGAP" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Rotating hourly gzip archives for air-gapped networks |
| **11** | Prometheus Metrics | **$([ "$SINK_PROMETHEUS" == "true" ] && echo "ACTIVE" || echo "INACTIVE")** | Metrics exporter on port 9598 for Grafana dashboards |

---

## Directory Structure

\`\`\`
deployment/${SERVER_NAME}/
├── .env                     # Runtime environment variables
├── docker-compose.yml       # Container services definition
├── vector-central.yaml      # Consolidated Vector Central Parser & Sinks config
├── config/                  # Modular configuration components
│   ├── sources.yaml         # Kafka raw consumer
│   ├── transforms/          # OCSF v1.3.0 transforms (11 format parsers)
│   └── sinks/               # Active sink configurations
├── modules/                 # Complete library of 11 modular sinks + documentation
├── run.sh                   # Server management script (start/stop/status/validate)
├── output/                  # Normalized OCSF output stream
$(if [[ "$BUNDLE_AGENT" == "true" ]]; then
cat << 'AGENT_TREE'
├── vector-agent.yaml        # Bundled edge collector configuration
├── sample-logs/             # Curated test logs for agent validation
└── logs/                    # Local directories monitored by agent
AGENT_TREE
fi)
\`\`\`

---

## Quick Start Commands

\`\`\`bash
# 1. Enter deployment directory
cd deployment/${SERVER_NAME}

# 2. Validate Vector configuration
./run.sh validate

# 3. Start the server stack
./run.sh start

# 4. Check status & live logs
./run.sh status
./run.sh logs
\`\`\`
EOF

# ── Validate Generated Vector Configurations ──────────────────────────────────
echo -e "\n${CYAN}Running syntax and schema validation with Vector engine...${RESET}"
docker run --rm -v "${TARGET_DIR}/vector-central.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml > /dev/null 2>&1
echo -e "   ${GREEN}✔ vector-central.yaml validated successfully with zero errors.${RESET}"

if [[ "$BUNDLE_AGENT" == "true" && -f "${TARGET_DIR}/vector-agent.yaml" ]]; then
  docker run --rm -v "${TARGET_DIR}/vector-agent.yaml:/etc/vector/vector.yaml:ro" timberio/vector:0.40.0-alpine validate --no-environment /etc/vector/vector.yaml > /dev/null 2>&1
  echo -e "   ${GREEN}✔ vector-agent.yaml validated successfully with zero errors.${RESET}"
fi

echo -e "\n================================================================================"
echo -e "  ${BOLD}${GREEN}ULPF Server Deployment Generated Successfully!${RESET}"
echo -e "================================================================================"
echo -e "  Location   : ${BOLD}${TARGET_DIR}${RESET}"
echo -e "  Sinks      : ${CYAN}Core (OpenSearch + MinIO + Local + ML)${RESET}"
if [[ "$SINK_SPLUNK" == "true" ]]; then echo -e "               ${CYAN}+ Splunk HEC SIEM${RESET}"; fi
if [[ "$SINK_ELASTIC" == "true" ]]; then echo -e "               ${CYAN}+ Elasticsearch SIEM${RESET}"; fi
if [[ "$SINK_CLICKHOUSE" == "true" ]]; then echo -e "               ${CYAN}+ ClickHouse Big Data OLAP${RESET}"; fi
if [[ "$SINK_S3_LAKE" == "true" ]]; then echo -e "               ${CYAN}+ AWS S3 / MinIO Data Lake${RESET}"; fi
if [[ "$SINK_GCP" == "true" ]]; then echo -e "               ${CYAN}+ Google Cloud Storage${RESET}"; fi
if [[ "$SINK_AZURE" == "true" ]]; then echo -e "               ${CYAN}+ Azure Blob Storage${RESET}"; fi
if [[ "$SINK_KAFKA" == "true" ]]; then echo -e "               ${CYAN}+ Downstream Kafka Bus${RESET}"; fi
if [[ "$SINK_SYSLOG" == "true" ]]; then echo -e "               ${CYAN}+ TCP/TLS Syslog Forwarder${RESET}"; fi
if [[ "$SINK_SOAR" == "true" ]]; then echo -e "               ${CYAN}+ SOAR Automation Webhook${RESET}"; fi
if [[ "$SINK_AIRGAP" == "true" ]]; then echo -e "               ${CYAN}+ Air-Gapped Immutable WORM Archive${RESET}"; fi
if [[ "$SINK_PROMETHEUS" == "true" ]]; then echo -e "               ${CYAN}+ Prometheus Metrics Exporter (port 9598)${RESET}"; fi
if [[ "$BUNDLE_AGENT" == "true" ]]; then
  echo -e "  Agent      : ${GREEN}Bundled (${AGENT_NAME}, mode: ${AGENT_MODE}, vendors: ${AGENT_VENDORS})${RESET}"
else
  echo -e "  Agent      : ${DIM}Not bundled (server-only)${RESET}"
fi
echo -e "--------------------------------------------------------------------------------"
echo -e "  To launch the deployment:"
echo -e "    ${BOLD}cd ${TARGET_DIR}${RESET}"
echo -e "    ${BOLD}./run.sh start${RESET}"
echo -e "================================================================================\n"
