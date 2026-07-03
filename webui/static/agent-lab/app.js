const state = { csrf: null, projects: [], profiles: {}, targets: {}, selected: null, lastTargets: [], lastDeployment: null };
const q = (id) => document.getElementById(id);

async function request(path, options = {}) {
  const r = await fetch(path, { credentials: 'same-origin', ...options });
  const t = await r.text();
  let b = {};
  try {
    b = t ? JSON.parse(t) : {};
  } catch {
    b = { error: t };
  }
  if (!r.ok) throw new Error(b.error || t || r.statusText);
  return b;
}

async function token() {
  if (!state.csrf) state.csrf = (await request('/api/csrf-token')).csrf_token;
  return state.csrf;
}

function note(msg, ok = true) {
  const el = q('status');
  el.textContent = msg;
  el.className = 'status ' + (ok ? 'ok' : 'bad');
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
    reader.onerror = () => reject(reader.error || new Error('file read failed'));
    reader.readAsDataURL(file);
  });
}

function bytesToBase64(bytes) {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let c = 0xffffffff;
  for (const byte of bytes) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function writeHeader(view, values) {
  let offset = 0;
  for (const [kind, value] of values) {
    if (kind === 16) {
      view.setUint16(offset, value, true);
      offset += 2;
    } else {
      view.setUint32(offset, value, true);
      offset += 4;
    }
  }
}

function cleanZipPath(path) {
  const clean = String(path || '').replace(/\\/g, '/').replace(/^\/+/, '');
  const parts = clean.split('/');
  if (!clean || clean.endsWith('/') || parts.some((part) => !part || part === '.' || part === '..')) {
    throw new Error('Folder contains an unsafe file path: ' + path);
  }
  return clean;
}

function folderProjectId(files) {
  const first = files.find((file) => file.webkitRelativePath || file.name);
  const rel = first ? String(first.webkitRelativePath || first.name) : '';
  const top = rel.split(/[\\/]/).filter(Boolean)[0] || '';
  return top.replace(/[^a-zA-Z0-9_.-]+/g, '-').replace(/^[._-]+|[._-]+$/g, '').slice(0, 80);
}

async function makeStoredZip(files) {
  const encoder = new TextEncoder();
  const chunks = [];
  const central = [];
  let offset = 0;
  const sorted = [...files].sort((a, b) => String(a.webkitRelativePath || a.name).localeCompare(String(b.webkitRelativePath || b.name)));

  for (const file of sorted) {
    const name = cleanZipPath(file.webkitRelativePath || file.name);
    const nameBytes = encoder.encode(name);
    const data = new Uint8Array(await file.arrayBuffer());
    const crc = crc32(data);
    const localHeader = new Uint8Array(30 + nameBytes.length);
    writeHeader(new DataView(localHeader.buffer), [
      [32, 0x04034b50],
      [16, 20],
      [16, 0],
      [16, 0],
      [16, 0],
      [16, 0],
      [32, crc],
      [32, data.length],
      [32, data.length],
      [16, nameBytes.length],
      [16, 0],
    ]);
    localHeader.set(nameBytes, 30);
    chunks.push(localHeader, data);
    central.push({ nameBytes, crc, size: data.length, offset });
    offset += localHeader.length + data.length;
  }

  const centralOffset = offset;
  const centralChunks = [];
  for (const entry of central) {
    const header = new Uint8Array(46 + entry.nameBytes.length);
    writeHeader(new DataView(header.buffer), [
      [32, 0x02014b50],
      [16, 20],
      [16, 20],
      [16, 0],
      [16, 0],
      [16, 0],
      [16, 0],
      [32, entry.crc],
      [32, entry.size],
      [32, entry.size],
      [16, entry.nameBytes.length],
      [16, 0],
      [16, 0],
      [16, 0],
      [16, 0],
      [32, 0],
      [32, entry.offset],
    ]);
    header.set(entry.nameBytes, 46);
    centralChunks.push(header);
    offset += header.length;
  }
  const centralSize = offset - centralOffset;
  const eocd = new Uint8Array(22);
  writeHeader(new DataView(eocd.buffer), [
    [32, 0x06054b50],
    [16, 0],
    [16, 0],
    [16, central.length],
    [16, central.length],
    [32, centralSize],
    [32, centralOffset],
    [16, 0],
  ]);
  const zipSize = offset + eocd.length;
  const out = new Uint8Array(zipSize);
  let cursor = 0;
  for (const chunk of [...chunks, ...centralChunks, eocd]) {
    out.set(chunk, cursor);
    cursor += chunk.length;
  }
  return bytesToBase64(out);
}

async function load() {
  try {
    const data = await request('/api/agent-lab');
    state.projects = data.projects || [];
    state.profiles = data.profiles || {};
    state.targets = data.targets || {};
    renderProviders(data.provider_presets || {});
    renderProfiles();
    renderProjects();
    renderTargets();
    note('Agent Lab ready. Import or select a real project.');
  } catch (e) {
    note(e.message, false);
  }
}

function renderProviders(presets) {
  const s = q('provider');
  s.innerHTML = Object.entries(presets)
    .map(([k, v]) => `<option value="${k}" data-url="${v.default_base_url || ''}" data-model="${v.default_model || ''}">${v.display_name || k}</option>`)
    .join('');
  providerChanged();
}

function providerChanged() {
  const o = q('provider').selectedOptions[0];
  if (o) {
    q('provider-base-url').value = o.dataset.url || '';
    q('provider-model').value = o.dataset.model || '';
  }
}

function renderProfiles() {
  q('scan-profile').innerHTML = Object.keys(state.profiles)
    .map((k) => `<option value="${k}">${k}</option>`)
    .join('');
  if (state.profiles.baseline) q('scan-profile').value = 'baseline';
}

function renderProjects() {
  const f = (q('project-filter').value || '').toLowerCase();
  q('project-list').innerHTML =
    state.projects
      .filter((p) => !f || p.id.toLowerCase().includes(f))
      .map((p) => {
        const managed = p.source !== 'mounted';
        const del = managed
          ? `<button class="project-delete" data-del="${p.id}" title="Delete this managed project" aria-label="Delete ${p.id}">Delete</button>`
          : '<span class="muted project-readonly" title="Mapped projects are read-only; remove the folder from ./projects/ to delete">mapped</span>';
        return `<div class="project-row"><button class="project" data-id="${p.id}"><strong>${p.id}</strong><br><span class="muted">${p.framework || 'unknown'} | ${(p.ports || []).join(',') || 'no ports'} | ${p.source}</span></button>${del}</div>`;
      })
      .join('') || '<p class="muted">No projects found. Upload a local folder, upload a ZIP, import from Git, or put an AI agent in ./projects/&lt;agent-name&gt;/ and refresh.</p>';
  document.querySelectorAll('[data-id]').forEach((b) => (b.onclick = () => selectProject(b.dataset.id)));
  document.querySelectorAll('[data-del]').forEach((b) => (b.onclick = () => deleteProject(b.dataset.del)));
}

async function deleteProject(id) {
  if (!window.confirm(`Delete managed project '${id}'? This permanently removes its imported files from Agent Lab storage.`)) return;
  try {
    const data = await request('/api/agent-lab/projects/' + encodeURIComponent(id) + '/delete', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: '{}' });
    if (data.deleted) {
      note('Deleted project ' + id);
      if (state.selected && state.selected.project_id === id) {
        state.selected = null;
        q('analysis').innerHTML = '<p class="empty-state">Select a project to read its framework, ports, and the HTTP contract VulnoraIQ will scan.</p>';
        q('contract-preview').classList.add('hidden');
        q('deploy').disabled = true;
      }
      await load();
    } else {
      note('Project ' + id + ' could not be deleted (not a managed project).', false);
    }
  } catch (e) {
    note(e.message, false);
  }
}

