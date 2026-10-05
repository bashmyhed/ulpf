<script>
  import { onMount } from 'svelte'
  import { fmt } from './api.js'

  let nodes = $state([
    {
      id: 'agent-a',
      name: 'Agent A',
      site_id: 'kol-dc1',
      badge: 'Syslog / CEF / LEEF',
      files: ['vector.yaml', 'config/sources.yaml', 'config/transform.yaml', 'config/sinks.yaml', 'config/env.yaml', 'config/README.md']
    },
    {
      id: 'agent-b',
      name: 'Agent B',
      site_id: 'del-dc2',
      badge: 'JSON / CSV / CloudTrail',
      files: ['vector.yaml', 'config/sources.yaml', 'config/transform.yaml', 'config/sinks.yaml', 'config/env.yaml', 'config/README.md']
    },
    {
      id: 'agent-c',
      name: 'Agent C',
      site_id: 'mum-dc3',
      badge: 'Windows EVTX / XML',
      files: ['vector.yaml', 'config/sources.yaml', 'config/transform.yaml', 'config/sinks.yaml', 'config/env.yaml', 'config/README.md']
    },
    {
      id: 'server-parser',
      name: 'Server Parser',
      site_id: 'kol-dc1',
      badge: 'OCSF Normalizer & Router',
      files: [
        'vector.yaml',
        'config/sources.yaml',
        'config/transforms/01_stamp_and_verify.yaml',
        'config/transforms/02_route.yaml',
        'config/transforms/03_parse_cisco_asa.yaml',
        'config/transforms/04_parse_linux_auth.yaml',
        'config/transforms/05_parse_paloalto_cef.yaml',
        'config/transforms/06_parse_qradar_leef.yaml',
        'config/transforms/07_parse_nginx_access.yaml',
        'config/transforms/08_parse_cloudtrail.yaml',
        'config/transforms/09_parse_k8s_audit.yaml',
        'config/transforms/10_parse_iot_sensor.yaml',
        'config/transforms/11_parse_postgres_db.yaml',
        'config/transforms/12_parse_windows_evtx.yaml',
        'config/transforms/13_parse_unknown.yaml',
        'config/sinks.yaml',
        'config/env.yaml',
        'config/README.md'
      ]
    }
  ])

  let selectedNode = $state('agent-a')
  let selectedFile = $state('vector.yaml')
  let fileContent = $state('')
  let originalContent = $state('')
  let loadingFile = $state(false)
  let validating = $state(false)
  let saving = $state(false)
  let statusBanner = $state(null) // { type: 'ok'|'bad'|'warn'|'pend', msg: '', details: '' }
  let commitHistory = $state([])
  let showHistory = $state(false)
  let currentSHA = $state('')
  let fileFilter = $state('')

  // LLM Prompt Area (Prop)
  let llmPrompt = $state('')
  let llmLoading = $state(false)
  let llmResponse = $state(null)

  async function loadCollectorFiles(nodeId) {
    try {
      const res = await fetch(`/api/v1/agents/${nodeId}/files`, {
        headers: { 'Authorization': 'Bearer ulpf-secret-token-admin-2026' }
      })
      if (res.ok) {
        const data = await res.json()
        if (data.files && data.files.length > 0) {
          const idx = nodes.findIndex((n) => n.id === nodeId)
          if (idx !== -1) {
            nodes[idx].files = data.files
          }
        }
      }
    } catch {}
  }

  async function loadFile(nodeId, fileName) {
    selectedNode = nodeId
    selectedFile = fileName
    loadingFile = true
    statusBanner = null
    try {
      const res = await fetch(`/api/v1/agents/${nodeId}/file?path=${encodeURIComponent(fileName)}`, {
        headers: { 'Authorization': 'Bearer ulpf-secret-token-admin-2026' }
      })
      if (res.ok) {
        const data = await res.json()
        fileContent = data.content ?? ''
      } else {
        // Fallback to active config endpoint if root vector.yaml
        const fallbackRes = await fetch(`/api/v1/configs/${nodeId}`, {
          headers: { 'Authorization': 'Bearer ulpf-secret-token-admin-2026' }
        })
        if (fallbackRes.ok) {
          fileContent = await fallbackRes.text()
        } else {
          fileContent = `# File: ${fileName} for ${nodeId}\n# Error reading from disk.\n`
        }
      }
      originalContent = fileContent
    } catch {
      fileContent = `# Configuration for ${nodeId} (${fileName})\n# Error connecting to config server.\n`
      originalContent = fileContent
    } finally {
      loadingFile = false
    }
  }

  async function validateConfig() {
    validating = true
    statusBanner = null
    try {
      const res = await fetch(`/api/v1/agents/${selectedNode}/validate`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ulpf-secret-token-admin-2026',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent
        })
      })
      const data = await res.json()
      if (res.ok && data.valid) {
        statusBanner = {
          type: 'ok',
          msg: `Validation Passed! (${data.duration_ms}ms)`,
          details: 'Syntax, VRL logic, and topology verified with Vector engine.'
        }
      } else {
        statusBanner = {
          type: 'bad',
          msg: 'Vector Validate Rejected Configuration',
          details: data.error || data.output || 'Topology or syntax error'
        }
      }
    } catch (err) {
      statusBanner = {
        type: 'bad',
        msg: 'Validator Connection Error',
        details: String(err)
      }
    } finally {
      validating = false
    }
  }

  async function saveAndDeploy() {
    saving = true
    statusBanner = null
    try {
      const res = await fetch(`/api/v1/agents/${selectedNode}/file`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ulpf-secret-token-admin-2026',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent,
          message: `Update ${selectedFile} via ULPF Dashboard`
        })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        currentSHA = data.commit_sha || ''
        originalContent = fileContent
        statusBanner = {
          type: 'ok',
          msg: `Saved & Deployed! Commit: ${currentSHA.slice(0, 8)}`,
          details: `Updated ${selectedFile} on disk and committed to Git repository.`
        }
      } else {
        statusBanner = {
          type: 'bad',
          msg: data.message || 'Save Failed',
          details: data.error || 'Existing running configuration preserved with zero disruption.'
        }
      }
    } catch (err) {
      statusBanner = {
        type: 'bad',
        msg: 'Save Request Failed',
        details: String(err)
      }
    } finally {
      saving = false
    }
  }

  async function loadHistory() {
    showHistory = !showHistory
    if (!showHistory) return
    try {
      const res = await fetch(`/api/v1/configs/${selectedNode}/history`, {
        headers: { 'Authorization': 'Bearer ulpf-secret-token-admin-2026' }
      })
      if (res.ok) {
        const data = await res.json()
        commitHistory = data.history || []
      }
    } catch {}
  }

  async function rollbackTo(sha) {
    if (!confirm(`Rollback ${selectedNode} to commit ${sha.slice(0, 8)}?`)) return
    try {
      const res = await fetch(`/api/v1/configs/${selectedNode}/rollback`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ulpf-secret-token-admin-2026',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ commit_sha: sha, message: `Rollback to ${sha.slice(0, 8)}` })
      })
      const data = await res.json()
      if (res.ok) {
        statusBanner = {
          type: 'ok',
          msg: `Rolled back to ${sha.slice(0, 8)}`,
          details: 'Restored verified historical configuration and re-deployed.'
        }
        showHistory = false
        loadFile(selectedNode, selectedFile)
      } else {
        statusBanner = { type: 'bad', msg: 'Rollback Failed', details: data.message }
      }
    } catch (err) {
      statusBanner = { type: 'bad', msg: 'Rollback Error', details: String(err) }
    }
  }

  function handleLLMPrompt() {
    if (!llmPrompt.trim()) return
    llmLoading = true
    llmResponse = null
    setTimeout(() => {
      llmLoading = false
      llmResponse = {
        suggestion: `# Suggested VRL remap rule for ${selectedNode}:\n.parsed, err = parse_regex(.message, r'^(?P<timestamp>\\S+) (?P<host>\\S+) (?P<msg>.*)$')\nif err == null {\n  .time = parse_timestamp!(.parsed.timestamp, "%Y-%m-%dT%H:%M:%SZ")\n  .device.hostname = .parsed.host\n}`,
        notes: `Analyzed prompt "${llmPrompt}". Generated compliant OCSF v1.3 remap rule.`
      }
    }, 600)
  }

  function insertLLMSuggestion() {
    if (!llmResponse?.suggestion) return
    fileContent = fileContent + '\n\n' + llmResponse.suggestion
    llmResponse = null
    llmPrompt = ''
  }

  function selectNode(id) {
    selectedNode = id
    loadCollectorFiles(id)
    const n = nodes.find((x) => x.id === id)
    if (n && n.files.length > 0) {
      loadFile(id, n.files[0])
    }
  }

  onMount(async () => {
    // Refresh files for all nodes
    for (const n of nodes) {
      loadCollectorFiles(n.id)
    }
    loadFile(selectedNode, selectedFile)
  })

  const isModified = $derived(fileContent !== originalContent)
  const currentNode = $derived(nodes.find((n) => n.id === selectedNode))
  const filteredFiles = $derived.by(() => {
    if (!currentNode) return []
    if (!fileFilter.trim()) return currentNode.files
    const q = fileFilter.trim().toLowerCase()
    return currentNode.files.filter((f) => f.toLowerCase().includes(q))
  })
