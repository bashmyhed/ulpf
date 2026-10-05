<script>
  import { onMount, onDestroy } from 'svelte'
  import { fmt } from './api.js'

  let { open = $bindable(true) } = $props()

  let alerts = $state([])
  let stats = $state({ total: 0, critical: 0, warn: 0, ml_count: 0, pipeline_count: 0 })
  let activeTab = $state('all') // 'all' | 'ml' | 'pipeline'
  let filterText = $state('')
  let expandedId = $state(null)
  let loading = $state(true)
  let pollTimer = null

  async function fetchAlerts() {
    try {
      const res = await fetch('/api/ulpf/alerts', {
        headers: { 'Authorization': 'Bearer admin-token' }
      })
      if (res.ok) {
        const data = await res.json()
        alerts = data.alerts || []
        stats = data.stats || { total: alerts.length, critical: 0, warn: alerts.length, ml_count: 0, pipeline_count: 0 }
      }
    } catch {
      // Fallback alerts if endpoint unavailable
      if (alerts.length === 0) {
        alerts = [
          {
            id: 'mock-ml-1',
            source: 'ml',
            category: 'data_quality',
            severity: 'warn',
            title: 'ML Anomaly: Unsupported Event Family',
            message: 'Topic ulpf-ocsf-events (partition 2, offset 95362)',
            node_id: 'server-parser',
            timestamp: new Date().toISOString(),
            resolved: false,
            details: { reason: ['unsupported_event_family'], status: 'data_quality' }
          }
        ]
      }
    } finally {
      loading = false
    }
  }

  async function resolveAlert(id) {
    try {
      await fetch(`/api/ulpf/alerts/${id}/resolve`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer admin-token' }
      })
      alerts = alerts.filter((a) => a.id !== id)
      stats.total = Math.max(0, stats.total - 1)
      if (expandedId === id) expandedId = null
    } catch {
      alerts = alerts.filter((a) => a.id !== id)
    }
  }

  async function dismissAll() {
    for (const a of alerts) {
      resolveAlert(a.id)
    }
  }

  const filteredAlerts = $derived.by(() => {
    let list = alerts
    if (activeTab === 'ml') list = list.filter((a) => a.source === 'ml')
    if (activeTab === 'pipeline') list = list.filter((a) => a.source === 'pipeline')
    if (filterText.trim()) {
      const q = filterText.trim().toLowerCase()
      list = list.filter((a) =>
        a.title.toLowerCase().includes(q) ||
        a.message.toLowerCase().includes(q) ||
        (a.category && a.category.toLowerCase().includes(q))
      )
    }
    return list
  })

  function toggleExpand(id) {
    expandedId = expandedId === id ? null : id
  }

  onMount(() => {
    fetchAlerts()
    pollTimer = setInterval(fetchAlerts, 4000)
  })

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer)
  })
</script>

