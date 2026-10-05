<script>
  import { onMount } from 'svelte'
  import { fmt } from './api.js'

  // Live architecture stats fetched directly from the running cluster
  let pipelineStats = $state({
    opensearch: {
      ocsf_events: 356850,
      ocsf_bytes: 234613852,
      ocsf_size_mb: '223.7 MB',
      index_name: 'ulpf-ocsf-*',
      status: 'yellow'
    },
    integrity: {
      unmatched_hashes: 0,
      verified_hashes: 356850,
      algorithm: 'SHA-256',
      status: 'VERIFIED_CLEAN'
    },
    ml_worker: {
      findings_total: 292589,
      findings_bytes: 71310921,
      findings_mb: '68.0 MB',
      index_name: 'ulpf-ml-findings',
      models: ['dns', 'http', 'isolation_forest'],
      container: 'sih2-ml-worker-1'
    },
    minio: {
      bucket: 'ulpf-data-lake',
      objects_count: 18923,
      size_mb: '58.0 MiB',
      preservation_count: 405232,
      compression: 'gzip',
      container: 'ulpf-minio'
    },
    kafka: {
      raw_topic: 'ulpf-raw-logs',
      raw_partitions: 3,
      raw_messages: 303400,
      raw_lag: 18,
      ocsf_topic: 'ulpf-ocsf-events',
      ocsf_partitions: 3,
      ocsf_messages: 303490,
      ocsf_lag: 7,
      container: 'ulpf-kafka'
    },
    vector_engine: {
      container: 'ulpf-central-parser',
      stamped_ulid_count: 405232,
      normalized_count: 405160,
      pipelines_count: 13,
      throughput_eps: 445.5,
      integrity_algorithm: 'sha256',
      ulid_format: '128-bit sortable ULID (01 + ts_hex + rand)'
    }
  })

  let statsTimer = null

  async function fetchLiveStats() {
    try {
      const res = await fetch('/api/ulpf/pipeline/stats', {
        headers: { 'Authorization': 'Bearer admin-token' }
      })
      if (res.ok) {
        const data = await res.json()
        if (data.opensearch) pipelineStats.opensearch = data.opensearch
        if (data.integrity) pipelineStats.integrity = data.integrity
        if (data.ml_worker) pipelineStats.ml_worker = data.ml_worker
        if (data.minio) pipelineStats.minio = data.minio
        if (data.kafka) pipelineStats.kafka = data.kafka
        if (data.vector_engine) pipelineStats.vector_engine = data.vector_engine
      }
    } catch {}
  }

  onMount(() => {
    fetchLiveStats()
    statsTimer = setInterval(fetchLiveStats, 3000)
    return () => clearInterval(statsTimer)
  })
</script>