async function selectProject(id) {
  try {
    state.selected = await request('/api/agent-lab/projects/' + encodeURIComponent(id) + '/analyze');
    renderAnalysis(state.selected);
    q('deploy').disabled = false;
    q('port').value = (state.selected.ports || [8000])[0] || 8000;
    // Pre-fill from the analyzer's ranked inference endpoint (e.g. AIRA's
    // GET /get), not endpoints[0] which is often a non-inference route like the
    // index "/". These form values are sent as target overrides on deploy, so
    // seeding them from the unranked first endpoint would override the correct
    // auto-detected contract with the wrong path.
    const ep = state.selected.selected_endpoint || (state.selected.endpoints || [])[0];
    q('endpoint-path').value = ep ? ep.path : '/';
    q('http-method').value = ep ? ep.method : 'POST';
    renderContractPreview();
  } catch (e) {
    note(e.message, false);
  }
}

async function importGit(ev) {
  ev.preventDefault();
  try {
    const body = { url: q('git-url').value, project_id: q('git-project-id').value, branch: q('git-branch').value };
    const data = await request('/api/agent-lab/import/git', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(body) });
    note('Imported ' + data.project_id);
    await load();
    await selectProject(data.project_id);
  } catch (e) {
    note(e.message, false);
  }
}

async function importZip(ev) {
  ev.preventDefault();
  try {
    const file = q('zip-file').files[0];
    if (!file) throw new Error('Choose a ZIP archive');
    const body = { project_id: q('zip-project-id').value, archive_base64: await toBase64(file) };
    const data = await request('/api/agent-lab/import/archive', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(body) });
    note('Uploaded ' + data.project_id);
    await load();
    await selectProject(data.project_id);
  } catch (e) {
    note(e.message, false);
  }
}

