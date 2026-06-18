// @Author suke @Date 2026-06-17 10:00:00 @Desc pyknp 前端 v4 — vis-network 主图（增量）+ HTML/CSS 调用链流程图（清晰可读）

if (typeof vis === 'undefined' || !vis.Network) {
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('status-msg');
    if (el) {
      el.textContent = '⚠️ /static/vis-network.min.js 加载失败';
      el.style.color = '#ef4444';
    }
  });
  throw new Error('vis-network not loaded');
}

const NODE_COLORS = {
  function:       '#3b82f6',
  method:         '#8b5cf6',
  nested:         '#6366f1',
  property:       '#ec4899',
  http_endpoint:  '#06b6d4',
  fixture:        '#eab308',
  untagged:       '#6b7280',
};

const EDGE_COLORS = {
  import_fast_path: '#10b981',
  jedi_goto:        '#3b82f6',
  unresolved:       '#4b5563',
};

let currentPayload = null;
let networkInstance = null;
let selectedNodeId = null;
let fileFilter = null;

const fileInput = document.getElementById('zip-input');
const nameInput = document.getElementById('project-name');
const analyzeBtn = document.getElementById('analyze-btn');
const statusMsg = document.getElementById('status-msg');

fileInput.addEventListener('change', () => {
  analyzeBtn.disabled = !fileInput.files.length;
});

analyzeBtn.addEventListener('click', async () => {
  if (!fileInput.files.length) return;
  analyzeBtn.disabled = true;
  statusMsg.style.color = '#9ca3af';
  statusMsg.textContent = 'analyzing...';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const projectName = nameInput.value.trim() || 'uploaded';
  try {
    const resp = await fetch(`/api/analyze?project_name=${encodeURIComponent(projectName)}`, {
      method: 'POST', body: formData,
    });
    if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
    const result = await resp.json();
    console.log('[pyknp] analyze done:', result.run_id, 'funcs:', result.total_functions);
    statusMsg.textContent = `analyze done · ${result.run_id} · ${result.total_functions} funcs / ${result.total_edges} edges; loading graph...`;
    await loadGraph(result.run_id);
  } catch (err) {
    console.error('[pyknp] analyze failed:', err);
    statusMsg.textContent = `error: ${err.message}`;
    statusMsg.style.color = '#ef4444';
  } finally {
    analyzeBtn.disabled = false;
  }
});