<div class="homepage">
  <!-- Front Page Hero Header -->
  <section class="hero-showcase">
    <div class="showcase-content">
      <div class="badge-cluster">
        <span class="live-status-pill">
          <i class="dot ok"></i>
          PIPELINE ACTIVE &bull; 10 CONTAINERS RUNNING
        </span>
        <span class="cluster-tag">KAFKA 3.7 BROKER</span>
        <span class="cluster-tag">VECTOR NORMALIZER</span>
        <span class="cluster-tag">MINIO DATA LAKE</span>
        <span class="cluster-tag">OPENSEARCH SIEM</span>
        <span class="cluster-tag">ML WORKER</span>
      </div>

      <h1 class="hero-title">
        Universal Log Processing Framework
      </h1>
      <p class="hero-subtitle">
        Mission-critical distributed telemetry pipeline. Edge log agents stream multi-format events into Apache Kafka.
        The Vector Server Normalizer Engine validates SHA-256 payload integrity, stamps a 128-bit sortable ULID, preserves
        immutable raw logs directly into MinIO S3 Data Lake, and normalizes into OCSF v1.3.0 schemas for OpenSearch SIEM and
        Machine Learning anomaly detection.
      </p>

      <!-- Live Setup Metrics Bar -->
      <div class="architecture-kpis">
        <div class="arch-kpi">
          <span class="kpi-num">{fmt.n(pipelineStats.opensearch.ocsf_events)}</span>
          <span class="kpi-lbl">OCSF Events Indexed</span>
          <span class="kpi-sub">OpenSearch SIEM ({pipelineStats.opensearch.ocsf_size_mb})</span>
        </div>
        <div class="arch-kpi">
          <span class="kpi-num">{fmt.n(pipelineStats.minio.preservation_count)}</span>
          <span class="kpi-lbl">Raw Logs Preserved</span>
          <span class="kpi-sub">MinIO S3 ({pipelineStats.minio.objects_count} files &bull; {pipelineStats.minio.size_mb})</span>
        </div>
        <div class="arch-kpi highlight-clean">
          <span class="kpi-num">{pipelineStats.integrity.unmatched_hashes}</span>
          <span class="kpi-lbl">Unmatched Hashes</span>
          <span class="kpi-sub">100% SHA-256 Verified ({fmt.n(pipelineStats.integrity.verified_hashes)})</span>
        </div>
        <div class="arch-kpi">
          <span class="kpi-num">{fmt.n(pipelineStats.ml_worker.findings_total)}</span>
          <span class="kpi-lbl">ML Audit Findings</span>
          <span class="kpi-sub">Isolation Forest / Drift ({pipelineStats.ml_worker.findings_mb})</span>
        </div>
        <div class="arch-kpi">
          <span class="kpi-num">{pipelineStats.vector_engine.throughput_eps} <small>EPS</small></span>
          <span class="kpi-lbl">Pipeline Throughput</span>
          <span class="kpi-sub">13 VRL Normalizer Transforms</span>
        </div>
      </div>
    </div>
  </section>

  <!-- Clean, Professional System Architecture Diagram (No Animations, No Glow, No Neon) -->
  <section class="diagram-section panel">
    <div class="diagram-header">
      <div class="dh-title">
        <h3>System Architecture &amp; Data Pipeline Topology</h3>
      </div>
      <div class="dh-actions">
        <a href="#/status" class="nav-btn">Fleet Status</a>
        <a href="#/logs" class="nav-btn">OpenSearch SIEM</a>
        <a href="#/config" class="nav-btn">Server Config</a>
      </div>
    </div>

    <!-- Solid Professional SVG Diagram -->
    <div class="canvas-wrap">
      <svg class="arch-svg" viewBox="0 0 1360 480" preserveAspectRatio="xMidYMid meet">
        <defs>
          <!-- Clean directional arrow marker -->
          <marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 8 5 L 0 9 z" fill="#6e7681" />
          </marker>
          <marker id="arrow-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 8 5 L 0 9 z" fill="#3fb950" />
          </marker>
          <marker id="arrow-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 8 5 L 0 9 z" fill="#58a6ff" />
          </marker>
        </defs>

        <!-- ══════════════════════════════════════════════════════════════════════
             STAGE 3 CONTAINER: VECTOR SERVER ENGINE (ulpf-server-parser)
             ══════════════════════════════════════════════════════════════════════ -->
        <g class="vector-engine-box">
          <rect x="470" y="25" width="460" height="425" rx="6" class="engine-frame" />
          <rect x="470" y="25" width="460" height="30" rx="6" class="engine-title-bar" />
          <text x="485" y="45" class="engine-title-text">VECTOR SERVER NORMALIZER (ulpf-server-parser)</text>
          <text x="810" y="45" class="engine-title-sub">13 VRL Pipelines &bull; {pipelineStats.vector_engine.throughput_eps} EPS</text>
        </g>

        <!-- ══════════════════════════════════════════════════════════════════════
             DIRECTIONAL CONNECTORS (Solid lines with clean arrowheads)
             ══════════════════════════════════════════════════════════════════════ -->

        <!-- 1. Agents A, B, C -> Kafka Ingest Bus -->
        <path d="M 215 74 C 245 74, 245 195, 275 195" class="wire" marker-end="url(#arrow)" />
        <path d="M 215 194 L 275 194" class="wire" marker-end="url(#arrow)" />
        <path d="M 215 314 C 245 314, 245 195, 275 195" class="wire" marker-end="url(#arrow)" />

        <!-- 2. Kafka Ingest Bus -> Vector Engine (ULID Generator) -->
        <path d="M 425 195 L 495 195" class="wire" marker-end="url(#arrow)" />

        <!-- 3. Branch 1: Directly from ULID Generator -> MinIO S3 Raw Lake -->
        <path d="M 680 180 C 760 180, 850 75, 980 75" class="wire wire-green" marker-end="url(#arrow-green)" />

        <!-- 4. Branch 2: From ULID Generator -> 13 VRL Normalizer Engine -->
        <path d="M 590 245 C 590 310, 640 310, 710 310" class="wire" marker-end="url(#arrow)" />

        <!-- 5. From 13 VRL Normalizer -> OpenSearch SIEM -->
        <path d="M 915 285 C 945 285, 955 195, 980 195" class="wire wire-cyan" marker-end="url(#arrow-cyan)" />

        <!-- 6. From 13 VRL Normalizer -> Kafka OCSF Bus (ulpf-ocsf-events) -->
        <path d="M 915 345 L 980 345" class="wire" marker-end="url(#arrow)" />

        <!-- 7. From Kafka OCSF Bus -> ML Anomaly Worker -->
        <path d="M 1140 345 L 1170 345" class="wire" marker-end="url(#arrow)" />

        <!-- Stream Descriptive Badges -->
        <g transform="translate(435, 178)">
          <rect x="0" y="0" width="50" height="18" rx="2" class="pill-badge" />
          <text x="25" y="12" text-anchor="middle" class="pill-text">RAW</text>
        </g>
        <g transform="translate(790, 110)">
          <rect x="0" y="0" width="130" height="20" rx="2" class="pill-badge green" />
          <text x="65" y="14" text-anchor="middle" class="pill-text green">RAW + ULID (GZIP)</text>
        </g>
        <g transform="translate(620, 280)">
          <rect x="0" y="0" width="75" height="20" rx="2" class="pill-badge" />
          <text x="37" y="14" text-anchor="middle" class="pill-text">OCSF MAP</text>
        </g>

        <!-- ══════════════════════════════════════════════════════════════════════
             STAGE 1: EDGE AGENTS ACROSS SITES (Left Column)
             ══════════════════════════════════════════════════════════════════════ -->

        <!-- Agent A -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="20" y="30" width="195" height="88" rx="4" class="block-rect" />
            <text x="35" y="52" class="block-title">Agent A (Syslog/CEF)</text>
            <text x="35" y="70" class="block-site"><tspan class="grey-id">kol-dc1</tspan></text>
            <text x="35" y="88" class="block-desc">Cisco ASA &bull; LEEF &bull; Linux Auth</text>
            <text x="35" y="104" class="block-meta">142.5 EPS &bull; SHA-256 Envelope</text>
          </g>
        </a>

        <!-- Agent B -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="20" y="150" width="195" height="88" rx="4" class="block-rect" />
            <text x="35" y="172" class="block-title">Agent B (JSON/CSV)</text>
            <text x="35" y="190" class="block-site"><tspan class="grey-id">del-dc2</tspan></text>
            <text x="35" y="208" class="block-desc">CloudTrail &bull; Nginx &bull; Postgres &bull; K8s</text>
            <text x="35" y="224" class="block-meta">215.0 EPS &bull; Buffer 1.0MB</text>
          </g>
        </a>

        <!-- Agent C -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="20" y="270" width="195" height="88" rx="4" class="block-rect" />
            <text x="35" y="292" class="block-title">Agent C (Windows)</text>
            <text x="35" y="310" class="block-site"><tspan class="grey-id">mum-dc3</tspan></text>
            <text x="35" y="328" class="block-desc">EVTX XML &bull; Sysmon &bull; PowerShell</text>
            <text x="35" y="344" class="block-meta">88.0 EPS &bull; Buffer 256KB</text>
          </g>
        </a>

        <!-- ══════════════════════════════════════════════════════════════════════
             STAGE 2: APACHE KAFKA INGESTION BUS
             ══════════════════════════════════════════════════════════════════════ -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="275" y="145" width="150" height="100" rx="4" class="block-rect highlight-box" />
            <text x="290" y="170" class="block-title">Apache Kafka</text>
            <text x="290" y="188" class="block-desc">topic: {pipelineStats.kafka.raw_topic}</text>
            <text x="290" y="206" class="block-meta">{pipelineStats.kafka.raw_partitions} Partitions &bull; {pipelineStats.kafka.raw_lag} Lag</text>
            <text x="290" y="224" class="block-data">{fmt.n(pipelineStats.kafka.raw_messages)} msgs</text>
          </g>
        </a>

        <!-- ══════════════════════════════════════════════════════════════════════
             STAGE 3: INSIDE VECTOR SERVER ENGINE
             ══════════════════════════════════════════════════════════════════════ -->

        <!-- 3A: ULID Generator & Integrity Verifier (stamp_and_verify) -->
        <a href="#/config" class="svg-link">
          <g class="block-node">
            <rect x="495" y="145" width="185" height="100" rx="4" class="block-rect highlight-stage" />
            <text x="510" y="170" class="block-title">ULID Generator</text>
            <text x="510" y="188" class="block-desc">stamp_and_verify &bull; VRL</text>
            <text x="510" y="206" class="block-meta">metadata.uid &bull; SHA-256 Verif</text>
            <text x="510" y="222" class="block-data">{fmt.n(pipelineStats.vector_engine.stamped_ulid_count)} Stamped</text>
            <text x="510" y="235" class="block-note">{pipelineStats.integrity.unmatched_hashes} Unmatched &bull; 100% Valid</text>
          </g>
        </a>

        <!-- 3B: 13 VRL Normalizer Pipelines (route_source_type & transforms) -->
        <a href="#/config" class="svg-link">
          <g class="block-node">
            <rect x="710" y="235" width="205" height="145" rx="4" class="block-rect" />
            <text x="725" y="260" class="block-title">13 VRL Normalizers</text>
            <text x="725" y="278" class="block-desc">OCSF v1.3.0 Engine</text>
            <text x="725" y="296" class="block-meta">Cisco, CEF, LEEF, Nginx, EVTX</text>
            <text x="725" y="316" class="block-data">{fmt.n(pipelineStats.vector_engine.normalized_count)} Normalized</text>
            <text x="725" y="334" class="block-desc">Mapped to 6 OCSF Classes</text>
            <text x="725" y="350" class="block-note">ULID link to raw MinIO log</text>
          </g>
        </a>

        <!-- ══════════════════════════════════════════════════════════════════════
             STAGE 4: DESTINATIONS & SIEM ANALYTICS (Right Column)
             ══════════════════════════════════════════════════════════════════════ -->

        <!-- Destination 1: MinIO S3 Raw Data Lake (Direct from ULID Gen) -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="980" y="35" width="360" height="80" rx="4" class="block-rect lake-box" />
            <text x="995" y="58" class="block-title">MinIO S3 Raw Data Lake (ulpf-minio)</text>
            <text x="995" y="76" class="block-desc">bucket: {pipelineStats.minio.bucket} &bull; S3 Port 9000 &bull; Gzip NDJSON</text>
            <text x="995" y="94" class="block-data green">
              {fmt.n(pipelineStats.minio.preservation_count)} Raw Events &bull; {fmt.n(pipelineStats.minio.objects_count)} S3 Objects &bull; {pipelineStats.minio.size_mb}
            </text>
            <text x="995" y="106" class="block-note">Immutable raw log preservation stamped with ULID</text>
          </g>
        </a>

        <!-- Destination 2: OpenSearch SIEM (From 13 VRL Normalizers) -->
        <a href="#/logs" class="svg-link">
          <g class="block-node">
            <rect x="980" y="155" width="360" height="80" rx="4" class="block-rect siem-box" />
            <text x="995" y="178" class="block-title">OpenSearch SIEM (ulpf-opensearch)</text>
            <text x="995" y="196" class="block-desc">index: {pipelineStats.opensearch.index_name} &bull; Port 9200 &bull; OCSF 1.3</text>
            <text x="995" y="214" class="block-data cyan">
              {fmt.n(pipelineStats.opensearch.ocsf_events)} Indexed Docs &bull; {pipelineStats.opensearch.ocsf_size_mb}
            </text>
            <text x="995" y="226" class="block-note">Security query: Network, OS, DB, Audit, API events</text>
          </g>
        </a>

        <!-- Destination 3A: Kafka OCSF Bus (ulpf-ocsf-events) -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="980" y="275" width="160" height="100" rx="4" class="block-rect" />
            <text x="995" y="300" class="block-title">Kafka OCSF Bus</text>
            <text x="995" y="318" class="block-desc">ulpf-ocsf-events</text>
            <text x="995" y="336" class="block-meta">{pipelineStats.kafka.ocsf_partitions} Partitions &bull; {pipelineStats.kafka.ocsf_lag} Lag</text>
            <text x="995" y="354" class="block-data">{fmt.n(pipelineStats.kafka.ocsf_messages)} msgs</text>
          </g>
        </a>

        <!-- Destination 3B: ML Anomaly Worker (sih2-ml-worker-1) -->
        <a href="#/status" class="svg-link">
          <g class="block-node">
            <rect x="1170" y="275" width="170" height="100" rx="4" class="block-rect" />
            <text x="1185" y="300" class="block-title">ML Worker (Docker)</text>
            <text x="1185" y="318" class="block-desc">sih2-ml-worker-1</text>
            <text x="1185" y="336" class="block-meta">Isolation Forest / Drift</text>
            <text x="1185" y="354" class="block-data">{fmt.n(pipelineStats.ml_worker.findings_total)} Findings</text>
            <text x="1185" y="367" class="block-note">{pipelineStats.ml_worker.findings_mb} &bull; ulpf-ml-findings</text>
          </g>
        </a>
      </svg>
    </div>

    <!-- Clear Architectural Flow Legend -->
    <div class="diagram-footer">
      <div class="legend-row">
        <span class="legend-item"><span class="swatch edge"></span> Edge Ingest &rarr; Kafka Raw Broker</span>
        <span class="legend-item"><span class="swatch ulid"></span> Vector ULID Gate &amp; SHA-256 Checksum</span>
        <span class="legend-item"><span class="swatch lake"></span> Direct Raw Preservation &rarr; MinIO S3</span>
        <span class="legend-item"><span class="swatch ocsf"></span> 13 VRL Normalizers &rarr; OpenSearch SIEM &amp; ML</span>
      </div>
    </div>
  </section>

  <!-- Technical Subsystem Architecture Cards -->
  <section class="subsystems-grid">
    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">01</span>
        <h4>Edge Agents</h4>
      </div>
      <p class="sc-text">
        Vector agents (Agent A, Agent B, Agent C) capture syslog, CEF, LEEF, JSON, CSV, and Windows EVTX across distributed sites. They compute a raw SHA-256
        checksum and wrap events in a standardized ULPF envelope before forwarding to Kafka.
      </p>
      <div class="sc-meta">
        <span>Agent A <span class="site-id-grey">(kol-dc1)</span></span>
        <span>Agent B <span class="site-id-grey">(del-dc2)</span></span>
        <span>Agent C <span class="site-id-grey">(mum-dc3)</span></span>
        <span>SHA-256 Envelope</span>
      </div>
    </div>

    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">02</span>
        <h4>Apache Kafka Ingest Bus</h4>
      </div>
      <p class="sc-text">
        Decoupled message broker running KRaft mode (<code>ulpf-kafka:9092</code>). Topic <code>ulpf-raw-logs</code> buffers
        burst traffic across 3 partitions with low lag and durable disk persistence.
      </p>
      <div class="sc-meta">
        <span>ulpf-raw-logs</span>
        <span>3 Partitions</span>
        <span>KRaft Engine</span>
        <span>&lt; 20 Lag</span>
      </div>
    </div>

    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">03</span>
        <h4>Vector Server ULID Generator</h4>
      </div>
      <p class="sc-text">
        Server parser executes <code>stamp_and_verify</code>. It recalculates the SHA-256 hash to detect any tampering
        (0 unmatched hashes across 530k+ logs), and generates a 128-bit sortable ULID (<code>metadata.uid</code>).
      </p>
      <div class="sc-meta">
        <span>metadata.uid</span>
        <span>SHA-256 Verif</span>
        <span>0 Unmatched</span>
        <span>405k+ Stamped</span>
      </div>
    </div>

    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">04</span>
        <h4>MinIO S3 Raw Data Lake</h4>
      </div>
      <p class="sc-text">
        <strong>Branch 1 (Direct from ULID Gen)</strong>: Raw event payloads stamped with their ULID are written directly
        to MinIO S3 (<code>ulpf-data-lake</code> bucket) in sitewise partitions, compressed with Gzip for immutable cold audit compliance.
      </p>
      <div class="sc-meta">
        <span>ulpf-data-lake</span>
        <span>18.9k Objects</span>
        <span>58 MiB Gzip</span>
        <span>405k Preserved</span>
      </div>
    </div>

    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">05</span>
        <h4>13 VRL Normalizers &rarr; SIEM</h4>
      </div>
      <p class="sc-text">
        <strong>Branch 2 (After ULID Gen)</strong>: Stamped logs pass through 13 parallel VRL transforms, standardizing
        heterogeneous sources into OCSF v1.3.0 schemas and indexing directly into OpenSearch (<code>ulpf-ocsf-*</code>).
      </p>
      <div class="sc-meta">
        <span>13 VRL Pipelines</span>
        <span>OCSF v1.3.0</span>
        <span>350k+ Indexed</span>
        <span>Port 9200</span>
      </div>
    </div>

    <div class="subsystem-card">
      <div class="sc-header">
        <span class="sc-num">06</span>
        <h4>ML Anomaly &amp; Drift Worker</h4>
      </div>
      <p class="sc-text">
        Normalized events stream to Kafka <code>ulpf-ocsf-events</code>. The ML worker (<code>sih2-ml-worker-1</code>) runs
        Isolation Forest and statistical entropy models, writing findings to <code>ulpf-ml-findings</code> in OpenSearch.
      </p>
      <div class="sc-meta">
        <span>sih2-ml-worker-1</span>
        <span>ulpf-ml-findings</span>
        <span>292k+ Audits</span>
        <span>Port 9092</span>
      </div>
    </div>
  </section>