async function importFolder(ev) {
  ev.preventDefault();
  try {
    const files = [...q('folder-files').files];
    if (!files.length) throw new Error('Choose a local agent folder');
    const projectId = (q('folder-project-id').value || folderProjectId(files)).trim();
    if (!projectId) throw new Error('Project ID could not be derived from the selected folder');
    note(`Preparing ${files.length} files from selected folder...`);
    const body = { project_id: projectId, archive_base64: await makeStoredZip(files) };
    const data = await request('/api/agent-lab/import/archive', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(body) });
    note('Uploaded folder ' + data.project_id + ' into managed Agent Lab');
    await load();
    await selectProject(data.project_id);
  } catch (e) {
    note(e.message, false);
  }
}

function deploymentModeChanged() {
  const mode = q('deployment-mode').value;
  q('external-base-url-field').classList.toggle('hidden', mode !== 'external');
  q('authorization-ack-field').classList.toggle('hidden', mode === 'container');
}

async function deploy() {
  if (!state.selected) return;
  try {
    const mode = q('deployment-mode').value;
    if (mode !== 'container' && !q('authorization-ack').checked) {
      throw new Error('Confirm you are authorized to test this endpoint before deploying an external/hybrid target.');
    }
    const body = {
      deployment_mode: mode,
      authorization_acknowledged: q('authorization-ack').checked,
      base_url: q('external-base-url').value,
      provider: { kind: q('provider').value, base_url: q('provider-base-url').value, model: q('provider-model').value, api_key: q('provider-api-key').value },
      env: {},
      gpu: { mode: q('gpu-mode').value, device_ids: q('gpu-devices').value },
      ports: [Number(q('port').value || 8000)],
      memory: q('memory').value,
      cpus: q('cpus').value,
      publish_ports: q('publish-ports').value === 'true',
      target: { type: q('target-type').value, endpoint_path: q('endpoint-path').value, method: q('http-method').value, safety_profile: 'local_lab_safe' },
    };
    note('Deploying ' + state.selected.id + '… (build/run/health-check can take a minute)');
    const data = await request('/api/agent-lab/projects/' + encodeURIComponent(state.selected.id) + '/deploy', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(body) });
    state.lastTargets = data.target_ids || [];
    state.lastDeployment = data;
    renderDeploymentSummary(data);
    renderDeploySuccess(data);
    note('Deployed ' + data.project_id + ' — auto-created target ' + (data.target_ids || []).join(', '));
    await load();
    renderTargets();
  } catch (e) {
    note(e.message, false);
    renderDeployFailure(e.message);
  }
}

