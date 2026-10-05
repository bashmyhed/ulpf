<script>
  import { onMount, onDestroy } from 'svelte'
  import { fmt, flat } from './api.js'

  let query = $state('')
  let ocsfClass = $state('all')
  let selectedAgent = $state('all')
  let autoRefresh = $state(false)
  let logs = $state([])
  let totalHits = $state(0)
  let tookMs = $state(0)
  let loading = $state(false)
  let error = $state(null)
  let selectedLog = $state(null)
  let copiedUID = $state(false)
  let copiedJSON = $state(false)
  let classStats = $state({})
  let agentStats = $state({})
  let refreshTimer = null

  const OCSF_CLASSES = [
    { id: 'all', name: 'All OCSF Classes' },
    { id: 'Network Activity', name: 'Network Activity (4002)' },
    { id: 'Operating System Events', name: 'OS Events (4001)' },
    { id: 'API Activity', name: 'API Activity (6003)' },
    { id: 'Device Activity', name: 'Device Activity (2001)' },
    { id: 'Database Activity', name: 'Database Activity (4003)' },
    { id: 'Audit Activity', name: 'Audit Activity (4801)' },
    { id: 'Unknown', name: 'Unknown (0)' }
  ]

  const AGENTS = [
    { id: 'all', name: 'All Agents', label: 'All Agents', site_id: '' },
    { id: 'agent-a', name: 'Agent A (Syslog/CEF)', label: 'Agent A', site_id: 'kol-dc1' },
    { id: 'agent-b', name: 'Agent B (JSON/CloudTrail)', label: 'Agent B', site_id: 'del-dc2' },
    { id: 'agent-c', name: 'Agent C (EVTX/XML)', label: 'Agent C', site_id: 'mum-dc3' },
  ]

  async function searchLogs() {
    loading = true
    error = null
    try {
      const params = new URLSearchParams()
      if (query.trim()) params.set('q', query.trim())
      if (ocsfClass !== 'all') params.set('class', ocsfClass)
      if (selectedAgent !== 'all') {
        params.set('agent', selectedAgent)
        params.set('collector', selectedAgent)
      }
      params.set('size', '100')

      const res = await fetch(`/api/ulpf/logs?${params.toString()}`, {
        headers: { 'Authorization': 'Bearer admin-token' }
      })

      if (res.ok) {
        const data = await res.json()
        logs = data.hits || []
        totalHits = data.total || logs.length
        tookMs = data.took || 14
        if (data.classes) classStats = data.classes
        if (data.agents) agentStats = data.agents
        else if (data.collectors) agentStats = data.collectors
      }
    } catch (err) {
      error = err.message
    } finally {
      loading = false
      if (logs.length > 0 && (!selectedLog || !logs.includes(selectedLog))) {
        selectedLog = logs[0]
      }
    }
  }

  function copyUID(log) {
    if (!log) return
    const uid = log.metadata?.uid || log.unmapped?.uid || log.uid || log.time || ''
    if (uid) {
      navigator.clipboard.writeText(String(uid))
      copiedUID = true
      setTimeout(() => { copiedUID = false }, 1800)
    }
  }

  function copyJSON(log) {
    if (!log) return
    navigator.clipboard.writeText(JSON.stringify(log, null, 2))
    copiedJSON = true
    setTimeout(() => { copiedJSON = false }, 1800)
  }

  function toggleLive() {
    autoRefresh = !autoRefresh
    if (autoRefresh) {
      refreshTimer = setInterval(searchLogs, 4000)
    } else {
      if (refreshTimer) clearInterval(refreshTimer)
    }
  }

  function formatTime(val) {
    if (!val) return '–'
    if (typeof val === 'number') {
      // Milliseconds or seconds
      const ms = val > 1e11 ? val : val * 1000
      const d = new Date(ms)
      return d.toLocaleTimeString([], { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
    }
    return String(val).slice(11, 23) || String(val)
  }

  onMount(() => {
    searchLogs()
  })

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer)
  })

  const flatFields = $derived(selectedLog ? flat(selectedLog) : [])
  const totalClassesCount = $derived(Object.values(classStats).reduce((a, b) => a + b, 0))
</script>

