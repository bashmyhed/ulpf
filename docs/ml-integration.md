# ML Pipeline Integration

The ML component is an additive consumer of normalized OCSF events. It does not
replace collection, integrity verification, raw preservation, or the existing
OpenSearch OCSF index.

```
collectors → ulpf-raw-logs → central parser → ulpf-ocsf-events → ml-worker → ulpf-ml-findings
                                      ├→ MinIO raw preservation
                                      ├→ /output/ocsf-events.ndjson
                                      └→ ulpf-ocsf-YYYY.MM.DD
```

## Deployment

From the repository root, start the normal stack and ML overlay together:

```bash
docker compose -f docker-compose.yml -f docker-compose.ml.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.ml.yml ps
docker compose -f docker-compose.yml -f docker-compose.ml.yml logs --tail=200 ml-worker
```

`kafka-setup` provisions `ulpf-ocsf-events` before the worker starts. The
central parser sends a JSON copy of every normalized event to that topic through
the `ml_ocsf_kafka` sink. Its existing file, MinIO, console, and OpenSearch
sinks remain enabled.

## Findings contract

The worker writes deterministic window documents to the OpenSearch index
`ulpf-ml-findings`. Important fields include `status`, `family`, `event_ids`,
`start`, `end`, and `rule_signals`.

- `scored`: a trained family model produced a score; `is_anomaly` is a
  behavioral anomaly decision, not an attack probability.
- `not_scored` and `insufficient_data`: no inference conclusion; they are not
  benign verdicts.
- `data_quality`: an event was rejected or dropped. An event explicitly marked
  `metadata.integrity.verified: false` is recorded as
  `integrity_verification_failed` and is never scored.

Only DNS and HTTP have shipped trained models. Authentication and generic
network findings can carry explicit rule signals but are not ML detections.

## Operations

Run exactly one `ml-worker` against its persistent `ml-state` volume. It owns
SQLite window/checkpoint state and is not safe to scale horizontally without
partitioned state. Its Compose health check reads `/state/health.json`; inspect
that file or worker logs when it is unhealthy.

The ML worker uses event-time 60-second windows with 30 seconds of allowed
lateness. A final quiet window closes only after a newer event advances the
watermark, so replay tests should use the offline scoring command described in
[`ml/README.md`](../ml/README.md). Keep the models and the state volume across
ordinary restarts.
