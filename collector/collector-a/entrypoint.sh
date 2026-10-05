#!/bin/bash
set -e

echo "=========================================================="
echo "  ULPF Collector Instance A (Syslog / CEF / LEEF)"
echo "=========================================================="
echo "  Collector ID    : ${COLLECTOR_ID:-collector-a}"
echo "  Site ID         : ${SITE_ID:-kol-dc1}"
echo "  Kafka Bootstrap : ${KAFKA_BOOTSTRAP:-kafka:9092}"
echo "  Mock Mode       : ${MOCK_MODE:-false}"
echo "  Config Server   : ${CONFIG_SERVER_URL:-http://config-server:8080}"
echo "=========================================================="

mkdir -p /logs/syslog /logs/cef /logs/raw /logs/debug
mkdir -p /run

# Start config-agent in background
echo "[collector-a] Starting config-agent..."
config-agent &
AGENT_PID=$!
echo "[collector-a] Config-agent started (PID: $AGENT_PID)"

# Wait a moment for initial config fetch
sleep 3

# If mock mode enabled, start background mock log generators
if [ "$MOCK_MODE" = "true" ] || [ "$MOCK_MODE" = "1" ]; then
  echo "[collector-a] Starting mock emulators (Poisson streaming)..."
  python3 /app/mocks/cisco_asa_syslog.py --rate 2 --mode file --output /logs/syslog/cisco_asa.log &
  python3 /app/mocks/linux_auth.py        --rate 2 --mode file --output /logs/syslog/linux_auth.log &
  python3 /app/mocks/firewall_cef.py      --rate 2 --mode file --output /logs/cef/paloalto.log &
  python3 /app/mocks/leef_qradar.py       --rate 2 --mode file --output /logs/raw/qradar.log &
  echo "[collector-a] Mock generators active in background."
fi

# Start Vector with config from managed directory
echo "[collector-a] Starting Vector..."
vector --config-dir /etc/vector &
VECTOR_PID=$!
echo $VECTOR_PID > /run/vector.pid
echo "[collector-a] Vector started (PID: $VECTOR_PID)"

# Wait for Vector to exit
wait $VECTOR_PID
VECTOR_EXIT=$?

# Stop config-agent
kill $AGENT_PID 2>/dev/null || true

exit $VECTOR_EXIT