async function loadGraph(runId) {
  try {
    statusMsg.textContent = 'fetching graph data...';
    const resp = await fetch(`/api/runs/${runId}/graph`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    currentPayload = await resp.json();
    console.log('[pyknp] graph payload:', currentPayload.nodes.length, 'nodes,', currentPayload.edges.length, 'edges');
    selectedNodeId = null;
    fileFilter = null;
    document.querySelectorAll('#file-tree .file-entry').forEach(e => e.classList.remove('active'));
    document.getElementById('sidebar-right').classList.add('hidden');
    statusMsg.textContent = `rendering ${currentPayload.nodes.length} nodes...`;
    renderStats();
    renderFileTree();
    renderGraph();
    statusMsg.textContent = `done · ${currentPayload.nodes.length} nodes / ${currentPayload.edges.length} edges · 拖拽节点 / 滚轮缩放 / 点击查看详情`;
  } catch (err) {
    console.error('[pyknp] loadGraph failed:', err);
    statusMsg.textContent = `error: ${err.message}`;
    statusMsg.style.color = '#ef4444';
  }
}

function renderStats() {
  if (!currentPayload) return;
  const stats = document.getElementById('stats');
  const prTop = document.getElementById('pagerank-top');
  const total = currentPayload.nodes.length;
  const edgeCount = currentPayload.edges.length;
  const tagCounts = currentPayload.tag_distribution;
  const ntypeCounts = {};
  currentPayload.nodes.forEach(n => {
    ntypeCounts[n.node_type] = (ntypeCounts[n.node_type] || 0) + 1;
  });
  stats.innerHTML = `
    <div><span>functions</span><b>${total}</b></div>
    <div><span>edges</span><b>${edgeCount}</b></div>
    ${Object.entries(ntypeCounts).map(([t, n]) =>
      `<div><span><span style="display:inline-block;background:${NODE_COLORS[t]||'#999'};width:8px;height:8px;border-radius:50%;margin-right:4px;"></span>${t}</span><b>${n}</b></div>`
    ).join('')}
    <div style="margin-top:6px;border-top:1px solid #2a3142;padding-top:6px;">
      ${Object.entries(tagCounts).map(([t, n]) =>
        `<div><span>${t}</span><b>${n}</b></div>`
      ).join('')}
    </div>
  `;
  const top = currentPayload.nodes.slice().sort((a, b) => b.pagerank - a.pagerank).slice(0, 15);
  prTop.innerHTML = top.map(n =>
    `<li data-node-id="${n.location_id}" title="${n.ref_id}">${n.label} <span style="color:#6b7280">${n.pagerank.toFixed(4)}</span></li>`
  ).join('');
  prTop.querySelectorAll('li').forEach(li => {
    li.addEventListener('click', () => selectNode(li.dataset.nodeId));
  });
}

function renderFileTree() {
  if (!currentPayload) return;
  const tree = document.getElementById('file-tree');
  const files = new Map();
  currentPayload.nodes.forEach(n => {
    if (!files.has(n.file)) files.set(n.file, []);
    files.get(n.file).push(n);
  });
  const sorted = [...files.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  tree.innerHTML = sorted.map(([file, fns]) => {
    return `<div class="file-entry" data-file="${file}" title="${fns.length} functions">📄 ${file} <span style="color:#6b7280">(${fns.length})</span></div>`;
  }).join('');
  tree.querySelectorAll('.file-entry').forEach(el => {
    el.addEventListener('click', () => {
      const wasActive = el.classList.contains('active');
      tree.querySelectorAll('.file-entry').forEach(e => e.classList.remove('active'));
      if (wasActive) {
        fileFilter = null;
      } else {
        el.classList.add('active');
        fileFilter = el.dataset.file;
      }
      renderGraph();
    });
  });
}

function visibleNodeTypes() {
  return new Set([...document.querySelectorAll('input[data-ntype]:checked')].map(cb => cb.dataset.ntype));
}
function visibleEdgeTypes() {
  return new Set([...document.querySelectorAll('input[data-etype]:checked')].map(cb => cb.dataset.etype));
}

function getNeighbors(nodeId, depth) {
  if (depth <= 0) return null;
  const visited = new Set([nodeId]);
  const frontier = [nodeId];
  for (let d = 0; d < depth; d++) {
    const next = [];
    for (const id of frontier) {
      for (const e of currentPayload.edges) {
        if (e.source === id && !visited.has(e.target)) { visited.add(e.target); next.push(e.target); }
        if (e.target === id && !visited.has(e.source)) { visited.add(e.source); next.push(e.source); }
      }
    }
    frontier.length = 0; frontier.push(...next);
  }
  return visited;
}

function buildVisData() {
  const visNtypes = visibleNodeTypes();
  const visEtypes = visibleEdgeTypes();
  const depth = parseInt(document.getElementById('depth-filter').value, 10);
  const neighbors = selectedNodeId ? getNeighbors(selectedNodeId, depth) : null;

  const visibleNodes = currentPayload.nodes.filter(n => {
    if (fileFilter && n.file !== fileFilter) return false;
    if (!visNtypes.has(n.node_type)) return false;
    if (neighbors && !neighbors.has(n.location_id)) return false;
    return true;
  });
  const visibleIds = new Set(visibleNodes.map(n => n.location_id));

  const visNodes = visibleNodes.map(n => {
    const color = NODE_COLORS[n.node_type] || NODE_COLORS.untagged;
    const isSelected = n.location_id === selectedNodeId;
    const size = 8 + Math.min(n.pagerank * 300, 24) + (n.in_degree + n.out_degree) * 0.4;
    return {
      id: n.location_id,
      label: n.label,
      title: `${n.ref_id}\n[${n.node_type}] · in:${n.in_degree} out:${n.out_degree} pr:${n.pagerank.toFixed(4)}\n${n.file}`,
      color: { background: color, border: isSelected ? '#fff' : color, highlight: { background: color, border: '#fff' } },
      size: isSelected ? size * 1.4 : size,
      borderWidth: isSelected ? 3 : 1.5,
      font: { color: '#cbd5e1', size: 11, face: 'JetBrains Mono' },
    };
  });

  const visEdges = currentPayload.edges
    .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
    .filter(e => visEtypes.has(e.resolved_via))
    .map((e, i) => {
      const color = EDGE_COLORS[e.resolved_via] || '#4b5563';
      return {
        id: `e${i}`,
        from: e.source, to: e.target,
        color: { color, opacity: 0.55, highlight: color },
        width: e.resolved_via === 'import_fast_path' ? 1.5 : 1,
        dashes: e.resolved_via === 'unresolved',
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        smooth: { enabled: true, type: 'continuous', roundness: 0.3 },
      };
    });

  return { nodes: visNodes, edges: visEdges };
}

const NETWORK_OPTIONS = {
  nodes: { shape: 'dot', shadow: false },
  edges: { selectionWidth: 3 },
  physics: {
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {
      gravitationalConstant: -65, centralGravity: 0.01,
      springLength: 110, springConstant: 0.08,
      damping: 0.5, avoidOverlap: 0.6,
    },
    stabilization: { iterations: 120, updateInterval: 25, fit: true },
  },
  interaction: {
    hover: true, tooltipDelay: 100,
    navigationButtons: true, keyboard: true, multiselect: true,
  },
};

function renderGraph() {
  if (!currentPayload) return;
  try {
    const data = buildVisData();
    const container = document.getElementById('graph');
    const rect = container.getBoundingClientRect();
    if (rect.width < 50 || rect.height < 50) {
      throw new Error(`#graph too small (${rect.width}x${rect.height})`);
    }
    if (networkInstance) {
      // 增量更新：保留物理状态，不闪烁
      networkInstance.setData(data);
    } else {
      console.log(`[pyknp] init render ${data.nodes.length} nodes / ${data.edges.length} edges into ${rect.width}x${rect.height}`);
      networkInstance = new vis.Network(container, data, NETWORK_OPTIONS);
      networkInstance.on('click', (params) => {
        if (params.nodes.length > 0) {
          selectNode(params.nodes[0]);
        } else {
          // 点空白：只取消选择，不销毁图
          if (selectedNodeId) {
            selectedNodeId = null;
            networkInstance.setData(buildVisData());
          }
          document.getElementById('sidebar-right').classList.add('hidden');
        }
      });
      networkInstance.on('stabilizationIterationsDone', () => {
        networkInstance.fit({ animation: false });
      });
    }
    renderLegend();
  } catch (err) {
    console.error('[pyknp] renderGraph failed:', err);
    statusMsg.textContent = `error: ${err.message}`;
    statusMsg.style.color = '#ef4444';
  }
}

function selectNode(nodeId) {
  selectedNodeId = nodeId;
  const node = currentPayload.nodes.find(n => n.location_id === nodeId);
  if (!node) return;
  // 增量更新主图（高亮选中节点）
  networkInstance.setData(buildVisData());
  showDetail(node);
}

async function showDetail(node) {
  const panel = document.getElementById('sidebar-right');
  panel.classList.remove('hidden');
  document.getElementById('detail-title').textContent = node.qualified_name_in_file || node.label;

  // 计算调用关系
  const callers = currentPayload.edges
    .filter(e => e.target === node.location_id)
    .map(e => currentPayload.nodes.find(n => n.location_id === e.source))
    .filter(Boolean);
  const callees = currentPayload.edges
    .filter(e => e.source === node.location_id)
    .map(e => currentPayload.nodes.find(n => n.location_id === e.target))
    .filter(Boolean);

  // 元信息
  const meta = document.getElementById('detail-meta');
  const tagPills = node.tags.map(t => {
    const c = NODE_COLORS[t] || '#6b7280';
    return `<span style="display:inline-block;padding:1px 6px;margin-right:4px;border-radius:8px;font-size:10px;background:${c};color:#0f1419;font-weight:600;">${t}</span>`;
  }).join('');
  meta.innerHTML = `
    <div><span>node_type</span><b>${node.node_type}</b></div>
    <div><span>file</span><b>${node.file}</b></div>
    <div><span>location_id</span><b>${node.location_id}</b></div>
    <div><span>callers</span><b>${callers.length}</b></div>
    <div><span>callees</span><b>${callees.length}</b></div>
    <div><span>pagerank</span><b>${node.pagerank.toFixed(6)}</b></div>
    <div style="display:block;margin-top:6px;">tags: ${tagPills || '<span style="color:#6b7280">(none)</span>'}</div>
  `;

  // mini 调用链图
  renderCallChain(node, callers, callees);

  // 源码
  document.getElementById('source-code').textContent = '加载中...';
  try {
    const startLine = Math.max(1, parseInt(node.location_id.split(':').pop(), 10) - 5);
    const resp = await fetch(
      `/api/runs/${currentPayload.run_id}/source?file=${encodeURIComponent(node.file)}&start_line=${startLine}&end_line=${startLine + 30}`
    );
    document.getElementById('source-code').textContent = resp.ok
      ? (await resp.json()).content
      : `(无法加载: HTTP ${resp.status})`;
  } catch (err) {
    document.getElementById('source-code').textContent = `error: ${err.message}`;
  }
}

function renderCallChain(node, callers, callees) {
  const container = document.getElementById('call-chain');
  if (!container) return;
  const callerMap = new Map(callers.map(c => [c.location_id, c]));
  const calleeMap = new Map(callees.map(c => [c.location_id, c]));
  const callerList = [...callerMap.values()];
  const calleeList = [...calleeMap.values()];

  const MAX_PER_SIDE = 8;
  const shortFile = (f) => (f || '').split('/').slice(-2).join('/');

  const renderNode = (n, isSelf = false) => {
    const color = NODE_COLORS[n.node_type] || '#6b7280';
    return `<div class="chain-node ${isSelf ? 'chain-node-self' : ''}" data-node-id="${n.location_id}" title="${n.ref_id || ''}">
      <span class="chain-node-dot" style="background:${color}"></span>
      <span class="chain-node-name">${n.label}</span>
      <span class="chain-node-meta">${n.node_type} · ${shortFile(n.file)}</span>
    </div>`;
  };

  const renderSide = (list, emptyText) => {
    if (list.length === 0) return `<div class="chain-empty">${emptyText}</div>`;
    const shown = list.slice(0, MAX_PER_SIDE);
    const overflow = list.length - shown.length;
    return shown.map(n => renderNode(n)).join('')
      + (overflow > 0 ? `<div class="chain-more">+${overflow} 更多</div>` : '');
  };

  if (callerList.length === 0 && calleeList.length === 0) {
    container.innerHTML = `<div class="chain-empty" style="padding:24px 12px;">该节点无调用关系（孤岛）</div>`;
    return;
  }

  container.innerHTML = `
    <div class="chain-flow">
      <div class="chain-layer chain-callers">
        <div class="chain-layer-head">
          <span class="chain-layer-icon">▲</span>
          <span class="chain-layer-title">调用方</span>
          <span class="chain-layer-count">${callerList.length}</span>
        </div>
        <div class="chain-nodes">${renderSide(callerList, '无调用方')}</div>
      </div>
      <div class="chain-arrow">▼</div>
      <div class="chain-layer chain-self">
        <div class="chain-layer-head">
          <span class="chain-layer-icon">●</span>
          <span class="chain-layer-title">当前节点</span>
        </div>
        <div class="chain-nodes">${renderNode(node, true)}</div>
      </div>
      <div class="chain-arrow">▼</div>
      <div class="chain-layer chain-callees">
        <div class="chain-layer-head">
          <span class="chain-layer-icon">▼</span>
          <span class="chain-layer-title">被调用</span>
          <span class="chain-layer-count">${calleeList.length}</span>
        </div>
        <div class="chain-nodes">${renderSide(calleeList, '无被调用')}</div>
      </div>
    </div>
  `;

  container.querySelectorAll('.chain-node[data-node-id]').forEach(el => {
    const nid = el.dataset.nodeId;
    if (nid && nid !== node.location_id) {
      el.addEventListener('click', () => selectNode(nid));
    }
  });
}

document.getElementById('detail-close').addEventListener('click', () => {
  document.getElementById('sidebar-right').classList.add('hidden');
  selectedNodeId = null;
  if (networkInstance) networkInstance.setData(buildVisData());
});

document.getElementById('fit-btn').addEventListener('click', () => {
  if (networkInstance) networkInstance.fit({ animation: true });
});

document.getElementById('clear-sel-btn').addEventListener('click', () => {
  selectedNodeId = null;
  fileFilter = null;
  document.querySelectorAll('#file-tree .file-entry').forEach(e => e.classList.remove('active'));
  document.getElementById('sidebar-right').classList.add('hidden');
  if (networkInstance) networkInstance.setData(buildVisData());
});

document.querySelectorAll('input[data-ntype], input[data-etype]').forEach(cb => {
  cb.addEventListener('change', () => { if (networkInstance) networkInstance.setData(buildVisData()); });
});

document.getElementById('depth-filter').addEventListener('change', () => {
  if (networkInstance) networkInstance.setData(buildVisData());
});

function renderLegend() {
  const legend = document.getElementById('legend');
  legend.innerHTML = `
    <div style="color:#6b7280;text-transform:uppercase;font-size:9px;margin-bottom:4px;">Nodes</div>
    ${Object.entries(NODE_COLORS).filter(([t]) => t !== 'untagged').map(([t, c]) =>
      `<div class="lg-item"><span class="lg-swatch" style="background:${c}"></span>${t}</div>`
    ).join('')}
    <div style="color:#6b7280;text-transform:uppercase;font-size:9px;margin:6px 0 4px;">Edges</div>
    ${Object.entries(EDGE_COLORS).map(([t, c]) =>
      `<div class="lg-item"><span class="lg-swatch" style="background:${c};border-radius:1px;height:3px;width:14px;"></span>${t}</div>`
    ).join('')}
  `;
}