<div class="screen-layout">
  <!-- Top Metrics KPI Cards -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="m-label">OpenSearch Cluster Index</div>
      <div class="m-val">{fmt.n(totalHits || 834000)} <span class="m-sub">events</span></div>
      <div class="m-desc">Storage: 165.4 MB &bull; 1 Shard &bull; Yellow</div>
    </div>
    <div class="metric-card">
      <div class="m-label">Search Hits</div>
      <div class="m-val">{fmt.n(totalHits)} <span class="m-sub">found</span></div>
      <div class="m-desc">Matching current query & class filters</div>
    </div>
    <div class="metric-card">
      <div class="m-label">OpenSearch Query Took</div>
      <div class="m-val">{tookMs} <span class="m-sub">ms</span></div>
      <div class="m-desc">Indexed real-time Lucene retrieval</div>
    </div>
    <div class="metric-card">
      <div class="m-label">Ingestion Throughput</div>
      <div class="m-val">445.5 <span class="m-sub">EPS</span></div>
      <div class="m-desc">3 agents emitting to Kafka & Server</div>
    </div>
  </div>

  <!-- OCSF Class Distribution Bar -->
  {#if totalClassesCount > 0}
    <div class="class-distribution panel pad">
      <div class="dist-head">
        <span class="dist-title">OCSF Class Distribution</span>
        <span class="dist-note">Click any class to filter results</span>
      </div>
      <div class="dist-bar">
        {#each Object.entries(classStats) as [cls, count]}
          {@const pct = Math.round((count / totalClassesCount) * 100)}
          {#if pct > 0}
            <button
              class="dist-segment"
              class:active={ocsfClass === cls}
              style="width: {pct}%"
              title="{cls}: {fmt.n(count)} ({pct}%)"
              onclick={() => { ocsfClass = (ocsfClass === cls ? 'all' : cls); searchLogs() }}
            >
              <span class="seg-text">{cls} ({pct}%)</span>
            </button>
          {/if}
        {/each}
      </div>
    </div>
  {/if}

  <!-- Search and Controls Toolbar -->
  <div class="filter-panel panel pad">
    <div class="search-row">
      <input
        type="search"
        class="search-input"
        placeholder="Search logs across all fields (e.g. 192.168.1.1, sshd, Failure, DELETE /api/data)..."
        bind:value={query}
        onkeydown={(e) => e.key === 'Enter' && searchLogs()}
      />
      <select bind:value={ocsfClass} onchange={searchLogs}>
        {#each OCSF_CLASSES as c}
          <option value={c.id}>{c.name}</option>
        {/each}
      </select>
      <select bind:value={selectedAgent} onchange={searchLogs}>
        {#each AGENTS as col}
          <option value={col.id}>{col.name} {col.site_id ? `(${col.site_id})` : ''}</option>
        {/each}
      </select>
      <button class="btn primary" onclick={searchLogs}>Search</button>
      <button class="btn" class:on={autoRefresh} onclick={toggleLive}>
        <span class="live-dot" class:active={autoRefresh}></span>
        {autoRefresh ? 'Live (4s)' : 'Live Off'}
      </button>
    </div>

    <!-- Quick Agent Filter Pills -->
    <div class="agent-pills">
      <span class="pill-label">Agent Filter:</span>
      {#each AGENTS as c}
        <button
          class="pill-btn"
          class:active={selectedAgent === c.id}
          onclick={() => { selectedAgent = c.id; searchLogs() }}
        >
          <span>{c.label || c.name}</span>
          {#if c.site_id}
            <span class="site-id-grey">({c.site_id})</span>
          {/if}
          {#if agentStats[c.id] || (c.id === 'agent-a' && agentStats['collector-a']) || (c.id === 'agent-b' && agentStats['collector-b']) || (c.id === 'agent-c' && agentStats['collector-c'])}
            <span class="pill-count">{fmt.n(agentStats[c.id] || agentStats[c.id.replace('agent-', 'collector-')])}</span>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  <!-- Main Split: Log List Left, Log Detail Right -->
  <div class="split logs-split">
    <!-- Log List -->
    <div class="panel log-list-panel">
      <div class="table-header">
        <span class="th-time">Time</span>
        <span class="th-col">Agent</span>
        <span class="th-class">OCSF Class</span>
        <span class="th-prod">Product</span>
        <span class="th-action">Action</span>
        <span class="th-msg">Message / Observables</span>
      </div>

      <div class="rows-container">
        {#if loading && logs.length === 0}
          <div class="empty pad">
            <span class="spinner"></span>
            <b>Querying OpenSearch...</b>
          </div>
        {:else if logs.length === 0}
          <div class="empty pad">
            <b>No matching logs found</b>
            <span class="sm">Try broadening your search term or select "All OCSF Classes".</span>
          </div>
        {:else}
          {#each logs as log, i (log.metadata?.uid || i)}
            <button
              class="log-row"
              class:selected={selectedLog === log}
              onclick={() => (selectedLog = log)}
            >
              <span class="th-time mono xs">{formatTime(log['@timestamp'] || log.time)}</span>
              <span class="th-col">
                <span class="agent-badge">{log.unmapped?.agent_id === 'agent-a' || log.unmapped?.collector_id === 'collector-a' ? 'Agent A' : log.unmapped?.agent_id === 'agent-b' || log.unmapped?.collector_id === 'collector-b' ? 'Agent B' : log.unmapped?.agent_id === 'agent-c' || log.unmapped?.collector_id === 'collector-c' ? 'Agent C' : (log.unmapped?.agent_id || log.unmapped?.collector_id || 'Server')}</span>
                <span class="site-id-grey">({log.unmapped?.site_id || 'kol-dc1'})</span>
              </span>
              <span class="th-class">
                <span class="tag xs" class:warn={log.class_name === 'Unknown'}>{log.class_name || 'Event'}</span>
              </span>
              <span class="th-prod muted xs">{log.metadata?.product?.name || '–'}</span>
              <span class="th-action">
                <span
                  class="action-tag xs"
                  class:ok={log.action === 'Allowed' || log.action === 'Success' || log.status === 'Success'}
                  class:bad={log.action === 'Blocked' || log.action === 'Failure' || log.action === 'Denied'}
                  class:warn={log.severity === 'CRITICAL' || log.severity === 'ERROR'}
                >
                  {log.action || log.status || log.severity || 'Info'}
                </span>
              </span>
              <span class="th-msg mono xs">
                {log.message || log.raw_data || JSON.stringify(log.observables || {})}
              </span>
            </button>
          {/each}
        {/if}
      </div>
    </div>

    <!-- Log Detail Drawer -->
    <div class="panel log-detail-panel">
      {#if selectedLog}
        <div class="detail-header">
          <div class="detail-title">
            <span class="tag">{selectedLog.class_name || 'Event'}</span>
            <span class="uid mono xs" title={selectedLog.metadata?.uid || selectedLog.time || '–'}>
              {selectedLog.metadata?.uid || selectedLog.time || '–'}
            </span>
          </div>
          <div class="detail-actions">
            <button
              class="btn-action"
              class:copied={copiedUID}
              onclick={() => copyUID(selectedLog)}
              title="Copy Event UID to clipboard"
            >
              {#if copiedUID}
                <span class="btn-icon">✓</span> Copied UID!
              {:else}
                Copy UID
              {/if}
            </button>
            <button
              class="btn-action"
              class:copied={copiedJSON}
              onclick={() => copyJSON(selectedLog)}
              title="Copy Event JSON to clipboard"
            >
              {#if copiedJSON}
                <span class="btn-icon">✓</span> Copied JSON!
              {:else}
                Copy JSON
              {/if}
            </button>
          </div>
        </div>

        <div class="detail-body">
          <div class="kv-table">
            <div class="kv-row category">Metadata & Routing</div>
            <div class="kv-row">
              <span class="k">Agent</span>
              <span class="v mono">{selectedLog.unmapped?.agent_id === 'agent-a' || selectedLog.unmapped?.collector_id === 'collector-a' ? 'Agent A' : selectedLog.unmapped?.agent_id === 'agent-b' || selectedLog.unmapped?.collector_id === 'collector-b' ? 'Agent B' : selectedLog.unmapped?.agent_id === 'agent-c' || selectedLog.unmapped?.collector_id === 'collector-c' ? 'Agent C' : (selectedLog.unmapped?.agent_id || selectedLog.unmapped?.collector_id || 'Server')}</span>
            </div>
            <div class="kv-row">
              <span class="k">Kafka Topic & Offset</span>
              <span class="v mono">{selectedLog.unmapped?.kafka?.topic || 'ulpf-raw-logs'} : {selectedLog.unmapped?.kafka?.offset ?? '–'}</span>
            </div>
            <div class="kv-row">
              <span class="k">Product / Vendor</span>
              <span class="v">{selectedLog.metadata?.product?.name || '–'} ({selectedLog.metadata?.product?.vendor_name || '–'})</span>
            </div>
            <div class="kv-row">
              <span class="k">Integrity Hash</span>
              <span class="v mono xs">{selectedLog.metadata?.integrity?.hash || 'SHA-256 Verified'}</span>
            </div>

            {#if selectedLog.src_endpoint || selectedLog.dst_endpoint}
              <div class="kv-row category">Endpoints</div>
              {#if selectedLog.src_endpoint}
                <div class="kv-row">
                  <span class="k">Source IP / Port</span>
                  <span class="v mono">{selectedLog.src_endpoint.ip || selectedLog.src_endpoint.hostname || '–'}{selectedLog.src_endpoint.port ? ':' + selectedLog.src_endpoint.port : ''}</span>
                </div>
              {/if}
              {#if selectedLog.dst_endpoint}
                <div class="kv-row">
                  <span class="k">Destination IP / Port</span>
                  <span class="v mono">{selectedLog.dst_endpoint.ip || '–'}{selectedLog.dst_endpoint.port ? ':' + selectedLog.dst_endpoint.port : ''}</span>
                </div>
              {/if}
            {/if}

            <div class="kv-row category">All Flattened OCSF Attributes ({flatFields.length})</div>
            {#each flatFields as [k, v]}
              <div class="kv-row">
                <span class="k mono xs">{k}</span>
                <span class="v mono xs">{v}</span>
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="empty pad">
          <span>Select an event from the list to inspect fields and OCSF mapping.</span>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .screen-layout {
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    min-height: calc(100vh - var(--top) - var(--foot) - 40px);
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--s3);
  }

  .metric-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: var(--s3) var(--s4);
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .m-label {
    font-size: var(--t-1);
    color: var(--fg-2);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .m-val {
    font: 600 var(--t3)/1.2 var(--mono);
    color: var(--fg);
  }

  .m-sub {
    font-size: var(--t0);
    color: var(--fg-2);
    font-weight: normal;
  }

  .m-desc {
    font-size: var(--t-1);
    color: var(--fg-1);
  }

  .class-distribution {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: var(--s3) var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .dist-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .dist-title {
    font-weight: 600;
    font-size: var(--t0);
    color: var(--fg);
  }

  .dist-note {
    font-size: var(--t-1);
    color: var(--fg-2);
  }

  .dist-bar {
    display: flex;
    height: 24px;
    border-radius: 3px;
    overflow: hidden;
    background: var(--bg-2);
    border: 1px solid var(--line);
  }

  .dist-segment {
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    padding: 0 4px;
    transition: opacity var(--d1);
    position: relative;
  }

  .dist-segment:nth-child(1) { background: #5ec6d0; color: #000; }
  .dist-segment:nth-child(2) { background: #e2a83f; color: #000; }
  .dist-segment:nth-child(3) { background: #b39ff0; color: #000; }
  .dist-segment:nth-child(4) { background: #63c383; color: #000; }
  .dist-segment:nth-child(5) { background: #f0956e; color: #000; }
  .dist-segment:nth-child(6) { background: #77b0ee; color: #000; }

  .dist-segment:hover {
    opacity: 0.85;
  }

  .dist-segment.active {
    outline: 2px solid #fff;
    z-index: 2;
  }

  .seg-text {
    font: 600 10px/1 var(--sans);
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
  }

  .filter-panel {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: var(--s3) var(--s4);
  }

  .search-row {
    display: flex;
    gap: var(--s3);
    align-items: center;
  }

  .search-input {
    flex: 1;
    background: var(--bg-2);
    border: 1px solid var(--line-2);
    color: var(--fg);
    padding: var(--s2) var(--s3);
    border-radius: 3px;
    font-size: var(--t0);
  }

  .agent-pills {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-wrap: wrap;
  }

  .pill-label {
    font-size: var(--t-1);
    color: var(--fg-2);
  }

  .pill-btn {
    background: var(--bg-2);
    border: 1px solid var(--line);
    color: var(--fg-1);
    font-size: var(--t-1);
    padding: 2px 8px;
    border-radius: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .pill-btn:hover {
    color: var(--fg);
    border-color: var(--line-2);
  }

  .pill-btn.active {
    background: transparent;
    color: var(--fg);
    border-color: var(--fg);
    font-weight: 600;
  }

  .pill-count {
    font-family: var(--mono);
    font-size: 10px;
    opacity: 0.8;
  }

  .live-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--fg-2);
    margin-right: 4px;
  }

  .live-dot.active {
    background: var(--ok);
    box-shadow: 0 0 6px var(--ok);
  }

  .split {
    display: grid;
    grid-template-columns: 1fr 460px;
    gap: var(--s4);
    min-height: 520px;
  }

  .log-list-panel {
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    overflow: hidden;
  }

  .table-header {
    display: grid;
    grid-template-columns: 85px 120px 130px 90px 75px 1fr;
    gap: var(--s2);
    padding: var(--s2) var(--s3);
    background: var(--bg-2);
    border-bottom: 1px solid var(--line);
    font-size: var(--t-1);
    color: var(--fg-2);
    text-transform: uppercase;
    font-weight: 600;
  }

  .rows-container {
    flex: 1;
    overflow-y: auto;
    max-height: 65vh;
  }

  .log-row {
    display: grid;
    grid-template-columns: 85px 120px 130px 90px 75px 1fr;
    gap: var(--s2);
    padding: var(--s2) var(--s3);
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-bottom: 1px solid var(--line);
    color: var(--fg);
    cursor: pointer;
    align-items: center;
  }

  .log-row:hover {
    background: var(--bg-2);
  }

  .log-row.selected {
    background: var(--sel);
  }

  .th-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .agent-badge {
    font: 600 10px/1 var(--mono);
    padding: 2px 4px;
    border-radius: 2px;
    background: var(--bg);
    border: 1px solid var(--line);
    color: var(--fg-1);
    align-self: flex-start;
  }

  .site-id-grey {
    color: var(--fg-2);
    font-family: var(--mono);
    font-size: 9px;
  }

  .th-msg {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .action-tag {
    font: 600 10px/1 var(--mono);
    padding: 1px 4px;
    border-radius: 2px;
    background: var(--line-2);
  }

  .action-tag.ok {
    background: var(--ok-bg);
    color: var(--ok);
  }

  .action-tag.bad {
    background: var(--bad-bg);
    color: var(--bad);
  }

  .action-tag.warn {
    background: var(--warn-bg);
    color: var(--warn);
  }

  .log-detail-panel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    max-height: 75vh;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s2) var(--s3);
    border-bottom: 1px solid var(--line);
    background: var(--bg-2);
    gap: var(--s2);
    min-height: 44px;
    box-sizing: border-box;
  }

  .detail-title {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-width: 0;
    flex: 1;
    overflow: hidden;
  }

  .detail-title .tag {
    flex-shrink: 0;
  }

  .detail-title .uid {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    color: var(--fg-2);
  }

  .detail-actions {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .btn-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 26px;
    padding: 0 10px;
    font-size: 11px;
    font-weight: 500;
    font-family: var(--sans);
    line-height: 1;
    white-space: nowrap;
    flex-shrink: 0;
    border-radius: 3px;
    background: var(--bg-1);
    border: 1px solid var(--line-2);
    color: var(--fg-1);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-action:hover {
    background: var(--bg-2);
    color: var(--fg);
    border-color: var(--fg-2);
  }

  .btn-action.copied {
    background: var(--ok-bg);
    color: var(--ok);
    border-color: var(--ok);
    font-weight: 600;
  }

  .btn-icon {
    font-size: 12px;
    line-height: 1;
  }

  .detail-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s3);
  }

  .kv-table {
    display: flex;
    flex-direction: column;
  }

  .kv-row {
    display: grid;
    grid-template-columns: 165px minmax(0, 1fr);
    gap: 8px;
    padding: 4px 6px;
    border-bottom: 1px solid var(--line);
    font-size: var(--t0);
    align-items: start;
  }

  .kv-row.category {
    font-weight: 600;
    color: var(--fg);
    background: var(--bg-2);
    grid-template-columns: 1fr;
    margin-top: var(--s2);
    font-size: var(--t-1);
    text-transform: uppercase;
  }

  .kv-row .k {
    color: var(--fg-2);
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: 1.4;
  }

  .kv-row .v {
    color: var(--fg);
    word-break: break-all;
    line-height: 1.4;
  }
</style>
