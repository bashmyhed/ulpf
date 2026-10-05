FROM timberio/vector:0.40.0-alpine

# Install Python 3 and bash for mock emulators and entrypoint
RUN apk add --no-cache bash python3

WORKDIR /app

# Copy config-agent binary
COPY config-agent /usr/local/bin/config-agent

# Copy Vector collector configuration
COPY vector.yaml /etc/vector/vector.yaml

# Copy mock generator scripts
COPY mocks/ /app/mocks/

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/mocks/*.py

# Environment defaults
ENV VECTOR_LOG=info \
    KAFKA_BOOTSTRAP=kafka:9092 \
    COLLECTOR_ID=collector-c \
    SITE_ID=kol-dc1 \
    INSTANCE_ENV=production \
    MOCK_MODE=false

ENTRYPOINT ["/entrypoint.sh"]
CMD ["vector", "--config", "/etc/vector/vector.yaml"]