function renderDeploymentSummary(data) {
  const card = q('deployment-summary');
  if (!data || !data.deployed) {
    card.classList.add('hidden');
    return;
  }
  const contract = data.endpoint_contract || {};
  const health = data.health_status || 'unknown';
  const rows = [
    ['Deployment mode', data.deployment_mode || 'container'],
    ['Reachable base URL', data.base_url || '(not published)'],
    ['Selected endpoint', (contract.method || '') + ' ' + (contract.path || '')],
    ['Request param', contract.param_key ? `${contract.param_key} (${contract.param_style || 'json'})` : '—'],
    ['Response shape', contract.response_shape || '—'],
    ['Target ID', (data.target_ids || []).join(', ') || '—'],
    ['Container port', data.container_port != null ? String(data.container_port) : '—'],
    ['Host port', data.host_port != null ? String(data.host_port) : '—'],
  ];
  q('summary-grid').innerHTML =
    rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`).join('') +
    `<dt>Health</dt><dd><span class="health-${escapeHtml(health)}">${escapeHtml(health)}</span></dd>`;
  card.classList.remove('hidden');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// --- readable renderers (replace raw-JSON dumps) --------------------------------

function methodBadge(method) {
  const m = String(method || '').toUpperCase() || 'POST';
  return `<span class="method method-${escapeHtml(m.toLowerCase())}">${escapeHtml(m)}</span>`;
}

// Compact human-readable contract: "GET /get ?msg= → text".
function contractChip(c) {
  if (!c || !c.path) return '';
  const param = c.param_key
    ? (c.param_style === 'query' ? `?${escapeHtml(c.param_key)}=` : `{ ${escapeHtml(c.param_key)} }`)
    : '';
  const shape = c.response_shape ? ` <span class="arrow">→</span> <span class="shape">${escapeHtml(c.response_shape)}</span>` : '';
  return `${methodBadge(c.method)}<code class="path">${escapeHtml(c.path)}</code>${param ? `<code class="param">${param}</code>` : ''}${shape}`;
}

function renderAnalysis(info) {
  const el = q('analysis');
  const sel = info.selected_endpoint;
  const facts = [
    ['Framework', info.framework || 'unknown'],
    ['Detected ports', (info.ports || []).join(', ') || '—'],
    ['Dockerfile', info.has_dockerfile ? 'in project' : 'auto-generated on deploy'],
    ['Source', `${info.source || '—'}${info.writable === false ? ' · read-only' : ''}`],
    ['Files', info.file_count != null ? String(info.file_count) : '—'],
  ];
  const factRows = facts.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd>`).join('');
  const envs = info.env_vars || [];
  const envBlock = envs.length
    ? `<div class="analysis-sub"><span class="analysis-sub-label">Environment variables</span><div class="pills">${envs.map((e) => `<span class="pill">${escapeHtml(e.name)}${e.required ? ' *' : ''}</span>`).join('')}</div></div>`
    : '';
  const contractBlock = sel
    ? `<div class="contract-chip">${contractChip(sel)}</div>
       <p class="analysis-hint">VulnoraIQ will register a target with this exact method, path, request key, and response handling — no manual edits.</p>`
    : `<div class="analysis-warn">No inference endpoint was auto-detected. Set the HTTP method and endpoint path yourself below, or use <strong>External endpoint</strong> mode to point at a URL you already run.</div>`;
  el.innerHTML = `
    <div class="analysis-head">
      <span class="analysis-name">${escapeHtml(info.name || info.id || 'project')}</span>
      <span class="analysis-detected">Detected inference endpoint</span>
    </div>
    ${contractBlock}
    <dl class="fact-grid">${factRows}</dl>
    ${envBlock}`;
}

// Live preview of the target that the current form settings will produce.
function renderContractPreview() {
  const wrap = q('contract-preview');
  const body = q('contract-preview-body');
  if (!state.selected) { wrap.classList.add('hidden'); return; }
  const type = q('target-type').value;
  let c;
  if (type === 'chat_completions') {
    c = { method: 'POST', path: '/v1/chat/completions', param_key: 'messages', param_style: 'json', response_shape: 'json' };
  } else {
    const sel = state.selected.selected_endpoint || {};
    c = {
      method: q('http-method').value,
      path: q('endpoint-path').value || '/',
      param_key: sel.param_key,
      param_style: sel.param_style,
      response_shape: sel.response_shape,
    };
  }
  body.innerHTML = contractChip(c) || '<span class="muted">Set a method and endpoint path.</span>';
  wrap.classList.remove('hidden');
}

// Collapse runs of identical log lines ("ERROR ... (×9)") so failure output is
// scannable instead of a wall of repeats.
function dedupeLogs(text) {
  const lines = String(text || '').split(/\r?\n/);
  const out = [];
  for (const line of lines) {
    const last = out[out.length - 1];
    if (last && last.text === line) { last.count += 1; }
    else { out.push({ text: line, count: 1 }); }
  }
  return out.map((l) => (l.count > 1 ? `${l.text}  (×${l.count})` : l.text)).join('\n').trim();
}

function renderDeploySuccess(data) {
  const el = q('deployments');
  const c = data.endpoint_contract || {};
  el.innerHTML = `
    <div class="result result-ok">
      <div class="result-head"><span class="result-dot"></span>Deployed ${escapeHtml(data.project_id || '')}</div>
      <div class="result-contract contract-chip">${contractChip(c)}</div>
      <dl class="fact-grid">
        <dt>Reachable URL</dt><dd>${escapeHtml(data.base_url || '—')}</dd>
        <dt>Target</dt><dd>${escapeHtml((data.target_ids || []).join(', ') || '—')}</dd>
        <dt>Health</dt><dd><span class="health-${escapeHtml(data.health_status || 'unknown')}">${escapeHtml(data.health_status || 'unknown')}</span></dd>
      </dl>
      <p class="analysis-hint">Pick this target under “5. Test with VulnoraIQ” and start a scan.</p>
    </div>`;
}