<aside class="alerts-drawer" class:collapsed={!open}>
  <!-- Collapsed Toggle Handle -->
  {#if !open}
    <button class="expand-btn" onclick={() => (open = true)} title="Open Alert Drawer">
      <span class="rotate-label">
        <span class="pulse-dot" class:has-alerts={alerts.length > 0}></span>
        ALERTS ({alerts.length})
      </span>
    </button>
  {:else}
    <!-- Drawer Header -->
    <div class="drawer-header">
      <div class="title-group">
        <span class="drawer-title">
          <i class="alert-pulse" class:active={alerts.length > 0}></i>
          System Alerts
        </span>
        <span class="total-badge" class:has-items={alerts.length > 0}>{alerts.length}</span>
      </div>
      <div class="header-actions">
        {#if alerts.length > 0}
          <button class="btn-ghost xs" onclick={dismissAll} title="Dismiss all alerts">Clear All</button>
        {/if}
        <button class="btn-ghost icon" onclick={() => (open = false)} title="Collapse Alert Panel">
          &times;
        </button>
      </div>
    </div>

    <!-- Summary KPI Pills -->
    <div class="stat-pills">
      <div class="pill ml">
        <span class="pill-dot"></span>
        <span class="pill-name">ML Engine</span>
        <span class="pill-val">{stats.ml_count}</span>
      </div>
      <div class="pill pipe">
        <span class="pill-dot"></span>
        <span class="pill-name">Pipeline</span>
        <span class="pill-val">{stats.pipeline_count}</span>
      </div>
      {#if stats.critical > 0}
        <div class="pill crit">
          <span class="pill-dot"></span>
          <span class="pill-name">Critical</span>
          <span class="pill-val">{stats.critical}</span>
        </div>
      {/if}
    </div>

    <!-- Filter Tabs & Search -->
    <div class="tab-strip">
      <button class="tab-btn" class:active={activeTab === 'all'} onclick={() => (activeTab = 'all')}>
        All ({alerts.length})
      </button>
      <button class="tab-btn" class:active={activeTab === 'ml'} onclick={() => (activeTab = 'ml')}>
        ML Findings ({stats.ml_count})
      </button>
      <button class="tab-btn" class:active={activeTab === 'pipeline'} onclick={() => (activeTab = 'pipeline')}>
        Pipeline ({stats.pipeline_count})
      </button>
    </div>

    <div class="search-box">
      <input
        type="text"
        placeholder="Filter alerts..."
        bind:value={filterText}
      />
      {#if filterText}
        <button class="clear-search" onclick={() => (filterText = '')}>&times;</button>
      {/if}
    </div>

    <!-- Alert List Stream -->
    <div class="alert-stream">
      {#if loading && alerts.length === 0}
        <div class="empty-state">
          <span class="spinner"></span>
          <span>Polling anomaly detectors...</span>
        </div>
      {:else if filteredAlerts.length === 0}
        <div class="empty-state ok">
          <span class="empty-icon">&check;</span>
          <span class="empty-title">All Systems Normal</span>
          <span class="empty-desc">No active anomalies, drift violations, or pipeline errors detected.</span>
        </div>
      {:else}
        {#each filteredAlerts as alert (alert.id)}
          <div
            class="alert-card"
            class:crit={alert.severity === 'critical'}
            class:warn={alert.severity === 'warn'}
            class:ml={alert.source === 'ml'}
            class:expanded={expandedId === alert.id}
          >
            <div class="card-head" role="button" tabindex="0" onclick={() => toggleExpand(alert.id)}>
              <div class="badge-row">
                <span class="tag-source" class:ml={alert.source === 'ml'}>
                  {alert.source === 'ml' ? 'ML FINDING' : 'PIPELINE'}
                </span>
                <span class="tag-sev" class:crit={alert.severity === 'critical'} class:warn={alert.severity === 'warn'}>
                  {alert.severity ? alert.severity.toUpperCase() : 'WARN'}
                </span>
                {#if alert.node_id}
                  <span class="node-tag">{alert.node_id}</span>
                {/if}
                <span class="time-ago">
                  {fmt.ago(Math.max(1, Math.floor((Date.now() - new Date(alert.timestamp).getTime()) / 1000)))}
                </span>
              </div>
              <div class="card-title">{alert.title}</div>
              <div class="card-msg">{alert.message}</div>
            </div>

            <!-- Action footer -->
            <div class="card-foot">
              <button class="btn-dismiss" onclick={(e) => { e.stopPropagation(); resolveAlert(alert.id) }}>
                Dismiss
              </button>
              <button class="btn-details" onclick={() => toggleExpand(alert.id)}>
                {expandedId === alert.id ? 'Hide Details ▲' : 'Inspect ▼'}
              </button>
            </div>

            <!-- Expandable JSON Details -->
            {#if expandedId === alert.id && alert.details}
              <div class="details-tray">
                <pre class="json-dump">{JSON.stringify(alert.details, null, 2)}</pre>
              </div>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</aside>

<style>
  .alerts-drawer {
    width: 360px;
    height: 100vh;
    position: sticky;
    top: 0;
    background: var(--bg-1);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    z-index: 20;
    transition: width var(--d2) var(--ease);
    overflow: hidden;
  }

  .alerts-drawer.collapsed {
    width: 36px;
    background: var(--bg);
  }

  .expand-btn {
    width: 100%;
    height: 100%;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--fg-2);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
  }

  .expand-btn:hover {
    color: var(--fg);
    background: var(--bg-1);
  }

  .rotate-label {
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transform: rotate(180deg);
    font: 600 var(--t-1)/1 var(--mono);
    letter-spacing: 0.12em;
    display: flex;
    align-items: center;
    gap: var(--s3);
  }

  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ok);
  }

  .pulse-dot.has-alerts {
    background: var(--warn);
    animation: pulseWarn 1.6s infinite;
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s3) var(--s4);
    height: var(--top);
    border-bottom: 1px solid var(--line);
    background: var(--bg-2);
  }

  .title-group {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }

  .drawer-title {
    font: 600 var(--t1)/1 var(--sans);
    color: var(--fg);
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .alert-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--ok);
  }

  .alert-pulse.active {
    background: var(--warn);
    animation: pulseWarn 1.6s infinite;
  }

  @keyframes pulseWarn {
    0% { transform: scale(0.95); opacity: 0.8; }
    50% { transform: scale(1.2); opacity: 1; box-shadow: 0 0 8px var(--warn); }
    100% { transform: scale(0.95); opacity: 0.8; }
  }

  .total-badge {
    font: 600 var(--t-1)/1 var(--mono);
    padding: 2px 6px;
    border-radius: 10px;
    background: var(--bg-1);
    color: var(--fg-2);
    border: 1px solid var(--line);
  }

  .total-badge.has-items {
    background: var(--warn-bg);
    color: var(--warn);
    border-color: var(--warn);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .btn-ghost {
    background: none;
    border: none;
    color: var(--fg-2);
    cursor: pointer;
    font-size: var(--t0);
    padding: 2px 6px;
    border-radius: 2px;
  }

  .btn-ghost:hover {
    color: var(--fg);
    background: var(--bg-1);
  }

  .btn-ghost.xs {
    font-size: var(--t-1);
  }

  .btn-ghost.icon {
    font-size: var(--t3);
    line-height: 1;
  }

  .stat-pills {
    display: flex;
    gap: var(--s2);
    padding: var(--s2) var(--s4);
    background: var(--bg);
    border-bottom: 1px solid var(--line);
  }

  .pill {
    flex: 1;
    display: flex;
    align-items: center;
    gap: var(--s1);
    padding: 4px 6px;
    border-radius: 3px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    font-size: var(--t-1);
  }

  .pill.ml .pill-dot { background: #5ec6d0; }
  .pill.pipe .pill-dot { background: #e2a83f; }
  .pill.crit .pill-dot { background: var(--bad); }

  .pill-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
  }

  .pill-name {
    color: var(--fg-2);
    flex: 1;
  }

  .pill-val {
    font-family: var(--mono);
    font-weight: 600;
    color: var(--fg);
  }

  .tab-strip {
    display: flex;
    border-bottom: 1px solid var(--line);
    background: var(--bg-1);
  }

  .tab-btn {
    flex: 1;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    padding: var(--s2) var(--s1);
    font-size: var(--t-1);
    color: var(--fg-2);
    cursor: pointer;
    text-align: center;
  }

  .tab-btn:hover {
    color: var(--fg);
    background: var(--bg-2);
  }

  .tab-btn.active {
    color: var(--fg);
    border-bottom-color: var(--fg);
    font-weight: 600;
  }

  .search-box {
    position: relative;
    padding: var(--s2) var(--s4);
    border-bottom: 1px solid var(--line);
    background: var(--bg);
  }

  .search-box input {
    width: 100%;
    padding: 4px var(--s3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 2px;
    font-size: var(--t0);
    color: var(--fg);
  }

  .search-box input:focus {
    border-color: var(--line-3);
    outline: none;
  }

  .clear-search {
    position: absolute;
    right: 22px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--fg-2);
    cursor: pointer;
    font-size: var(--t2);
  }

  .alert-stream {
    flex: 1;
    overflow-y: auto;
    padding: var(--s3) var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }

  .empty-state {
    padding: var(--s7) var(--s4);
    text-align: center;
    color: var(--fg-2);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s2);
  }

  .empty-state.ok .empty-icon {
    font-size: var(--t4);
    color: var(--ok);
  }

  .empty-title {
    font-weight: 600;
    color: var(--fg);
    font-size: var(--t1);
  }

  .empty-desc {
    font-size: var(--t0);
    max-width: 240px;
    line-height: 1.4;
  }

  .alert-card {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-left: 3px solid var(--warn);
    border-radius: 3px;
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    transition: background var(--d1);
  }

  .alert-card.crit {
    border-left-color: var(--bad);
    background: var(--bad-bg);
  }

  .alert-card.ml {
    border-left-color: #5ec6d0;
  }

  .alert-card:hover {
    border-color: var(--line-2);
  }

  .card-head {
    cursor: pointer;
  }

  .badge-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    margin-bottom: var(--s1);
  }

  .tag-source {
    font: 600 10px/1 var(--mono);
    padding: 1px 4px;
    border-radius: 2px;
    background: var(--line-2);
    color: var(--fg);
  }

  .tag-source.ml {
    background: #0f7a86;
    color: #fff;
  }

  .tag-sev {
    font: 600 10px/1 var(--mono);
    padding: 1px 4px;
    border-radius: 2px;
  }

  .tag-sev.warn {
    background: var(--warn-bg);
    color: var(--warn);
    border: 1px solid var(--warn);
  }

  .tag-sev.crit {
    background: var(--bad);
    color: #fff;
  }

  .node-tag {
    font: var(--t-1) var(--mono);
    color: var(--fg-2);
  }

  .time-ago {
    margin-left: auto;
    font-size: var(--t-1);
    color: var(--fg-2);
  }

  .card-title {
    font-weight: 600;
    font-size: var(--t0);
    color: var(--fg);
    line-height: 1.3;
  }

  .card-msg {
    font-size: var(--t-1);
    color: var(--fg-1);
    margin-top: 2px;
    word-break: break-word;
  }

  .card-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid var(--line);
    padding-top: var(--s2);
    margin-top: var(--s1);
  }

  .btn-dismiss {
    background: none;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    color: var(--fg-1);
    font-size: var(--t-1);
    padding: 2px 6px;
    cursor: pointer;
  }

  .btn-dismiss:hover {
    color: var(--bad);
    border-color: var(--bad);
  }

  .btn-details {
    background: none;
    border: none;
    color: var(--fg-2);
    font-size: var(--t-1);
    cursor: pointer;
  }

  .btn-details:hover {
    color: var(--fg);
  }

  .details-tray {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 2px;
    padding: var(--s2);
    margin-top: var(--s2);
    max-height: 200px;
    overflow-y: auto;
  }

  .json-dump {
    font-size: 11px;
    color: var(--fg-1);
  }
</style>
