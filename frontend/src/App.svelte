<script>
  import { onMount } from 'svelte'
  import Live from './Live.svelte'
  import Review from './Review.svelte'
  import Traceback from './Traceback.svelte'
  import Pivot from './Pivot.svelte'
  import Replay from './Replay.svelte'
  import Drift from './Drift.svelte'
  import Integrity from './Integrity.svelte'
  import Flow from './Flow.svelte'
  import Status from './Status.svelte'
  import Logs from './Logs.svelte'
  import Config from './Config.svelte'
  import AlertDrawer from './AlertDrawer.svelte'
  import { live, loadStatus } from './state.svelte.js'
  import { screenKey, typing, theme } from './keys.js'
  import { fmt } from './api.js'

  // Flow is the front door (#/ and #/flow, key 0, Esc from any top-level screen); the
  // seven windows are one step behind it.
  const SCREENS = [
    { key: '0', view: 'flow', label: 'Flow' },
    { key: '1', view: 'live', label: 'Live' },
    { key: '2', view: 'review', label: 'Review' },
    { key: '3', view: 'trace', label: 'Traceback' },
    { key: '4', view: 'pivot', label: 'Pivot' },
    { key: '5', view: 'replay', label: 'Replay' },
    { key: '6', view: 'drift', label: 'Drift' },
    { key: '7', view: 'integrity', label: 'Integrity' },
    { key: '8', view: 'status', label: 'Status' },
    { key: '9', view: 'logs', label: 'Logs' },
    { key: 'c', view: 'config', label: 'Config' },
  ]

  // #/live · #/review/<id> · #/trace/<raw_id> · #/pivot/<kind>/<value> · #/replay · #/drift · #/integrity
  function parse(h) {
    const parts = h.replace(/^#\/?/, '').split('/').map(decodeURIComponent)
    const raw = parts[0]
    const view = (!raw || raw === 'home' || raw === 'flow') ? 'home' : (SCREENS.some((s) => s.view === raw) ? raw : 'home')
    return { view, a: parts[1] ?? '', b: parts.slice(2).join('/') }
  }
  let route = $state(parse(location.hash))
  let helpOpen = $state(false)
  let alertDrawerOpen = $state(true)
  let mode = $state(theme())
  window.addEventListener('hashchange', () => {
    route = parse(location.hash)
    helpOpen = false
    window.scrollTo(0, 0)
    // The screen transition runs only for a navigation, never for the first paint.
    document.documentElement.dataset.nav = ''
  })
  loadStatus()
  // A count badge pops when it changes, not when it first appears with the hello frame.
  setTimeout(() => (document.documentElement.dataset.live = ''), 1500)

  function onKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return
    if (e.key === 'Escape') {
      if (helpOpen) { helpOpen = false; e.preventDefault(); return }
      if (typing(e)) { e.target.blur(); return }
    }
    if (typing(e)) return
    if (e.key === 'a') { alertDrawerOpen = !alertDrawerOpen; return }
    const s = SCREENS.find((x) => x.key === e.key)
    if (s) { location.hash = `#/${s.view}`; e.preventDefault(); return }
    if (screenKey(e)) { e.preventDefault(); return }
    // An Esc no screen used goes back to the front door.
    if (e.key === 'Escape' && route.view !== 'home') location.hash = '#/'
  }

  const drifting = $derived((live.drift ?? []).filter((d) => d.state === 'tripped' || d.state === 'proposed').length)
  const st = $derived(live.status)
  const server = $derived(live.metrics?.server)

  let agentCount = $state(3)
  let unmatchedHashCount = $state(0)
  let alertsCount = $state(0)

  async function pollFooterStats() {
    try {
      const [pipeRes, alertsRes, agentsRes] = await Promise.allSettled([
        fetch('/api/ulpf/pipeline/stats', { headers: { 'Authorization': 'Bearer admin-token' } }),
        fetch('/api/ulpf/alerts', { headers: { 'Authorization': 'Bearer admin-token' } }),
        fetch('/api/ulpf/agents', { headers: { 'Authorization': 'Bearer admin-token' } })
      ])
      if (pipeRes.status === 'fulfilled' && pipeRes.value.ok) {
        const d = await pipeRes.value.json()
        if (d.integrity) unmatchedHashCount = d.integrity.unmatched_hashes ?? 0
      }
      if (alertsRes.status === 'fulfilled' && alertsRes.value.ok) {
        const d = await alertsRes.value.json()
        alertsCount = d.stats?.total ?? d.alerts?.length ?? 0
      }
      if (agentsRes.status === 'fulfilled' && agentsRes.value.ok) {
        const d = await agentsRes.value.json()
        const list = (d.agents || d.collectors || []).filter((a) => a.agent_type !== 'server')
        agentCount = list.length || 3
      }
    } catch {}
  }

  onMount(() => {
    pollFooterStats()
    const timer = setInterval(pollFooterStats, 4000)
    return () => clearInterval(timer)
  })
