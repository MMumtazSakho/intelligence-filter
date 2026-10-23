let currentMode = 'one-shot';
let currentStocks = [];
let sortCol = 'roe_ttm';
let sortAsc = false;
let currentSql = '';
let isEditingSql = false;

// Formatters
function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(val)) return "-";
  const absVal = Math.abs(val);
  const sign = val < 0 ? "-" : "";
  if (absVal >= 1e12) {
    return `${sign}Rp ${(absVal / 1e12).toFixed(2)} T`;
  } else if (absVal >= 1e9) {
    return `${sign}Rp ${(absVal / 1e9).toFixed(2)} M`;
  } else {
    return `${sign}Rp ${new Intl.NumberFormat('id-ID').format(Math.round(absVal))}`;
  }
}

function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return `${Number(val).toFixed(2)}%`;
}

function formatRatio(val) {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return Number(val).toFixed(2);
}

// Mode Selection
function setMode(mode) {
  currentMode = mode;
  document.getElementById('modeOneShot').classList.toggle('active', mode === 'one-shot');
  document.getElementById('modeMultistep').classList.toggle('active', mode === 'multistep');
  
  const mainLayout = document.getElementById('mainLayout');
  const contentRight = document.getElementById('contentRight');

  if (mode === 'one-shot') {
    if (mainLayout) mainLayout.classList.remove('multistep-active');
    if (contentRight) contentRight.style.display = 'none';
    document.getElementById('stepsPanel').style.display = 'none';
    document.getElementById('summaryPanel').style.display = 'none';
  } else {
    const hasSteps = document.getElementById('stepsList').children.length > 0;
    const hasSummary = document.getElementById('summaryContent').innerHTML.trim().length > 0;
    if (hasSteps || hasSummary) {
      if (mainLayout) mainLayout.classList.add('multistep-active');
      if (contentRight) contentRight.style.display = 'block';
    }
  }
}

// Preset application
function applyPreset(prompt) {
  document.getElementById('promptInput').value = prompt;
  handleScreen();
}

function resetToAll() {
  document.getElementById('promptInput').value = '';
  document.getElementById('stepsPanel').style.display = 'none';
  document.getElementById('sqlPanel').style.display = 'none';
  const infoText = document.getElementById('sqlInfoText');
  if (infoText) {
    infoText.innerText = '';
    infoText.style.display = 'none';
  }
  document.getElementById('summaryPanel').style.display = 'none';
  
  const mainLayout = document.getElementById('mainLayout');
  const contentRight = document.getElementById('contentRight');
  if (mainLayout) mainLayout.classList.remove('multistep-active');
  if (contentRight) contentRight.style.display = 'none';
  
  fetchAllStocks();
}

// Fetch Initial Stocks
async function fetchAllStocks() {
  setLoading(true, "Memuat data 32 emiten saham...");
  try {
    const res = await fetch('/api/stocks');
    const json = await res.json();
    if (json.status === 'success') {
      currentStocks = json.data;
      renderTable();
      updateStats();
    }
  } catch (err) {
    console.error("Gagal memuat saham:", err);
  } finally {
    setLoading(false);
  }
}

// Handle Screen
async function handleScreen(e) {
  if (e) e.preventDefault();
  const prompt = document.getElementById('promptInput').value.trim();
  if (!prompt) return;

  const submitBtn = document.getElementById('submitBtn');
  submitBtn.disabled = true;

  if (currentMode === 'multistep') {
    await handleMultistepStream(prompt, submitBtn);
    return;
  }

  // One-Shot Mode (Fast Single Pass)
  const mainLayout = document.getElementById('mainLayout');
  const contentRight = document.getElementById('contentRight');
  if (mainLayout) mainLayout.classList.remove('multistep-active');
  if (contentRight) contentRight.style.display = 'none';
  document.getElementById('stepsPanel').style.display = 'none';
  document.getElementById('summaryPanel').style.display = 'none';
  setLoading(true, "Mencari data saham...");

  try {
    const res = await fetch('/api/screen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, mode: 'one-shot' })
    });
    const data = await res.json();

    if (data.status === 'success') {
      currentStocks = data.results || [];
      currentSql = data.sql || '';
      const currentInfo = data.info || '';
      
      displaySql(currentSql, currentInfo);
      document.getElementById('summaryPanel').style.display = 'none';
      renderTable();
      updateStats();
    } else {
      alert("Error: " + (data.message || "Gagal memproses prompt."));
    }
  } catch (err) {
    alert("Koneksi gagal: " + err.message);
  } finally {
    setLoading(false);
    submitBtn.disabled = false;
  }
}

