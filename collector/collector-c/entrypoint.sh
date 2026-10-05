#!/bin/bash
set -e

echo "=========================================================="
echo "  ULPF Collector Instance C (Windows EVTX XML)"
echo "=========================================================="
echo "  Collector ID    : ${COLLECTOR_ID:-collector-c}"
echo "  Site ID         : ${SITE_ID:-kol-dc1}"
echo "  Kafka Bootstrap : ${KAFKA_BOOTSTRAP:-kafka:9092}"
echo "  Mock Mode       : ${MOCK_MODE:-false}"
echo "  Config Server   : ${CONFIG_SERVER_URL:-http://config-server:8080}"
echo "=========================================================="

mkdir -p /logs/xml /logs/syslog /logs/debug
mkdir -p /run

# Start config-agent in background
echo "[collector-c] Starting config-agent..."
config-agent &
AGENT_PID=$!
echo "[collector-c] Config-agent started (PID: $AGENT_PID)"

# Wait a moment for initial config fetch
sleep 3

# If mock mode enabled, start background mock log generator
if [ "$MOCK_MODE" = "true" ] || [ "$MOCK_MODE" = "1" ]; then
  echo "[collector-c] Starting Windows Event mock emulator (Poisson streaming)..."
  python3 /app/mocks/windows_event.py --rate 2 --mode file --output /logs/xml/windows_events.log &
  echo "[collector-c] Windows Event mock generator active in background."
fi

# Start Vector with config from managed directory
echo "[collector-c] Starting Vector..."
vector --config-dir /etc/vector &
VECTOR_PID=$!
echo $VECTOR_PID > /run/vector.pid
echo "[collector-c] Vector started (PID: $VECTOR_PID)"

# Wait for Vector to exit
wait $VECTOR_PID
VECTOR_EXIT=$?

# Stop config-agent
kill $AGENT_PID 2>/dev/null || true

exit $VECTOR_EXIT