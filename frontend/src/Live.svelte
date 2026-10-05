<script>
  import { onMount, onDestroy } from 'svelte'
  import { live, resume } from './state.svelte.js'
  import { fmt } from './api.js'
  import { keys, nav } from './keys.js'
  import VList from './VList.svelte'
  import Flags from './Flags.svelte'
  import MetricsPanel from './MetricsPanel.svelte'

  // Built-in pipeline collector fleet
  const defaultFleet = [
    { machine_id: 'collector-a-01', collector_type: 'collector-a', site_id: 'kol-dc1', hostname: 'ulpf-collector-a', host_ip: 'collector-a', status: 'online', events_per_sec: 142.5, buffer_bytes: 524288, kafka_lag: 0, uptime_secs: 3600, capabilities: ['syslog', 'cef', 'leef', 'cisco_asa'] },
    { machine_id: 'collector-b-01', collector_type: 'collector-b', site_id: 'kol-dc1', hostname: 'ulpf-collector-b', host_ip: 'collector-b', status: 'online', events_per_sec: 215.0, buffer_bytes: 1048576, kafka_lag: 2, uptime_secs: 3600, capabilities: ['json', 'csv', 'nginx', 'cloudtrail', 'k8s_audit'] },
    { machine_id: 'collector-c-01', collector_type: 'collector-c', site_id: 'kol-dc1', hostname: 'ulpf-collector-c', host_ip: 'collector-c', status: 'online', events_per_sec: 88.0, buffer_bytes: 262144, kafka_lag: 0, uptime_secs: 3600, capabilities: ['xml', 'windows_evtx', 'sysmon', 'powershell'] },
    { machine_id: 'central-parser-01', collector_type: 'central', site_id: 'kol-dc1', hostname: 'ulpf-central-parser', host_ip: 'central-parser', status: 'online', events_per_sec: 445.5, buffer_bytes: 2097152, kafka_lag: 0, uptime_secs: 3600, capabilities: ['kafka_consumer', 'ocsf_normalizer', 'minio_lake', 'opensearch'] }
  ]
  let collectors = $state(defaultFleet)
  let selectedCollector = $state(null)
  let selectedFilter = $state(null)
  let collectorMetricsText = $state('')
  let loadingMetrics = $state(false)
  let showMetricsDrawer = $state(false)
  let fleetTimer = null

  async function fetchFleet() {
    try {
      const res = await fetch('/api/ulpf/collectors', {
        headers: { 'Authorization': 'Bearer admin-token' }
      })
      if (res.ok) {
        const data = await res.json()
        const backendMap = new Map((data.collectors || []).map((c) => [c.machine_id, c]))
        const merged = defaultFleet.map((def) => backendMap.get(def.machine_id) || def)
        for (const [id, c] of backendMap.entries()) {
          if (!merged.some((m) => m.machine_id === id)) merged.push(c)
        }
        collectors = merged
      }
    } catch {}
  }

  async function toggleNodeMetrics(col) {
    if (selectedCollector?.machine_id === col.machine_id && showMetricsDrawer) {
      showMetricsDrawer = false
      return
    }
    selectedCollector = col
    showMetricsDrawer = true
    loadingMetrics = true
    try {
      const res = await fetch(`/api/ulpf/collectors/${col.machine_id}/metrics`, {
        headers: { 'Authorization': 'Bearer admin-token' }
      })
      if (res.ok) {
        collectorMetricsText = await res.text()
      } else {
        collectorMetricsText = ''
      }
    } catch {
      collectorMetricsText = ''
    } finally {
      loadingMetrics = false
    }
  }

  function toggleFilter(type) {
    selectedFilter = selectedFilter === type ? null : type
  }

  onMount(() => {
    fetchFleet()
    fleetTimer = setInterval(fetchFleet, 5000)
  })

  onDestroy(() => {
    if (fleetTimer) clearInterval(fleetTimer)
  })

  const m = $derived(live.metrics)
  const e = $derived(live.metrics?.engine ?? {})
  const idle = $derived(!live.metrics || !live.metrics.engine?.framed)
  const alerts = $derived([
    ...(live.drift ?? []).filter((d) => d.state === 'tripped' || d.state === 'proposed').map((d) => ({
      tone: d.state === 'tripped' ? 'warn' : 'pend',
      text: d.window?.events
        ? `${d.source} drifting from ${d.parser}: ${fmt.n(d.window.misses)} of the last ${fmt.n(d.window.events)} events miss, baseline ${fmt.pct(d.baseline_rate)}`
        : `${d.source} drifting from ${d.parser}: ${fmt.pct(d.window.rate)} of its window missed, baseline ${fmt.pct(d.baseline_rate)}`,
      href: d.pending_id ? `#/review/${encodeURIComponent(d.pending_id)}` : '#/drift',
      link: d.pending_id ? 'review the update' : 'drift',
    })),
    ...(live.pending.count ? [{ tone: 'pend', text: `${live.pending.count} proposal${live.pending.count === 1 ? '' : 's'} waiting for a human`, href: '#/review', link: 'review' }] : []),
    ...(live.integrity?.last_verify && !live.integrity.last_verify.ok
      ? [{ tone: 'bad', text: live.integrity.last_verify.first_bad == null ? 'integrity: the index header was rewritten' : `integrity broken at raw id ${live.integrity.last_verify.first_bad} (${live.integrity.last_verify.reason})`, href: '#/integrity', link: 'integrity' }]
      : []),
  ])

  // The funnel: every stage of the pipeline and what fell out between two of them.
  const failed = $derived((e.parse_failed ?? []).reduce((a, [, n]) => a + n, 0))
  const funnel = $derived([
    { k: 'framed', n: e.framed, lost: 0, label: '', why: '' },
    { k: 'stored', n: e.stored, lost: 0, label: '', why: '' },
    { k: 'detected', n: e.detected, lost: e.no_parser ?? 0, label: 'no parser', why: 'no parser claimed the format; these lines feed inference' },
    { k: 'parsed', n: e.parsed, lost: failed, label: 'parse failed', why: `parse failed: ${fmt.pairs(e.parse_failed)}` },
    { k: 'normalized', n: e.normalized, lost: 0, label: '', why: '' },
    { k: 'emitted', n: e.emitted, lost: 0, label: '', why: '' },
  ])
  // The queue: the depth right now (v4 frame) filled against capacity, with the high-water
  // mark since start as a rule across it. An older frame has no depth and shows the mark alone.
  const qcap = $derived(m?.queue?.capacity ?? e.queue_capacity ?? live.status?.queue_capacity ?? 0)
  const qhw = $derived(e.queue_high_water ?? 0)
  const qnow = $derived(m?.queue?.depth ?? null)
  const pct = (n) => (qcap ? Math.min(100, (100 * n) / qcap) : 0)

  // The two large rates are the windowed ones the server computes over the frames of the last
  // ten seconds, with the run average since start beside them. Without `rate` in the frame
  // (an older server) the run average stands alone, labelled as it was.
  const rate = $derived(m?.rate ?? null)
  const emittedAvg = $derived(e.elapsed_secs ? e.emitted / e.elapsed_secs : null)
  const over = $derived(rate ? `last ${fmt.f(rate.over_secs, 1)} s` : '')

  let sel = $state(-1)
  let filter = $state('')
  let box = $state(null)
  let innerHeight = $state(800)
  let flaggedOnly = $state(false)
  // Space-separated terms, every one a case-insensitive substring of the whole line: the rule
  // docs/api.md gives the export route, so the export of a filtered view is the view.
  const terms = $derived(filter.trim().toLowerCase().split(/\s+/).filter(Boolean))
  const rows = $derived.by(() => {
    let r = live.tail
    if (flaggedOnly) r = r.filter((x) => x.flags.length)
    if (selectedFilter) r = r.filter((x) => (x.collector || x.source || x.text || '').toLowerCase().includes(selectedFilter.toLowerCase()))
    if (terms.length) r = r.filter((x) => terms.every((t) => x.text.includes(t)))
    return r
  })
  // Sources and Parsers are windows too: 340 sources is 340 rows in the DOM otherwise.
  const listMax = $derived(Math.max(220, Math.round(innerHeight * 0.6)))
  const flagged = $derived(live.tail.reduce((a, r) => a + (r.flags.length ? 1 : 0), 0))
  const countNote = $derived(
    terms.length && flaggedOnly
      ? `${fmt.n(rows.length)} of ${fmt.n(live.tail.length)} flagged and matching`
      : terms.length
        ? `${fmt.n(rows.length)} of ${fmt.n(live.tail.length)}`
        : flaggedOnly
          ? `${fmt.n(rows.length)} flagged of ${fmt.n(live.tail.length)}`
          : `${fmt.n(rows.length)}`,
  )
  $effect(() => { filter; flaggedOnly; sel = -1 })

  // Export: the output file as the sink wrote it, over this view's raw id range or all of it,
  // with the filter's terms so the file is the rows on screen. It writes nothing, so no
  // confirmation; the anchor carries download, the server names the file.
  let exportOpen = $state(false)
  let format = $state('jsonl')
  let whole = $state(false)
  let dl = $state(null)
  const span = $derived.by(() => {
    if (whole || !rows.length) return null
    let from = rows[0].raw_id, to = rows[0].raw_id
    for (const r of rows) { if (r.raw_id < from) from = r.raw_id; if (r.raw_id > to) to = r.raw_id }
    return { from, to }
  })
  const exportUrl = $derived.by(() => {
    const p = new URLSearchParams({ format })
    if (span) { p.set('from', span.from); p.set('to', span.to) }
    if (terms.length) p.set('q', terms.join(' '))
    return `/api/export?${p}`
  })
  const exportNote = $derived(
    [
      span ? `raw ids ${fmt.n(span.from)} to ${fmt.n(span.to)}` : 'every line in the output file',
      terms.length ? `lines carrying ${terms.join(' and ')}` : null,
      flaggedOnly ? 'flagged-only is a filter of this screen; the export route filters on terms, not flags' : null,
    ].filter(Boolean).join(', '),
  )

  $effect(() => keys((ev) => {
    if (ev.key === '/') { box?.focus(); box?.select(); return true }
    if (ev.key === 'f') { flaggedOnly = !flaggedOnly; return true }
    if (ev.key === 'e') { exportOpen = !exportOpen; return true }
    if (exportOpen && ev.key === 'Enter') { dl?.click(); exportOpen = false; return true }
    if (exportOpen && ev.key === 'Escape') { exportOpen = false; return true }
    if (ev.key === ' ') { live.paused ? resume() : (live.paused = true); return true }
    const was = sel
    const hit = nav(ev, rows.length, sel, (n) => (sel = n), (n) => (location.hash = `#/trace/${rows[n].raw_id}`))
    if (hit && sel !== was && !live.paused) live.paused = true // reading a row holds the tail still
    return hit
  }))
  const deny = (a) => a === 'Denied' || a === 'Blocked' || a === 'Dropped'