// Multistep Streaming Handler
async function handleMultistepStream(prompt, submitBtn) {
  const mainLayout = document.getElementById('mainLayout');
  const contentRight = document.getElementById('contentRight');
  const stepsPanel = document.getElementById('stepsPanel');
  const stepsList = document.getElementById('stepsList');
  const summaryPanel = document.getElementById('summaryPanel');
  const summaryContent = document.getElementById('summaryContent');

  // Activate side-by-side layout
  if (mainLayout) mainLayout.classList.add('multistep-active');
  if (contentRight) contentRight.style.display = 'block';

  // Reset panels
  stepsList.innerHTML = '';
  stepsPanel.style.display = 'block';
  summaryPanel.style.display = 'none';
  summaryContent.innerHTML = '';
  document.getElementById('sqlPanel').style.display = 'none';

  let streamedSummary = '';

  try {
    const res = await fetch('/api/screen-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, mode: 'multistep' })
    });

    if (!res.ok || !res.body) {
      throw new Error(`Server mengembalikan status ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        const jsonStr = part.replace(/^data:\s*/, '').trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          processAgentEvent(event);
        } catch (err) {
          console.error("Gagal parse event SSE:", err, jsonStr);
        }
      }
    }
  } catch (err) {
    alert("Gagal memproses: " + err.message);
  } finally {
    setLoading(false);
    submitBtn.disabled = false;
  }

  function processAgentEvent(event) {
    if (event.type === 'step_start') {
      startStep(event.info || '');
    } else if (event.type === 'step_end') {
      finishStep(event.meta || '');
    } else if (event.type === 'summary_chunk') {
      summaryPanel.style.display = 'block';
      streamedSummary += event.chunk;
      summaryContent.innerHTML = renderMarkdown(streamedSummary);
      if (contentRight) {
        const isNearBottom = contentRight.scrollHeight - contentRight.scrollTop - contentRight.clientHeight < 120;
        if (isNearBottom) {
          contentRight.scrollTop = contentRight.scrollHeight;
        }
      }
    } else if (event.type === 'complete') {
      finishStep('');
      currentStocks = event.results || [];
      currentSql = event.sql || '';
      displaySql(currentSql, event.info || '');
      renderTable();
      updateStats();
    } else if (event.type === 'error') {
      const active = stepsList.querySelector('.tl-item.active');
      if (active) {
        active.classList.remove('active');
        active.classList.add('failed');
      }
      alert("Error: " + event.message);
    }
  }

  function startStep(text) {
    finishStep('');
    const item = document.createElement('li');
    item.className = 'tl-item active';
    item.innerHTML = `<span class="tl-dot"></span><div class="tl-body"><div class="tl-text">${escapeHtml(text)}</div></div>`;
    stepsList.appendChild(item);
    if (contentRight && (!summaryPanel || summaryPanel.style.display === 'none')) {
      contentRight.scrollTop = contentRight.scrollHeight;
    }
  }

  function finishStep(meta) {
    const active = stepsList.querySelector('.tl-item.active');
    if (!active) return;
    active.classList.remove('active');
    active.classList.add('done');
    if (meta) {
      const m = document.createElement('div');
      m.className = 'tl-meta';
      m.innerText = meta;
      active.querySelector('.tl-body').appendChild(m);
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
  }
}

// Display SQL
function displaySql(sql, info = '') {
  const panel = document.getElementById('sqlPanel');
  const display = document.getElementById('sqlDisplay');
  const editor = document.getElementById('sqlEditor');
  const infoText = document.getElementById('sqlInfoText');

  if (!sql) {
    panel.style.display = 'none';
    return;
  }

  panel.style.display = 'block';
  display.innerText = sql;
  editor.value = sql;
  display.style.display = 'block';
  editor.style.display = 'none';
  document.getElementById('toggleEditBtn').innerText = 'Edit SQL';
  document.getElementById('runCustomSqlBtn').style.display = 'none';
  isEditingSql = false;

  if (infoText) {
    if (info && info.trim()) {
      infoText.innerText = info.trim();
      infoText.style.display = 'block';
    } else {
      infoText.style.display = 'none';
    }
  }
}

function toggleEditSql() {
  const display = document.getElementById('sqlDisplay');
  const editor = document.getElementById('sqlEditor');
  const runBtn = document.getElementById('runCustomSqlBtn');
  const toggleBtn = document.getElementById('toggleEditBtn');

  isEditingSql = !isEditingSql;
  if (isEditingSql) {
    display.style.display = 'none';
    editor.style.display = 'block';
    editor.focus();
    runBtn.style.display = 'inline-block';
    toggleBtn.innerText = 'Batal';
  } else {
    display.style.display = 'block';
    editor.style.display = 'none';
    runBtn.style.display = 'none';
    toggleBtn.innerText = 'Edit SQL';
  }
}

async function runCustomSql() {
  const sql = document.getElementById('sqlEditor').value.trim();
  if (!sql) return;

  setLoading(true, "Mengeksekusi SQL kustom...");
  try {
    const res = await fetch('/api/execute-sql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql })
    });
    const data = await res.json();
    if (data.status === 'success') {
      currentStocks = data.results || [];
      currentSql = sql;
      displaySql(sql, "Query dieksekusi secara manual dari editor SQL.");
      renderTable();
      updateStats();
    } else {
      alert("SQL Error: " + (data.error || "Gagal mengeksekusi query."));
    }
  } catch (err) {
    alert("Gagal menjalankan SQL: " + err.message);
  } finally {
    setLoading(false);
  }
}

function copySql() {
  const sql = currentSql || document.getElementById('sqlDisplay').innerText;
  navigator.clipboard.writeText(sql).then(() => {
    const btn = document.getElementById('copySqlBtn');
    btn.innerText = 'Tersalin!';
    setTimeout(() => { btn.innerText = 'Salin SQL'; }, 2000);
  });
}

// Display Summary
function displaySummary(markdown) {
  const panel = document.getElementById('summaryPanel');
  const container = document.getElementById('summaryContent');
  panel.style.display = 'block';
  container.innerHTML = renderMarkdown(markdown);
}

function renderMarkdown(text) {
  if (!text) return "";

  // Normalize: ensure tables have empty line before them so CommonMark/GFM always parses them as <table>
  let cleanText = text.replace(/([^\n])\n(\|[^\n]+\|)/g, '$1\n\n$2');

  if (typeof marked !== 'undefined' && marked.parse) {
    try {
      return marked.parse(cleanText, { gfm: true, breaks: true });
    } catch (e) {
      console.warn("Marked parser error, falling back:", e);
    }
  }

  // Fallback parser if marked is unavailable
  return cleanText
    .replace(/^### (.*$)/gim, '<h4>$1</h4>')
    .replace(/^## (.*$)/gim, '<h3>$1</h3>')
    .replace(/^# (.*$)/gim, '<h2>$1</h2>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>')
    .replace(/\n/gim, '<br>');
}

// Table Rendering & Sorting
function renderTable() {
  const tbody = document.getElementById('stocksTableBody');
  const emptyState = document.getElementById('emptyState');
  const table = document.getElementById('stocksTable');

  if (!currentStocks || currentStocks.length === 0) {
    tbody.innerHTML = '';
    emptyState.style.display = 'block';
    table.style.display = 'none';
    return;
  }

  emptyState.style.display = 'none';
  table.style.display = 'table';

  // Sort
  const sorted = [...currentStocks].sort((a, b) => {
    let valA = a[sortCol];
    let valB = b[sortCol];

    if (valA === null || valA === undefined) return 1;
    if (valB === null || valB === undefined) return -1;

    if (typeof valA === 'string') {
      return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortAsc ? valA - valB : valB - valA;
  });

  // Update header classes
  document.querySelectorAll('th').forEach(th => {
    th.classList.remove('sorted-asc', 'sorted-desc');
  });

  tbody.innerHTML = sorted.map(s => {
    return `
      <tr>
        <td><span class="symbol-badge">${s.symbol || '-'}</span></td>
        <td class="numeric-cell"><strong>${formatPercent(s.roe_ttm)}</strong></td>
        <td class="numeric-cell">${formatPercent(s.dividend_yield)}</td>
        <td class="numeric-cell">${formatRatio(s.der)}</td>
        <td class="numeric-cell">${formatRatio(s.current_ratio)}</td>
        <td class="numeric-cell">${formatPercent(s.gross_margin)}</td>
        <td class="numeric-cell" title="Nilai tepat: Rp ${s.net_profit_ttm ? s.net_profit_ttm.toLocaleString('id-ID') : '-'}">${formatCurrency(s.net_profit_ttm)}</td>
        <td class="numeric-cell" title="Nilai tepat: Rp ${s.fcf_ttm ? s.fcf_ttm.toLocaleString('id-ID') : '-'}">${formatCurrency(s.fcf_ttm)}</td>
      </tr>
    `;
  }).join('');
}

function sortTable(column) {
  if (sortCol === column) {
    sortAsc = !sortAsc;
  } else {
    sortCol = column;
    sortAsc = false; // default desc for financial metrics
  }
  renderTable();
}

// Update Stats Cards
function updateStats() {
  const count = currentStocks.length;
  document.getElementById('statCount').innerText = count;

  if (count === 0) {
    document.getElementById('statAvgRoe').innerText = '0.0%';
    document.getElementById('statAvgDiv').innerText = '0.0%';
    document.getElementById('statAvgDer').innerText = '0.00';
    return;
  }

  const validRoe = currentStocks.filter(s => s.roe_ttm !== null && !isNaN(s.roe_ttm));
  const avgRoe = validRoe.length > 0 ? (validRoe.reduce((acc, s) => acc + s.roe_ttm, 0) / validRoe.length).toFixed(1) : '0.0';

  const validDiv = currentStocks.filter(s => s.dividend_yield !== null && !isNaN(s.dividend_yield));
  const avgDiv = validDiv.length > 0 ? (validDiv.reduce((acc, s) => acc + s.dividend_yield, 0) / validDiv.length).toFixed(1) : '0.0';

  const validDer = currentStocks.filter(s => s.der !== null && !isNaN(s.der));
  const avgDer = validDer.length > 0 ? (validDer.reduce((acc, s) => acc + s.der, 0) / validDer.length).toFixed(2) : '0.00';

  document.getElementById('statAvgRoe').innerText = `${avgRoe}%`;
  document.getElementById('statAvgDiv').innerText = `${avgDiv}%`;
  document.getElementById('statAvgDer').innerText = avgDer;
}

// Loading state
function setLoading(isLoading, text) {
  const indicator = document.getElementById('loadingIndicator');
  const loadingText = document.getElementById('loadingText');
  if (isLoading) {
    if (text) loadingText.innerText = text;
    indicator.style.display = 'flex';
  } else {
    indicator.style.display = 'none';
  }
}

// Init on page load
document.addEventListener('DOMContentLoaded', () => {
  fetchAllStocks();
});
