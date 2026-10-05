#!/bin/bash
set -e

echo "=========================================================="
echo "  ULPF Collector Instance B (Structured JSON & CSV)"
echo "=========================================================="
echo "  Collector ID    : ${COLLECTOR_ID:-collector-b}"
echo "  Site ID         : ${SITE_ID:-kol-dc1}"
echo "  Kafka Bootstrap : ${KAFKA_BOOTSTRAP:-kafka:9092}"
echo "  Mock Mode       : ${MOCK_MODE:-false}"
echo "  Config Server   : ${CONFIG_SERVER_URL:-http://config-server:8080}"
echo "=========================================================="

mkdir -p /logs/json /logs/csv /logs/debug
mkdir -p /run

# Start config-agent in background
echo "[collector-b] Starting config-agent..."
config-agent &
AGENT_PID=$!
echo "[collector-b] Config-agent started (PID: $AGENT_PID)"

# Wait a moment for initial config fetch
sleep 3

# If mock mode enabled, start background mock log generators
if [ "$MOCK_MODE" = "true" ] || [ "$MOCK_MODE" = "1" ]; then
  echo "[collector-b] Starting mock emulators (Poisson streaming)..."
  python3 /app/mocks/nginx_access.py    --rate 2 --mode file --output /logs/json/nginx.log &
  python3 /app/mocks/cloudtrail_json.py --rate 1 --mode file --output /logs/json/cloudtrail.log &
  python3 /app/mocks/k8s_audit.py       --rate 1 --mode file --output /logs/json/k8s_audit.log &
  python3 /app/mocks/iot_sensor.py      --rate 2 --mode file --output /logs/json/iot.log &
  python3 /app/mocks/db_postgres.py     --rate 2 --mode file --output /logs/csv/postgres.csv &
  echo "[collector-b] Mock generators active in background."
fi

# Start Vector with config from managed directory
echo "[collector-b] Starting Vector..."
vector --config-dir /etc/vector &
VECTOR_PID=$!
echo $VECTOR_PID > /run/vector.pid
echo "[collector-b] Vector started (PID: $VECTOR_PID)"

# Wait for Vector to exit
wait $VECTOR_PID
VECTOR_EXIT=$?

# Stop config-agent
kill $AGENT_PID 2>/dev/null || true

exit $VECTOR_EXIT