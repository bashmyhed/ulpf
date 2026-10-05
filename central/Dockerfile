FROM timberio/vector:0.40.0-alpine

# Install bash and curl for network checks
RUN apk add --no-cache bash curl

WORKDIR /app

# Copy config-agent binary
COPY config-agent /usr/local/bin/config-agent

# Copy validated central parser config and entrypoint
COPY vector.yaml /etc/vector/vector.yaml
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Environment variables with sensible defaults
ENV VECTOR_LOG=info \
    KAFKA_BOOTSTRAP=kafka:9092 \
    MINIO_ENDPOINT=http://minio:9000 \
    MINIO_BUCKET=ulpf-data-lake \
    MINIO_ROOT_USER=minioadmin \
    MINIO_ROOT_PASSWORD=minioadmin

ENTRYPOINT ["/entrypoint.sh"]
CMD ["vector", "--config", "/etc/vector/vector.yaml"]