</script>

<svelte:window onkeydown={onKey} />

<header class="top">
  <a href="#/" class="brand" title="ULPF Home">ULPF</a>
  <nav aria-label="Screens">
    <a href="#/status" class:on={route.view === 'status'} aria-current={route.view === 'status' ? 'page' : undefined}>
      Status
    </a>
    <a href="#/logs" class:on={route.view === 'logs'} aria-current={route.view === 'logs' ? 'page' : undefined}>
      Logs
    </a>
    <a href="#/config" class:on={route.view === 'config'} aria-current={route.view === 'config' ? 'page' : undefined}>
      Config
    </a>
  </nav>
  <span class="right">
    <button onclick={() => (alertDrawerOpen = !alertDrawerOpen)} title="Toggle Alerts Panel" class:on={alertDrawerOpen}>
      Alerts
    </button>
  </span>
</header>

<div class="app-body">
  <main class="main-viewport">
    {#key route.view}
      <div class="screen">
        {#if route.view === 'home' || route.view === 'flow'}
          <Flow />
        {:else if route.view === 'live'}
          <Live />
        {:else if route.view === 'review'}
          <Review id={route.a} />
        {:else if route.view === 'trace'}
          <Traceback id={route.a} />
        {:else if route.view === 'pivot'}
          <Pivot kind={route.a} value={route.b} />
        {:else if route.view === 'replay'}
          <Replay />
        {:else if route.view === 'drift'}
          <Drift />
        {:else if route.view === 'integrity'}
          <Integrity />
        {:else if route.view === 'status'}
          <Status />
        {:else if route.view === 'logs'}
          <Logs />
        {:else if route.view === 'config'}
          <Config />
        {:else}
          <Flow />
        {/if}
      </div>
    {/key}
  </main>
  <AlertDrawer bind:open={alertDrawerOpen} />
</div>

<footer class="foot">
  <span class={live.conn}><i class="dot"></i>{live.conn === 'live' ? 'stream' : live.conn === 'connecting' ? 'connecting' : `retry ${live.retryIn}s`}</span>
  <span>listen <b>{st?.listen ?? '–'}</b></span>
  <span>schema <b>{st?.schema ? `${st.schema.name} ${st.schema.version}` : (st ? 'ocsf' : '–')}</b></span>
  {#if st?.syslog?.udp || st?.syslog?.tcp}
    <span>syslog <b>{[st.syslog.udp && `udp ${st.syslog.udp}`, st.syslog.tcp && `tcp ${st.syslog.tcp}`].filter(Boolean).join('  ')}</b></span>
  {/if}
  <span>up <b>{fmt.ago(server?.uptime_secs)}</b></span>
  <span>agents <b>{agentCount}</b></span>
  <span class:is-warn={unmatchedHashCount > 0}>unmatched hashes <b>{unmatchedHashCount}</b></span>
  <span class:is-warn={alertsCount > 0}>alerts <b>{alertsCount}</b></span>
  {#if live.metrics?.queue}<span title="batches in flight between the ingest threads and the output thread, against the queue's capacity">queue <b>{fmt.n(live.metrics.queue.depth)}/{fmt.n(live.metrics.queue.capacity)}</b></span>{/if}
  <span class="push" class:is-warn={live.dropped > 0} title="a frame that arrived before the previous one painted replaced it; nothing queues">frames skipped <b>{fmt.n(live.dropped)}</b></span>
  <span class:is-warn={live.evicted > 0} title="events the server's tail ring dropped before this screen read them: they are gone from the ring (the store still has every one)">events skipped <b>{fmt.n(live.evicted)}</b></span>
  {#if live.cut > 0}
    <span class="cutnote" title="a burst larger than one frame: a frame carries the newest {fmt.n(st?.tail_per_tick ?? 200)} events, so these older ones were not sent to this screen; the ring still holds the newest {fmt.n(st?.tail_capacity ?? 1000)}">{fmt.n(live.cut)} older rows not shown</span>
  {/if}
</footer>

{#if helpOpen}
  <div class="overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) helpOpen = false }}>
    <div class="keymap" role="dialog" aria-label="Keyboard map" tabindex="-1" {@attach (el) => el.focus()}>
      <h2>Keys <span class="note">Esc closes it; any letter or digit closes it and still does its job</span><button class="btn" onclick={() => (helpOpen = false)}>close<kbd>Esc</kbd></button></h2>
      <section>
        <h3>Anywhere</h3>
        <dl>
          <dt>0</dt><dd>Flow, the front door: every station of the machine, live</dd>
          <dt>1 … 7</dt><dd>Live, Review, Traceback, Pivot, Replay, Drift, Integrity, one step behind it</dd>
          <dt>?</dt><dd>this map</dd>
          <dt>t</dt><dd>light or dark</dd>
          <dt>/</dt><dd>the search or lookup box on this screen</dd>
          <dt>Esc</dt><dd>close, leave a detail for its list, or go back to Flow from any screen</dd>
        </dl>
        <h3>Flow</h3>
        <dl>
          <dt>i s d p n e</dt><dd>ingest, preserve, detect, parse, normalize, emit: opens the screen behind the station</dd>
          <dt>r</dt><dd>the tray: proposals waiting for review</dd>
          <dt>h / l</dt><dd>move along the line (arrows work too), Enter opens</dd>
        </dl>
        <h3>Any list</h3>
        <dl>
          <dt>j / k</dt><dd>move down, up (arrows work too)</dd>
          <dt>g / G</dt><dd>first row, last row</dd>
          <dt>Enter</dt><dd>open the selected row</dd>
        </dl>
        <h3>Live</h3>
        <dl>
          <dt>space</dt><dd>hold the tail still, and release it</dd>
          <dt>Enter</dt><dd>trace the selected event's bytes</dd>
          <dt>f</dt><dd>only the rows carrying a flag, and every row again</dd>
          <dt>e</dt><dd>the export choice: Enter takes the file, Esc closes it</dd>
        </dl>
        <h3>Traceback</h3>
        <dl>
          <dt>j / k</dt><dd>walk the normalized fields, lighting each field's bytes</dd>
          <dt>Enter</dt><dd>keep the selected field lit while you read the other side</dd>
          <dt>h</dt><dd>hex or text</dd>
          <dt>Esc</dt><dd>release the lit field</dd>
        </dl>
      </section>
      <section>
        <h3>Review</h3>
        <dl>
          <dt>s</dt><dd>save the definition</dd>
          <dt>a</dt><dd>approve: opens the confirmation, Enter confirms, Esc cancels</dd>
          <dt>x</dt><dd>reject: the same confirmation</dd>
          <dt>d</dt><dd>diff against the parser this replaces</dd>
          <dt>m</dt><dd>merge the picked templates</dd>
          <dt>r</dt><dd>regenerate from the kept templates</dd>
        </dl>
        <h3>Pivot</h3>
        <dl>
          <dt>Backspace</dt><dd>back one step along the trail</dd>
          <dt>m</dt><dd>load older events</dd>
          <dt>Enter</dt><dd>trace the selected event</dd>
        </dl>
        <h3>Replay, Drift, Integrity</h3>
        <dl>
          <dt>j / k</dt><dd>walk the diff entries, or the drift alerts</dd>
          <dt>Enter</dt><dd>trace the entry, or open the drift proposal</dd>
          <dt>v</dt><dd>start a verify (Integrity) or a replay (Replay), with confirmation</dd>
          <dt>m</dt><dd>load more diff entries (Replay)</dd>
        </dl>
      </section>
    </div>
  </div>
{/if}

<style>
  .app-body {
    display: flex;
    align-items: stretch;
    width: 100%;
    min-height: calc(100vh - var(--top) - var(--foot));
  }

  .main-viewport {
    flex: 1;
    min-width: 0;
    max-width: 100%;
    margin: 0;
    padding: var(--s5) var(--gutter) calc(var(--foot) + var(--s5));
  }

  .top .brand {
    color: var(--fg);
    text-decoration: none;
    cursor: pointer;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  .top .brand:hover {
    color: #fff;
  }

  .top .right button.on {
    color: var(--warn);
    border-bottom: 2px solid var(--warn);
  }
</style>
