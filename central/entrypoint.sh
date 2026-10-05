#!/bin/bash
set -e

echo "=========================================================="
echo "  NTRO ULPF Central Log Processor & Normalizer"
echo "=========================================================="
echo "  Kafka Bootstrap : ${KAFKA_BOOTSTRAP:-kafka:9092}"
echo "  MinIO Endpoint  : ${MINIO_ENDPOINT:-http://minio:9000}"
echo "  MinIO Bucket    : ${MINIO_BUCKET:-ulpf-data-lake}"
echo "  Config Server   : ${CONFIG_SERVER_URL:-http://config-server:8080}"
echo "=========================================================="

mkdir -p /run

# Start config-agent in background
echo "[central-parser] Starting config-agent..."
config-agent &
AGENT_PID=$!
echo "[central-parser] Config-agent started (PID: $AGENT_PID)"

# Wait a moment for initial config fetch
sleep 3

# Check MinIO connectivity if endpoint provided
if [ -n "$MINIO_ENDPOINT" ]; then
  echo "[central-parser] Verifying MinIO connectivity at ${MINIO_ENDPOINT}/minio/health/live..."
  for i in $(seq 1 30); do
    if curl -s "${MINIO_ENDPOINT}/minio/health/live" >/dev/null 2>&1; then
      echo "[central-parser] MinIO is reachable and healthy."
      break
    fi
    echo "[central-parser] Waiting for MinIO... ($i/30)"
    sleep 2
  done
fi

# Start Vector with config from managed directory
echo "[central-parser] Starting Vector..."
vector --config-dir /etc/vector &
VECTOR_PID=$!
echo $VECTOR_PID > /run/vector.pid
echo "[central-parser] Vector started (PID: $VECTOR_PID)"

# Wait for Vector to exit
wait $VECTOR_PID
VECTOR_EXIT=$?

# Stop config-agent
kill $AGENT_PID 2>/dev/null || true

exit $VECTOR_EXIT