function renderDeployFailure(message) {
  const el = q('deployments');
  const marker = 'Last container logs:';
  const idx = String(message).indexOf(marker);
  const summary = idx >= 0 ? String(message).slice(0, idx).trim() : String(message).trim();
  const logs = idx >= 0 ? dedupeLogs(String(message).slice(idx + marker.length)) : '';
  el.innerHTML = `
    <div class="result result-fail">
      <div class="result-head"><span class="result-dot"></span>Deployment failed</div>
      <p class="result-msg">${escapeHtml(summary)}</p>
      ${logs ? `<details open><summary>Container logs</summary><pre class="log-block">${escapeHtml(logs)}</pre></details>` : ''}
    </div>`;
}

function renderScanAccepted(data) {
  const el = q('deployments');
  el.innerHTML = `
    <div class="result result-ok">
      <div class="result-head"><span class="result-dot"></span>Scan queued</div>
      <dl class="fact-grid">
        <dt>Scan ID</dt><dd>${escapeHtml(data.id || '—')}</dd>
        <dt>Target</dt><dd>${escapeHtml(data.target || '—')}</dd>
        <dt>Profile</dt><dd>${escapeHtml(data.profile || '—')}</dd>
        <dt>Status</dt><dd>${escapeHtml(data.status || 'queued')}</dd>
      </dl>
      <p class="analysis-hint">Follow progress and evidence in the main console Overview.</p>
    </div>`;
}

async function summaryRunScan() {
  const ids = state.lastTargets;
  if (!ids.length) {
    note('No auto-created target to scan yet.', false);
    return;
  }
  q('target-select').value = ids[0];
  await scan();
}

async function summaryRemove() {
  const dep = state.lastDeployment;
  if (!dep) return;
  const ident = dep.deployment_id || dep.project_id;
  if (!window.confirm(`Stop and remove deployment '${ident}'?`)) return;
  try {
    const data = await request('/api/agent-lab/deployments/' + encodeURIComponent(ident) + '/remove', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: '{}' });
    note(data.removed ? 'Removed deployment ' + ident : 'No running container found for ' + ident);
    state.lastDeployment = null;
    q('deployment-summary').classList.add('hidden');
    await load();
  } catch (e) {
    note(e.message, false);
  }
}

function renderTargets() {
  const ids = state.lastTargets.length ? state.lastTargets : Object.keys(state.targets).filter((id) => id.startsWith('agent-lab-'));
  q('target-select').innerHTML = ids.map((id) => `<option value="${id}">${id}</option>`).join('');
  q('start-scan').disabled = !ids.length;
}

async function scan() {
  try {
    const body = { target: q('target-select').value, profile: q('scan-profile').value || 'baseline', authorised: true };
    const data = await request('/api/scans', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': await token() }, body: JSON.stringify(body) });
    renderScanAccepted(data);
    note('Scan queued for ' + (data.target || 'target'));
  } catch (e) {
    note(e.message, false);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  q('git-form').onsubmit = importGit;
  q('zip-form').onsubmit = importZip;
  q('folder-form').onsubmit = importFolder;
  q('refresh').onclick = load;
  q('refresh-mounted').onclick = load;
  q('project-filter').oninput = renderProjects;
  q('provider').onchange = providerChanged;
  q('deployment-mode').onchange = deploymentModeChanged;
  // Keep the "target VulnoraIQ will create" preview in sync with manual edits.
  q('http-method').onchange = renderContractPreview;
  q('endpoint-path').oninput = renderContractPreview;
  q('target-type').onchange = renderContractPreview;
  q('deploy').onclick = deploy;
  q('start-scan').onclick = scan;
  q('summary-run-scan').onclick = summaryRunScan;
  q('summary-remove').onclick = summaryRemove;
  deploymentModeChanged();
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll('.tab,.tab-panel').forEach((x) => x.classList.remove('active'));
      tab.classList.add('active');
      (q(tab.dataset.tab + '-form') || q(tab.dataset.tab + '-panel')).classList.add('active');
    };
  });
  load();
});
