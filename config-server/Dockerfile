FROM golang:1.21-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY . .

# Build
RUN CGO_ENABLED=0 go build -o /config-server ./cmd/server

# Final stage
FROM alpine:3.18

RUN apk add --no-cache ca-certificates git bash curl python3 py3-pip

# Install pyyaml for envelope validation
RUN pip3 install --break-system-packages pyyaml

# Install Vector for validation
RUN curl -sSL https://sh.vector.dev | bash -s -- -y
ENV PATH="/root/.vector/bin:${PATH}"

WORKDIR /app

COPY --from=builder /config-server /usr/local/bin/config-server

# Copy validation script
COPY validate_envelope.py /usr/local/bin/validate_envelope.py
RUN chmod +x /usr/local/bin/validate_envelope.py

# Create secrets directory
RUN mkdir -p /etc/ulpf/secrets /data

EXPOSE 8080

ENTRYPOINT ["config-server"]
CMD ["-repo", "/opt/ulpf-config.git", "-secrets", "/etc/ulpf/secrets", "-addr", ":8080", "-status-file", "/data/fleet-status.json"]