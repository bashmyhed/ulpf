<script>
  import { fmt } from './api.js'

  // collector: object from /api/ulpf/collectors
  // rawMetrics: raw prometheus text string from /api/ulpf/collectors/:id/metrics
  let { collector = null, rawMetrics = '' } = $props()

  // Parse Prometheus text lines for key gauges and counters
  const parsed = $derived.by(() => {
    const res = {
      cpuUsage: null,
      memoryUsedBytes: null,
      memoryTotalBytes: null,
      diskReadBytes: null,
      diskWrittenBytes: null,
      netTxBytes: null,
      netRxBytes: null,
      eventsSent: null,
      eventsReceived: null,
      errorsTotal: null,
      rawLines: []
    }

    if (!rawMetrics) return res

    const lines = rawMetrics.split('\n')
    res.rawLines = lines.filter((l) => l && !l.startsWith('#')).slice(0, 30)

    for (const line of lines) {
      if (!line || line.startsWith('#')) continue
      const parts = line.split(/\s+/)
      if (parts.length < 2) continue
      const name = parts[0]
      const val = parseFloat(parts[1])
      if (isNaN(val)) continue

      if (name.startsWith('host_cpu_seconds_total') && name.includes('mode="user"')) {
        res.cpuUsage = val
      } else if (name.startsWith('host_memory_used_bytes')) {
        res.memoryUsedBytes = val
      } else if (name.startsWith('host_memory_total_bytes')) {
        res.memoryTotalBytes = val
      } else if (name.startsWith('host_disk_read_bytes_total')) {
        res.diskReadBytes = val
      } else if (name.startsWith('host_disk_written_bytes_total')) {
        res.diskWrittenBytes = val
      } else if (name.startsWith('host_network_transmit_bytes_total')) {
        res.netTxBytes = val
      } else if (name.startsWith('host_network_receive_bytes_total')) {
        res.netRxBytes = val
      } else if (name.startsWith('vector_component_sent_events_total')) {
        res.eventsSent = (res.eventsSent ?? 0) + val
      } else if (name.startsWith('vector_component_received_events_total')) {
        res.eventsReceived = (res.eventsReceived ?? 0) + val
      } else if (name.startsWith('vector_component_errors_total')) {
        res.errorsTotal = (res.errorsTotal ?? 0) + val
      }
    }
    return res
  })
</script>

<div class="metrics-panel">
  <div class="head quiet">
    <h3>Live Pipeline & System Metrics</h3>
    {#if collector?.last_seen}
      <span class="note push">Last seen {fmt.ago(Math.floor((Date.now() - new Date(collector.last_seen).getTime()) / 1000))}</span>
    {/if}
  </div>

  <div class="kvs-grid">
    <div class="stat-card">
      <div class="stat-label">Throughput</div>
      <div class="stat-val num">{fmt.f(collector?.events_per_sec ?? 0, 1)} <span class="unit">eps</span></div>
      <div class="bar-track">
        <div class="bar-fill" style="width: {Math.min(100, ((collector?.events_per_sec ?? 0) / 500) * 100)}%"></div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Buffer Pressure</div>
      <div class="stat-val num">{fmt.mb(collector?.buffer_bytes ?? 0)} <span class="unit">MB</span></div>
      <div class="bar-track">
        <div class="bar-fill warn" style="width: {Math.min(100, ((collector?.buffer_bytes ?? 0) / 10485760) * 100)}%"></div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Kafka Producer Lag</div>
      <div class="stat-val num">{fmt.n(collector?.kafka_lag ?? 0)} <span class="unit">msgs</span></div>
      <div class="bar-track">
        <div class="bar-fill bad" style="width: {Math.min(100, (collector?.kafka_lag ?? 0))}%"></div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Uptime</div>
      <div class="stat-val num">{fmt.ago(collector?.uptime_secs ?? 0)}</div>
      <div class="sub-label">Version: {collector?.version || 'v1.0.0'}</div>
    </div>
  </div>

  <!-- Detailed host and vector telemetry -->
  <div class="counters">
    <b>Pipeline Counters</b>
    <div class="kvs">
      <div class="kv"><span>Events Emitted</span><b>{fmt.n(parsed.eventsSent ?? collector?.events_per_sec)}</b></div>
      <div class="kv"><span>Events Ingested</span><b>{fmt.n(parsed.eventsReceived ?? collector?.events_per_sec)}</b></div>
      <div class="kv"><span>Errors Total</span><b class:is-bad={(parsed.errorsTotal ?? 0) > 0}>{fmt.n(parsed.errorsTotal ?? 0)}</b></div>
      <div class="kv"><span>Network Transmit</span><b>{fmt.mb(parsed.netTxBytes)} MB</b></div>
    </div>
  </div>

  <div class="counters">
    <b>Host Resources</b>
    <div class="kvs">
      <div class="kv"><span>Host IP</span><b class="mono">{collector?.host_ip || '–'}</b></div>
      <div class="kv"><span>Hostname</span><b>{collector?.hostname || '–'}</b></div>
      <div class="kv"><span>Disk Read</span><b>{fmt.mb(parsed.diskReadBytes)} MB</b></div>
      <div class="kv"><span>Disk Written</span><b>{fmt.mb(parsed.diskWrittenBytes)} MB</b></div>
    </div>
  </div>

  {#if collector?.capabilities?.length}
    <div class="capabilities-row">
      <span class="muted xs">Capabilities:</span>
      {#each collector.capabilities as cap}
        <span class="tag">{cap}</span>
      {/each}
    </div>
  {/if}

  {#if parsed.rawLines.length > 0}
    <details class="prom-dump">
      <summary class="muted xs">Prometheus Metrics Stream ({parsed.rawLines.length} samples)</summary>
      <pre class="prom-code">{parsed.rawLines.join('\n')}</pre>
    </details>
  {/if}
</div>

<style>
  .metrics-panel { display: grid; gap: var(--s4); }
  .kvs-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: var(--s3); }
  .stat-card { background: var(--bg); border: 1px solid var(--line); padding: var(--s3); border-radius: 2px; }
  .stat-label { font-size: var(--t-1); color: var(--fg-2); text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-val { font-size: var(--t2); font-weight: 600; margin: 4px 0; color: var(--fg); }
  .stat-val .unit { font-size: var(--t-1); font-weight: 400; color: var(--fg-2); }
  .sub-label { font-size: var(--t-1); color: var(--fg-2); }
  .bar-track { width: 100%; height: 3px; background: var(--line); border-radius: 1px; overflow: hidden; margin-top: 4px; }
  .bar-fill { height: 100%; background: var(--ok); transition: width 0.3s ease; }
  .bar-fill.warn { background: var(--warn); }
  .bar-fill.bad { background: var(--bad); }
  .capabilities-row { display: flex; align-items: center; gap: var(--s2); flex-wrap: wrap; margin-top: var(--s2); }
  .prom-dump { margin-top: var(--s3); border-top: 1px solid var(--line); padding-top: var(--s2); }
  .prom-dump summary { cursor: pointer; }
  .prom-code { font-size: 10px; max-height: 160px; overflow-y: auto; background: var(--bg); padding: var(--s2); border: 1px solid var(--line); margin-top: var(--s2); }
</style>