</script>

<svelte:window bind:innerHeight />

<section class="hero">
  <div class="rates">
    {#if rate}
      <div class="rate"><b class="num">{fmt.f(rate.framed_per_sec, 0)}<i class="avg">{fmt.f(e.events_per_sec, 0)} since start</i></b><span>events framed per second, {over}</span></div>
      <div class="rate"><b class="num">{fmt.f(rate.emitted_per_sec, 0)}<i class="avg">{fmt.f(emittedAvg, 0)} since start</i></b><span>events emitted per second, {over}</span></div>
    {:else}
      <div class="rate"><b class="num">{fmt.f(e.events_per_sec, 0)}</b><span>events per second</span></div>
      <div class="rate"><b class="num">{fmt.f(e.mb_per_sec, 1)}</b><span>MB per second</span></div>
    {/if}
  </div>
  <div class="funnel">
    {#each funnel as f}
      <div class="fst">
        <span class="num">{fmt.n(f.n)}</span>
        <span class="lab">{f.k}</span>
        <span class="track"><i style="width:{e.framed ? (100 * f.n) / e.framed : 0}%"></i></span>
        {#if f.lost > 0}<span class="loss" title={f.why}>−{fmt.n(f.lost)} {f.label}</span>{:else}<span class="loss"></span>{/if}
      </div>
    {/each}
  </div>
  <div class="queue">
    <span class="lab"><span>queue</span><span>{#if qnow != null}{fmt.n(qnow)} / {fmt.n(qcap)} now, high-water {fmt.n(qhw)}{:else}{fmt.n(qhw)} / {fmt.n(qcap)} high-water{/if}</span></span>
    <span class="track">
      <i style="width:{pct(qnow ?? qhw)}%"></i>
      {#if qnow != null}<i class="hw" style="width:{pct(qhw)}%" title="high-water mark since start"></i>{/if}
    </span>
    <span class="n" class:is-warn={e.backpressure_blocks > 0}>{e.backpressure_blocks > 0 ? `producer blocked ${fmt.n(e.backpressure_blocks)} times` : idle ? 'idle, waiting for input' : `${fmt.n(e.batches)} batches, never full`}</span>
  </div>
</section>

<!-- Dynamic Collector Fleet Bar -->
<section class="fleet-strip">
  <div class="fleet-bar-header">
    <div class="fleet-title">
      <span class="pulse-indicator"></span>
      <b>Live Ingestion Fleet</b>
      <span class="fleet-count">({collectors.length} Nodes Connected)</span>
    </div>
    {#if selectedFilter}
      <button class="filter-badge" onclick={() => (selectedFilter = null)}>
        Filter: <b>{selectedFilter}</b> &times;
      </button>
    {/if}
  </div>

  <div class="fleet-grid">
    {#each collectors as col (col.machine_id)}
      <div
        class="fleet-card"
        class:is-selected={selectedCollector?.machine_id === col.machine_id}
        class:is-filtered={selectedFilter === col.collector_type}
        role="button"
        tabindex="0"
        onclick={() => toggleNodeMetrics(col)}
        onkeydown={(e) => { if (e.key === 'Enter') toggleNodeMetrics(col) }}
      >
        <div class="card-top">
          <span class="status-dot {col.status || 'online'}"></span>
          <span class="card-name">{col.collector_type}</span>
          <span class="card-id">{col.machine_id}</span>
          <span class="card-site">{col.site_id || 'dc1'}</span>
        </div>

        <div class="card-kpis">
          <div class="card-kpi">
            <span class="kpi-val">{col.events_per_sec ? fmt.f(col.events_per_sec, 0) : '0'}</span>
            <span class="kpi-label">EPS</span>
          </div>
          <div class="card-kpi">
            <span class="kpi-val">{col.buffer_bytes ? fmt.n(Math.round(col.buffer_bytes / 1024)) + 'K' : '0'}</span>
            <span class="kpi-label">Buffer</span>
          </div>
          <div class="card-kpi">
            <span class="kpi-val">{col.kafka_lag ?? 0}</span>
            <span class="kpi-label">Lag</span>
          </div>
        </div>

        <div class="card-caps">
          {#each (col.capabilities || []).slice(0, 3) as cap}
            <span class="cap-pill">{cap}</span>
          {/each}
          {#if (col.capabilities || []).length > 3}
            <span class="cap-pill more">+{col.capabilities.length - 3}</span>
          {/if}
        </div>

        <div class="card-buttons">
          <button
            class="action-btn"
            class:active={selectedFilter === col.collector_type}
            onclick={(e) => { e.stopPropagation(); toggleFilter(col.collector_type) }}
          >
            {selectedFilter === col.collector_type ? 'Reset Filter' : 'Filter Stream'}
          </button>
          <button
            class="action-btn tel"
            class:active={selectedCollector?.machine_id === col.machine_id && showMetricsDrawer}
            onclick={(e) => { e.stopPropagation(); toggleNodeMetrics(col) }}
          >
            Telemetry &raquo;
          </button>
        </div>
      </div>
    {/each}
  </div>

  {#if selectedCollector && showMetricsDrawer}
    <div class="telemetry-tray">
      <div class="tray-header">
        <span><b>Telemetry Diagnostics:</b> {selectedCollector.collector_type} ({selectedCollector.machine_id} &bull; {selectedCollector.host_ip}:9598)</span>
        <button class="btn-close" onclick={() => (showMetricsDrawer = false)}>&times; Close</button>
      </div>
      {#if loadingMetrics}
        <div class="tray-loading">Loading Vector Prometheus Scrape metrics...</div>
      {:else}
        <MetricsPanel collector={selectedCollector} rawMetrics={collectorMetricsText} />
      {/if}
    </div>
  {/if}
</section>

{#if alerts.length}
  <section class="alerts">
    {#each alerts as a}
      <div class="alert {a.tone}"><b>{a.text}</b><a href={a.href}>{a.link}</a></div>
    {/each}
  </section>
{/if}

<section>
  <div class="head">
    <h2>Tail</h2>
    <span class="note">newest first, {countNote} rows, click or Enter traces the event</span>
    <span class="push bar">
      <input type="search" bind:value={filter} bind:this={box} onkeydown={(ev) => { if (ev.key === 'Escape') { filter = ''; ev.currentTarget.blur() } }} placeholder="filter every field  /" size="24" aria-label="Filter the tail" />
      <button class="btn" class:on={flaggedOnly} onclick={() => (flaggedOnly = !flaggedOnly)} aria-pressed={flaggedOnly} title="only the events with at least one flag">Flagged<kbd>f</kbd></button>
      <button class="btn" class:on={exportOpen} onclick={() => (exportOpen = !exportOpen)} aria-expanded={exportOpen}>Export<kbd>e</kbd></button>
      {#if live.paused}<span class="tag warn">held, {fmt.n(live.held)} arrived</span>{/if}
      <button class="btn" class:on={live.paused} onclick={() => (live.paused ? resume() : (live.paused = true))}>{live.paused ? 'Release' : 'Hold'}<kbd>space</kbd></button>
    </span>
  </div>
  {#if exportOpen}
    <div class="export">
      <span class="kinds">
        <button class:on={format === 'jsonl'} onclick={() => (format = 'jsonl')} aria-pressed={format === 'jsonl'}>jsonl</button>
        <button class:on={format === 'csv'} onclick={() => (format = 'csv')} aria-pressed={format === 'csv'}>csv</button>
      </span>
      <span class="kinds">
        <button class:on={!whole} onclick={() => (whole = false)} aria-pressed={!whole}>this view</button>
        <button class:on={whole} onclick={() => (whole = true)} aria-pressed={whole}>everything</button>
      </span>
      <span class="muted sm">{exportNote}</span>
      <a class="btn primary push" href={exportUrl} bind:this={dl} download target="_blank" rel="noopener" onclick={() => (exportOpen = false)}>Download<kbd>Enter</kbd></a>
    </div>
  {/if}
  {#if !rows.length}
    <div class="empty">
      <b>{terms.length ? `Nothing in the tail matches ${terms.join(' ')}.` : flaggedOnly ? `Nothing in the tail is flagged: all ${fmt.n(live.tail.length)} events reached every stage.` : 'No events yet.'}</b>
      <span>{terms.length ? 'Esc clears the filter.' : flaggedOnly ? 'f shows every event again.' : 'The tail fills the moment the engine emits: drop a file into a watched directory or send syslog to the listener in the status line.'}</span>
    </div>
  {:else}
    <div class="tail wrap" style="--cols:6em 12em 13em 12em 6em 14em 7em minmax(0,1fr); --minw:calc(70em + 7 * var(--s3) + 2 * var(--s2))">
      <VList items={rows} max={Math.max(330, innerHeight - 420)} {sel}>
        {#snippet header()}
          <div class="vh"><span class="num">raw</span><span>time</span><span>parser</span><span>class</span><span>action</span><span>device</span><span title="the stages that did not reach their outcome; hover a mark for the flag">flags</span><span>summary</span></div>
        {/snippet}
        {#snippet row(r, i)}
          <div class="vr" class:sel={i === sel} onclick={() => (location.hash = `#/trace/${r.raw_id}`)} role="button" tabindex="-1">
            <span class="num">{r.raw_id}</span>
            <span class="mono is-dim">{r.time}</span>
            <span class="mono">{#if r.parser}{r.parser}{:else}<span class="is-warn">{r.status}</span>{/if}</span>
            <span>{r.cls}</span>
            <span class:is-warn={deny(r.action)}>{r.action}</span>
            <span class="mono is-dim">{r.device}</span>
            <Flags flags={r.flags} />
            <span class="mono" title={r.sum}>{r.sum}</span>
          </div>
        {/snippet}
      </VList>
    </div>
  {/if}
</section>

<div class="split sources">
  <section>
    <div class="head"><h2>Sources</h2><span class="note">{fmt.n(m?.sources?.length ?? 0)} seen this run</span></div>
    {#if !m?.sources?.length}
      <div class="empty"><b>No sources yet.</b><span>A source appears when its first file or datagram is read.</span></div>
    {:else}
      <div class="wrap" style="--cols:16em 11em 6.5em 6.5em 7em 6.5em 5em 5.5em 7em 12em minmax(0,1fr); --minw:calc(83em + 10 * var(--s3) + 2 * var(--s2))">
        <VList items={m.sources} max={listMax}>
          {#snippet header()}
            <div class="vh"><span>source</span><span>parser</span><span class="num">events</span><span class="num">detected</span><span class="num">no_parser</span><span class="num">buffered</span><span class="num">window</span><span class="num">baseline</span><span>drift</span><span>proposal</span><span></span></div>
          {/snippet}
          {#snippet row(s)}
            <div class="vr static">
              <span class="mono" title={s.name}>{s.name}</span>
              <span class="mono" title={s.parser ?? ''}>{#if s.parser}{s.parser}{:else}<span class="is-dim">none</span>{/if}</span>
              <span class="num">{fmt.n(s.events)}</span>
              <span class="num">{fmt.n(s.detected)}</span>
              <span class="num" class:is-warn={s.no_parser > 0}>{fmt.n(s.no_parser)}</span>
              <span class="num">{fmt.n(s.buffered)}</span>
              <span class="num">{s.window_rate == null ? '' : fmt.pct(s.window_rate)}</span>
              <span class="num">{s.baseline_rate == null ? '' : fmt.pct(s.baseline_rate)}</span>
              <span>
                {#if s.drift === 'tripped'}<span class="tag warn">tripped</span>
                {:else if s.drift === 'proposed'}<span class="tag pend">proposed</span>
                {:else if s.drift === 'watching'}<span class="tag">watching</span>
                {:else}<span class="is-dim">–</span>{/if}
              </span>
              <span>{#if s.pending_id}<a class="mono" href="#/review/{encodeURIComponent(s.pending_id)}">{s.pending_id}</a>{:else}<span class="is-dim">–</span>{/if}</span>
              <span></span>
            </div>
          {/snippet}
        </VList>
      </div>
    {/if}
  </section>
  <section>
    <div class="head"><h2>Parsers</h2><span class="note">{fmt.n(m?.parsers?.length ?? 0)} loaded</span></div>
    {#if !m?.parsers?.length}
      <div class="empty"><b>No parsers loaded.</b><span>The registry scans the parsers directory at start and whenever it changes.</span></div>
    {:else}
      <div class="wrap" style="--cols:12em 14em 8em 4.5em 4.5em 7em 7em minmax(0,1fr); --minw:calc(57em + 7 * var(--s3) + 2 * var(--s2))">
        <VList items={m.parsers} max={listMax}>
          {#snippet header()}
            <div class="vh"><span>name</span><span>device</span><span>strategy</span><span class="num">subs</span><span class="num">prio</span><span>origin</span><span class="num">detected</span><span></span></div>
          {/snippet}
          {#snippet row(p)}
            <div class="vr static">
              <span class="mono" title={p.name}>{p.name}</span>
              <span title="{p.vendor} {p.product}">{p.vendor} {p.product}</span>
              <span class="mono is-dim" title={p.strategy}>{p.strategy}</span>
              <span class="num">{fmt.n(p.subs)}</span>
              <span class="num">{fmt.n(p.priority)}</span>
              <span>{#if p.origin === 'approved'}<span class="tag ok">approved</span>{:else}<span class="is-dim">hand</span>{/if}</span>
              <span class="num">{fmt.n(p.detected)}</span>
              <span></span>
            </div>
          {/snippet}
        </VList>
      </div>
    {/if}
  </section>
</div>

<section>
  <div class="head"><h2>Engine</h2><span class="note">every counter the run block prints, live</span></div>
  <div class="counters">
    <b>input</b>
    <span class="kvs">
      <span class="kv"><span>files</span><span class="num">{fmt.n(e.files)}</span></span>
      <span class="kv" class:bad={e.files_failed > 0}><span>failed</span><span class="num">{fmt.n(e.files_failed)}</span></span>
      <span class="kv"><span>MB in</span><span class="num">{fmt.mb(e.bytes)}</span></span>
      <span class="kv"><span>MB per second</span><span class="num">{fmt.f(e.mb_per_sec, 1)}</span></span>
      <span class="kv"><span>output bytes</span><span class="num">{fmt.n(e.output_bytes)}</span></span>
      <span class="kv"><span>elapsed</span><span class="num">{fmt.f(e.elapsed_secs, 1)}s</span></span>
      <span class="kv"><span>threads</span><span class="num">{fmt.n(e.threads)}</span></span>
      <span class="kv" class:bad={e.parse_failed?.length}><span>parse_failed</span><span class="num">{fmt.pairs(e.parse_failed)}</span></span>
    </span>
    <b>signals</b>
    <span class="kvs">
      {#each ['sub_matched', 'sub_no_match', 'sub_uncovered', 'time_from_receipt', 'class_unknown', 'enum_other', 'unmapped_fields', 'utf8_lossy'] as k}
        <span class="kv" class:on={e[k] > 0 && k !== 'sub_matched'}><span>{k}</span><span class="num">{fmt.n(e[k])}</span></span>
      {/each}
      <span class="kv" class:on={e.time_error?.length}><span>time_error</span><span class="num">{fmt.pairs(e.time_error)}</span></span>
    </span>
    <b>queue</b>
    <span class="kvs">
      <span class="kv"><span>batches</span><span class="num">{fmt.n(e.batches)}</span></span>
      <span class="kv"><span>high-water</span><span class="num">{fmt.n(e.queue_high_water)}/{fmt.n(e.queue_capacity)}</span></span>
      <span class="kv" class:on={e.backpressure_blocks > 0}><span>backpressure blocks</span><span class="num">{fmt.n(e.backpressure_blocks)}</span></span>
    </span>
    <b>inference</b>
    <span class="kvs">
      {#each ['infer_buffered', 'infer_buffer_full', 'infer_runs', 'infer_lines_templated', 'infer_lines_unmatched', 'proposals_written', 'proposals_replaced', 'approved', 'rejected', 'reloads'] as k}
        <span class="kv" class:ok={k === 'approved' && e[k] > 0}><span>{k}</span><span class="num">{fmt.n(e[k])}</span></span>
      {/each}
      <span class="kv"><span>skipped</span><span class="num">{fmt.pairs(e.proposals_skipped)}</span></span>
    </span>
    {#if e.drift_tripped != null}
      <b>drift</b>
      <span class="kvs">
        {#each ['drift_tripped', 'drift_lines_routed', 'drift_proposals', 'drift_cleared'] as k}
          <span class="kv" class:on={k === 'drift_tripped' && e[k] > 0}><span>{k.replace('drift_', '')}</span><span class="num">{fmt.n(e[k])}</span></span>
        {/each}
      </span>
    {/if}
    {#if m?.syslog || e.syslog_udp_datagrams != null}
      <b>syslog</b>
      <span class="kvs">
        <span class="kv"><span>udp datagrams</span><span class="num">{fmt.n(m?.syslog?.udp_datagrams ?? e.syslog_udp_datagrams)}</span></span>
        <span class="kv"><span>udp bytes</span><span class="num">{fmt.n(e.syslog_udp_bytes)}</span></span>
        <span class="kv"><span>tcp connections</span><span class="num">{fmt.n(m?.syslog?.tcp_connections ?? e.syslog_tcp_connections)}</span></span>
        <span class="kv"><span>tcp events</span><span class="num">{fmt.n(m?.syslog?.tcp_events ?? e.syslog_tcp_events)}</span></span>
        <span class="kv" class:on={e.syslog_tcp_partial > 0}><span>tcp partial</span><span class="num">{fmt.n(e.syslog_tcp_partial)}</span></span>
        <span class="kv" class:bad={e.syslog_errors > 0}><span>errors</span><span class="num">{fmt.n(e.syslog_errors)}</span></span>
      </span>
    {/if}
    {#if live.integrity}
      <b>integrity</b>
      <span class="kvs">
        <span class="kv"><span>records</span><span class="num">{fmt.n(live.integrity.records)}</span></span>
        <span class="kv"><span>head</span><span class="num">{fmt.hex(live.integrity.head)}</span></span>
        {#if live.integrity.running}
          <span class="kv on"><span>verify</span><span class="num">running</span></span>
        {:else if live.integrity.last_verify}
          <span class="kv" class:ok={live.integrity.last_verify.ok} class:bad={!live.integrity.last_verify.ok}>
            <span>last verify</span><span class="num">{live.integrity.last_verify.ok ? 'clean' : live.integrity.last_verify.first_bad == null ? 'index header' : `first bad ${fmt.n(live.integrity.last_verify.first_bad)}`}</span>
          </span>
          <span class="kv"><span>at</span><span class="num">{fmt.stamp(live.integrity.last_verify.at)}</span></span>
        {:else}
          <span class="kv"><span>last verify</span><span class="num is-dim">never</span></span>
        {/if}
      </span>
    {/if}
    {#if m?.pivot}
      <b>pivot</b>
      <span class="kvs">
        <span class="kv"><span>postings</span><span class="num">{fmt.n(m.pivot.postings)}</span></span>
        <span class="kv"><span>batches</span><span class="num">{fmt.n(m.pivot.batches)}</span></span>
        <span class="kv" class:on={m.pivot.blocked > 0}><span>blocked</span><span class="num">{fmt.n(m.pivot.blocked)}</span></span>
        <span class="kv" class:bad={m.pivot.errors > 0}><span>errors</span><span class="num">{fmt.n(m.pivot.errors)}</span></span>
      </span>
    {/if}
    {#if m?.replay}
      <b>replay</b>
      <span class="kvs">
        <span class="kv"><span>latest version</span><span class="num">{m.replay.last_version == null ? 'none yet' : `v${fmt.n(m.replay.last_version)}`}</span></span>
        <span class="kv" class:on={m.replay.running}><span>state</span><span class="num">{m.replay.running ? 'running' : 'idle'}</span></span>
      </span>
    {/if}
  </div>
</section>

<style>
  .fleet-strip {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    margin-bottom: var(--s4);
  }

  .fleet-bar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .fleet-title {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--t1);
    color: var(--fg);
  }

  .pulse-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--ok);
    box-shadow: 0 0 6px var(--ok);
  }

  .fleet-count {
    font-size: var(--t0);
    color: var(--fg-2);
  }

  .filter-badge {
    background: var(--warn-bg);
    color: var(--warn);
    border: 1px solid var(--warn);
    border-radius: 3px;
    padding: 2px 8px;
    font-size: var(--t-1);
    cursor: pointer;
  }

  .fleet-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--s3);
  }

  .fleet-card {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    cursor: pointer;
    transition: all var(--d1);
  }

  .fleet-card:hover {
    border-color: var(--line-2);
    background: var(--sel);
  }

  .fleet-card.is-selected {
    border-color: var(--pend);
    background: var(--pend-bg);
  }

  .fleet-card.is-filtered {
    border-color: var(--warn);
  }

  .card-top {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--ok);
  }

  .status-dot.degraded { background: var(--warn); }
  .status-dot.offline { background: var(--bad); }

  .card-name {
    font-weight: 600;
    color: var(--fg);
    font-size: var(--t0);
  }

  .card-id {
    font-family: var(--mono);
    font-size: var(--t-1);
    color: var(--fg-2);
  }

  .card-site {
    margin-left: auto;
    font-size: 10px;
    color: var(--fg-2);
    text-transform: uppercase;
  }

  .card-kpis {
    display: flex;
    gap: var(--s2);
    background: var(--bg);
    padding: var(--s1) var(--s2);
    border-radius: 2px;
  }

  .card-kpi {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .kpi-val {
    font-family: var(--mono);
    font-weight: 600;
    font-size: var(--t0);
    color: var(--fg);
  }

  .kpi-label {
    font-size: 10px;
    color: var(--fg-2);
    text-transform: uppercase;
  }

  .card-caps {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }

  .cap-pill {
    font: 500 10px/1.2 var(--mono);
    background: var(--bg-1);
    color: var(--fg-1);
    padding: 1px 4px;
    border-radius: 2px;
    border: 1px solid var(--line);
  }

  .cap-pill.more {
    color: var(--fg-2);
  }

  .card-buttons {
    display: flex;
    gap: var(--s2);
    margin-top: auto;
    padding-top: var(--s1);
  }

  .action-btn {
    flex: 1;
    background: none;
    border: 1px solid var(--line-2);
    border-radius: 2px;
    color: var(--fg-1);
    font-size: var(--t-1);
    padding: 3px 6px;
    cursor: pointer;
    text-align: center;
  }

  .action-btn:hover {
    color: var(--fg);
    border-color: var(--line-3);
  }

  .action-btn.active {
    background: var(--pend);
    color: var(--bg);
    border-color: var(--pend);
    font-weight: 600;
  }

  .action-btn.tel.active {
    background: var(--warn);
    color: var(--bg);
    border-color: var(--warn);
  }

  .telemetry-tray {
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: var(--s3);
    margin-top: var(--s2);
  }

  .tray-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--s2);
    margin-bottom: var(--s2);
    border-bottom: 1px solid var(--line);
    font-size: var(--t0);
    color: var(--fg-1);
  }

  .btn-close {
    background: none;
    border: none;
    color: var(--fg-2);
    cursor: pointer;
    font-size: var(--t0);
  }

  .btn-close:hover {
    color: var(--fg);
  }

  .tray-loading {
    padding: var(--s4);
    text-align: center;
    color: var(--fg-2);
    font-size: var(--t0);
  }
</style>