</script>

<div class="screen-layout">
  <!-- Split: Left File Tree, Right Editor -->
  <div class="split config-split">
    <!-- Left Navigation Tree -->
    <div class="panel tree-panel">
      <div class="head quiet pad">
        <h2>Agent Fleet Configs</h2>
        <span class="note push">Vector Engine</span>
      </div>

      <!-- Node Selector Pills -->
      <div class="node-tabs pad">
        {#each nodes as node}
          <button
            class="node-tab-btn"
            class:active={selectedNode === node.id}
            onclick={() => selectNode(node.id)}
          >
            <span class="node-tab-name">{node.name}</span>
            <span class="site-id-grey">{node.site_id}</span>
            <span class="node-tab-badge">{node.badge.split('/')[0]}</span>
          </button>
        {/each}
      </div>

      <div class="file-search-bar pad">
        <input
          type="search"
          placeholder="Filter config files..."
          bind:value={fileFilter}
        />
      </div>

      <div class="tree-container">
        {#if currentNode}
          <div class="file-category">
            <span class="cat-label">Config Files ({filteredFiles.length})</span>
          </div>
          <div class="node-files">
            {#each filteredFiles as file}
              <button
                class="file-item mono xs"
                class:active={selectedFile === file}
                onclick={() => loadFile(selectedNode, file)}
              >
                <span class="doc-icon" class:yaml={file.endsWith('.yaml') || file.endsWith('.yml')}>
                  {file === 'vector.yaml' ? '★' : file.includes('transform') ? '⚡' : file.includes('sources') ? '📥' : file.includes('sinks') ? '📤' : '≡'}
                </span>
                <span class="file-name">{file}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Right Editor & Operations Panel -->
    <div class="panel editor-panel">
      <!-- Editor Top Bar -->
      <div class="editor-bar pad">
        <div class="file-breadcrumb">
          <span class="tag ok">{selectedNode}</span>
          {#if currentNode}
            <span class="site-id-grey breadcrumb-site">({currentNode.site_id})</span>
          {/if}
          <b class="mono">{selectedFile}</b>
          {#if isModified}
            <span class="tag warn xs">unsaved changes</span>
          {/if}
          {#if currentSHA}
            <span class="mono xs dim">SHA: {currentSHA.slice(0, 8)}</span>
          {/if}
        </div>

        <div class="bar-actions push">
          <button class="btn" onclick={loadHistory}>
            History ({commitHistory.length || 'Git'})
          </button>
          <button class="btn" disabled={validating} onclick={validateConfig}>
            {validating ? 'Validating...' : 'Validate Config'}
          </button>
          <button class="btn primary" disabled={saving} onclick={saveAndDeploy}>
            {saving ? 'Saving...' : 'Save & Deploy'}
          </button>
        </div>
      </div>

      <!-- Validation & Deploy Notification Banner -->
      {#if statusBanner}
        <div class="notice {statusBanner.type} bar">
          <span class="tag {statusBanner.type}">{statusBanner.type.toUpperCase()}</span>
          <div>
            <b>{statusBanner.msg}</b>
            {#if statusBanner.details}
              <div class="banner-details mono xs">{statusBanner.details}</div>
            {/if}
          </div>
          <button class="btn sm push" onclick={() => (statusBanner = null)}>✕</button>
        </div>
      {/if}

      <!-- Git History Modal / Drawer -->
      {#if showHistory}
        <div class="history-drawer pad">
          <div class="head quiet">
            <h3>Git Commit Version History for {selectedNode}</h3>
            <button class="btn sm push" onclick={() => (showHistory = false)}>Close</button>
          </div>
          {#if commitHistory.length === 0}
            <div class="empty">No historical commits recorded yet for this node.</div>
          {:else}
            <div class="history-list">
              {#each commitHistory as commit}
                <div class="history-item">
                  <span class="mono xs">{commit.commit_sha ? commit.commit_sha.slice(0, 8) : ''}</span>
                  <span class="dim xs">{commit.timestamp ? fmt.stamp(commit.timestamp) : ''}</span>
                  <span class="hist-msg">{commit.message}</span>
                  <button class="btn sm" onclick={() => rollbackTo(commit.commit_sha)}>Rollback</button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      <!-- Main YAML Text Editor -->
      <div class="editor-container">
        {#if loadingFile}
          <div class="editor-loading">
            <span class="spinner"></span> Loading {selectedFile}...
          </div>
        {:else}
          <textarea
            class="editor"
            spellcheck="false"
            bind:value={fileContent}
            placeholder="Configuration content..."
          ></textarea>
        {/if}
      </div>

      <!-- LLM Copilot Prompt Bar (Prop) -->
      <div class="llm-bar pad">
        <div class="llm-header">
          <span class="tag pend">AI CONFIG COPILOT</span>
          <span class="xs dim">Chat with LLM to generate or update Vector log format parsers</span>
        </div>

        <div class="llm-input-row">
          <input
            type="text"
            class="llm-input"
            placeholder="e.g. Add regex parser for Fortinet VPN logs to OCSF Network Activity..."
            bind:value={llmPrompt}
            onkeydown={(e) => e.key === 'Enter' && handleLLMPrompt()}
          />
          <button class="btn" disabled={llmLoading || !llmPrompt.trim()} onclick={handleLLMPrompt}>
            {llmLoading ? 'Generating...' : 'Ask Copilot'}
          </button>
        </div>

        {#if llmResponse}
          <div class="llm-response-box">
            <div class="llm-notes xs">{llmResponse.notes}</div>
            <pre class="llm-code mono xs">{llmResponse.suggestion}</pre>
            <div class="llm-actions">
              <button class="btn primary sm" onclick={insertLLMSuggestion}>Insert into Editor</button>
              <button class="btn sm" onclick={() => (llmResponse = null)}>Dismiss</button>
            </div>
          </div>
        {/if}
      </div>
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

  .config-split {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: var(--s4);
    align-items: stretch;
    min-height: 75vh;
  }

  .tree-panel {
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    overflow: hidden;
  }

  .node-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s2);
    border-bottom: 1px solid var(--line);
    background: var(--bg);
  }

  .node-tab-btn {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: var(--s2);
    border: 1px solid var(--line);
    background: var(--bg-1);
    border-radius: 3px;
    cursor: pointer;
    text-align: left;
    transition: all var(--d1);
  }

  .node-tab-btn:hover {
    background: var(--bg-2);
    border-color: var(--line-2);
  }

  .node-tab-btn.active {
    background: var(--sel);
    border-color: var(--pend);
  }

  .node-tab-name {
    font-weight: 600;
    font-size: var(--t0);
    color: var(--fg);
  }

  .site-id-grey {
    color: var(--fg-2);
    font-size: 10px;
    font-family: var(--mono);
    font-weight: 400;
  }

  .breadcrumb-site {
    margin: 0 var(--s1);
  }

  .node-tab-badge {
    font-size: 10px;
    color: var(--fg-2);
  }

  .file-search-bar {
    border-bottom: 1px solid var(--line);
    background: var(--bg-1);
  }

  .file-search-bar input {
    width: 100%;
    padding: 4px var(--s2);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: 2px;
    font-size: var(--t-1);
    color: var(--fg);
  }

  .tree-container {
    flex: 1;
    overflow-y: auto;
    padding: var(--s2) 0;
  }

  .file-category {
    padding: var(--s1) var(--s3);
  }

  .cat-label {
    font: 600 var(--t-1)/1 var(--sans);
    color: var(--fg-2);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .node-files {
    display: flex;
    flex-direction: column;
  }

  .file-item {
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding: 6px var(--s3);
    background: none;
    border: none;
    color: var(--fg-1);
    cursor: pointer;
    text-align: left;
    width: 100%;
    border-left: 2px solid transparent;
  }

  .file-item:hover {
    background: var(--bg-2);
    color: var(--fg);
  }

  .file-item.active {
    background: var(--sel);
    color: var(--fg);
    border-left-color: var(--ok);
  }

  .doc-icon {
    color: var(--fg-2);
    font-size: 11px;
    width: 14px;
    text-align: center;
  }

  .doc-icon.yaml {
    color: #5ec6d0;
  }

  .file-name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 11px;
  }

  .editor-panel {
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 4px;
    overflow: hidden;
  }

  .editor-bar {
    display: flex;
    align-items: center;
    background: var(--bg-2);
    border-bottom: 1px solid var(--line);
    gap: var(--s3);
  }

  .file-breadcrumb {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .bar-actions {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .banner-details {
    margin-top: 4px;
    font-size: 11px;
    line-height: 1.4;
    max-height: 100px;
    overflow-y: auto;
  }

  .history-drawer {
    background: var(--bg);
    border-bottom: 1px solid var(--line);
    max-height: 200px;
    overflow-y: auto;
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: var(--s1);
    margin-top: var(--s2);
  }

  .history-item {
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: 4px var(--s2);
    background: var(--bg-1);
    border-radius: 2px;
  }

  .hist-msg {
    flex: 1;
    font-size: var(--t-1);
    color: var(--fg-1);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .editor-container {
    flex: 1;
    display: flex;
    min-height: 440px;
    background: var(--bg);
    position: relative;
  }

  .editor-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    color: var(--fg-2);
    gap: var(--s2);
  }

  .editor {
    width: 100%;
    height: 100%;
    min-height: 440px;
    background: var(--bg);
    color: var(--fg);
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.6;
    padding: var(--s3);
    border: none;
    resize: none;
    outline: none;
    tab-size: 2;
  }

  .llm-bar {
    background: var(--bg-2);
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .llm-header {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .llm-input-row {
    display: flex;
    gap: var(--s2);
  }

  .llm-input {
    flex: 1;
    background: var(--bg-1);
    border: 1px solid var(--line-2);
    border-radius: 2px;
    padding: var(--s2);
    font-size: var(--t0);
    color: var(--fg);
  }

  .llm-response-box {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  .llm-code {
    background: var(--bg);
    padding: var(--s2);
    border-radius: 2px;
    border: 1px solid var(--line);
    color: var(--ok);
  }

  .llm-actions {
    display: flex;
    gap: var(--s2);
  }
</style>