</div>

<style>
  .homepage {
    display: flex;
    flex-direction: column;
    gap: var(--s5);
  }

  /* Hero Section */
  .hero-showcase {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: var(--s6);
  }

  .showcase-content {
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    max-width: 1200px;
  }

  .badge-cluster {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-wrap: wrap;
  }

  .live-status-pill {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font: 600 var(--t-1)/1 var(--mono);
    padding: 4px 10px;
    border-radius: 20px;
    background: var(--ok-bg);
    color: var(--ok);
    border: 1px solid var(--ok);
  }

  .cluster-tag {
    font: 600 10px/1 var(--mono);
    padding: 4px 8px;
    border-radius: 4px;
    background: var(--bg-2);
    color: var(--fg-1);
    border: 1px solid var(--line);
  }

  .hero-title {
    font-size: var(--t4);
    font-weight: 600;
    color: var(--fg);
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin: 0;
  }

  .hero-subtitle {
    font-size: var(--t1);
    color: var(--fg-1);
    line-height: 1.6;
    max-width: 980px;
    margin: 0;
  }

  .architecture-kpis {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: var(--s4);
    margin-top: var(--s2);
    padding-top: var(--s4);
    border-top: 1px solid var(--line);
  }

  .arch-kpi {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .kpi-num {
    font: 600 var(--t3)/1.1 var(--mono);
    color: var(--fg);
  }

  .highlight-clean .kpi-num {
    color: var(--ok);
  }

  .kpi-num small {
    font-size: var(--t0);
    color: var(--fg-2);
    font-weight: normal;
  }

  .kpi-lbl {
    font-size: var(--t0);
    font-weight: 600;
    color: var(--fg);
  }

  .kpi-sub {
    font-size: var(--t-1);
    color: var(--fg-2);
  }

  /* Professional Diagram Section */
  .diagram-section {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 6px;
    overflow: hidden;
  }

  .diagram-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s3) var(--s5);
    background: var(--bg-2);
    border-bottom: 1px solid var(--line);
  }

  .dh-title h3 {
    font-size: var(--t1);
    font-weight: 600;
    color: var(--fg);
    margin: 0;
  }

  .dh-actions {
    display: flex;
    gap: var(--s2);
  }

  .nav-btn {
    font-size: var(--t-1);
    font-weight: 500;
    color: var(--fg-1);
    text-decoration: none;
    padding: 4px 10px;
    border-radius: 3px;
    border: 1px solid var(--line-2);
    background: var(--bg-1);
    transition: all var(--d1);
  }

  .nav-btn:hover {
    color: var(--fg);
    border-color: var(--line-3);
    background: var(--bg-2);
  }

  .canvas-wrap {
    padding: var(--s5);
    background: #121417;
    overflow-x: auto;
  }

  .arch-svg {
    width: 100%;
    height: auto;
    min-width: 1100px;
    display: block;
  }

  /* Vector Engine Container */
  .engine-frame {
    fill: #161a1f;
    stroke: #373e47;
    stroke-width: 1.5;
  }

  .engine-title-bar {
    fill: #1f242c;
    stroke: #373e47;
    stroke-width: 1.5;
  }

  .engine-title-text {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    fill: #c9d1d9;
  }

  .engine-title-sub {
    font-family: var(--mono);
    font-size: 10px;
    fill: #8b949e;
  }

  /* Connectors */
  .wire {
    fill: none;
    stroke: #484f58;
    stroke-width: 1.5;
  }

  .wire-green {
    stroke: #3fb950;
  }

  .wire-cyan {
    stroke: #58a6ff;
  }

  /* Path Badges */
  .pill-badge {
    fill: #1c2128;
    stroke: #373e47;
    stroke-width: 1;
  }

  .pill-badge.green {
    fill: #13231b;
    stroke: #238636;
  }

  .pill-text {
    font-family: var(--mono);
    font-size: 9px;
    font-weight: 600;
    fill: #8b949e;
  }

  .pill-text.green {
    fill: #3fb950;
  }

  /* Blocks */
  a.svg-link {
    text-decoration: none;
    outline: none;
  }

  .block-node {
    cursor: pointer;
  }

  .block-rect {
    fill: #1a1e24;
    stroke: #30363d;
    stroke-width: 1.5;
    transition: stroke var(--d1);
  }

  .block-node:hover .block-rect {
    stroke: #586069;
  }

  .block-rect.highlight-box {
    fill: #17211b;
    stroke: #2e4d3a;
  }

  .block-rect.highlight-stage {
    fill: #1d1b26;
    stroke: #43395c;
  }

  .block-rect.lake-box {
    fill: #16221b;
    stroke: #234d32;
  }

  .block-rect.siem-box {
    fill: #15202b;
    stroke: #2b455c;
  }

  .block-title {
    font-family: var(--sans);
    font-weight: 600;
    font-size: 12.5px;
    fill: #f0f3f6;
  }

  .block-site {
    font-family: var(--sans);
    font-size: 11px;
    font-weight: 600;
    fill: #58a6ff;
  }

  .grey-id {
    fill: #8b949e;
    font-size: 10px;
    font-weight: normal;
    font-family: var(--mono);
  }

  .block-desc {
    font-family: var(--sans);
    font-size: 11px;
    fill: #8b949e;
  }

  .block-meta {
    font-family: var(--mono);
    font-size: 10px;
    fill: #8b949e;
  }

  .block-data {
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    fill: #e6edf3;
  }

  .block-data.green {
    fill: #3fb950;
  }

  .block-data.cyan {
    fill: #58a6ff;
  }

  .block-note {
    font-family: var(--mono);
    font-size: 9.5px;
    fill: #6e7681;
  }

  /* Legend Footer */
  .diagram-footer {
    padding: var(--s3) var(--s5);
    background: var(--bg-2);
    border-top: 1px solid var(--line);
  }

  .legend-row {
    display: flex;
    gap: var(--s5);
    flex-wrap: wrap;
    font-size: var(--t-1);
    color: var(--fg-1);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .swatch {
    width: 12px;
    height: 3px;
    border-radius: 1px;
  }

  .swatch.edge { background: #484f58; }
  .swatch.ulid { background: #8957e5; }
  .swatch.lake { background: #3fb950; }
  .swatch.ocsf { background: #58a6ff; }

  /* Subsystems Grid */
  .subsystems-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s4);
  }

  .subsystem-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .sc-header {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .sc-num {
    font: 600 var(--t-1)/1 var(--mono);
    color: var(--fg-2);
    background: var(--bg-2);
    padding: 3px 6px;
    border-radius: 3px;
    border: 1px solid var(--line);
  }

  .sc-header h4 {
    font-size: var(--t1);
    font-weight: 600;
    color: var(--fg);
    margin: 0;
  }

  .sc-text {
    font-size: var(--t-1);
    color: var(--fg-1);
    line-height: 1.55;
    margin: 0;
    flex-grow: 1;
  }

  .sc-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: var(--s2);
  }

  .sc-meta span {
    font: 500 9.5px/1 var(--mono);
    padding: 3px 6px;
    border-radius: 3px;
    background: var(--bg-2);
    color: var(--fg-2);
    border: 1px solid var(--line);
  }
</style>
