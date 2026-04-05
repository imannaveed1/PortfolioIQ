// ─── State ────────────────────────────────────────────────────────────────

let analysisData = null;
let charts = {};

// ─── Tab Switching ────────────────────────────────────────────────────────

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  document.getElementById('panel-' + tab).classList.add('active');
}

function setExampleUrl(url) {
  document.getElementById('url-input').value = url;
  document.getElementById('url-input').focus();
}

// ─── Screen Management ────────────────────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

function resetApp() {
  analysisData = null;
  Object.values(charts).forEach(c => { try { c.destroy(); } catch(e){} });
  charts = {};
  document.getElementById('file-input').value = '';
  document.getElementById('url-input').value = '';
  setProgress(0, 'Ready');
  showScreen('upload-screen');
}

// ─── Progress ─────────────────────────────────────────────────────────────

function setProgress(pct, label, source) {
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-pct').textContent = pct + '%';
  if (label) document.getElementById('progress-label').textContent = label;
  if (source !== undefined) document.getElementById('progress-source').textContent = source;
}

// ─── Upload & Analyze ─────────────────────────────────────────────────────

async function analyzeFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    alert('Please upload a valid image file (PNG, JPG, WEBP, BMP).');
    return;
  }

  document.getElementById('progress-title').textContent = 'Analyzing your design…';
  document.getElementById('progress-spinner').textContent = '⚙️';
  showScreen('progress-screen');
  setProgress(5, 'Uploading image…', file.name);

  const formData = new FormData();
  formData.append('image', file);

  const steps = [
    [15, 'Extracting color palette…'],
    [30, 'Running K-Means clustering…'],
    [50, 'Analyzing contrast ratios…'],
    [65, 'Measuring layout balance…'],
    [78, 'Detecting design style…'],
    [88, 'Calculating scores…'],
    [94, 'Generating suggestions…'],
  ];

  let stepIdx = 0;
  const ticker = setInterval(() => {
    if (stepIdx < steps.length) setProgress(...steps[stepIdx++]);
  }, 400);

  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });
    clearInterval(ticker);
    if (!res.ok) { const e = await res.json(); throw new Error(e.error || 'Analysis failed'); }
    const data = await res.json();
    analysisData = data;
    setProgress(100, 'Done!');
    await delay(350);
    renderResults(data);
    showScreen('results-screen');
  } catch (err) {
    clearInterval(ticker);
    alert('Error: ' + err.message);
    resetApp();
  }
}

// ─── URL Analysis ─────────────────────────────────────────────────────────

async function analyzeFromUrl() {
  const raw = document.getElementById('url-input').value.trim();
  if (!raw) { alert('Please enter a URL.'); return; }

  let url = raw;
  if (!url.startsWith('http://') && !url.startsWith('https://')) url = 'https://' + url;

  document.getElementById('progress-title').textContent = 'Loading your portfolio…';
  document.getElementById('progress-spinner').textContent = '🌐';
  showScreen('progress-screen');
  setProgress(5, 'Launching headless browser…', url);

  const steps = [
    [1200, 10, 'Opening browser…'],
    [2500, 20, 'Navigating to URL…'],
    [5000, 35, 'Waiting for page to load…'],
    [8000, 50, 'Rendering fonts & images…'],
    [11000, 62, 'Taking screenshot…'],
    [13000, 72, 'Extracting color palette…'],
    [15000, 82, 'Analyzing layout & contrast…'],
    [17000, 91, 'Detecting design style…'],
  ];

  const timers = steps.map(([ms, pct, label]) =>
    setTimeout(() => setProgress(pct, label), ms)
  );

  try {
    const res = await fetch('/analyze-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    timers.forEach(t => clearTimeout(t));

    if (!res.ok) { const e = await res.json(); throw new Error(e.error || 'URL analysis failed'); }
    const data = await res.json();
    analysisData = data;
    setProgress(100, 'Done!');
    await delay(350);
    renderResults(data);
    showScreen('results-screen');
  } catch (err) {
    timers.forEach(t => clearTimeout(t));
    alert('Error: ' + err.message);
    resetApp();
  }
}

// ─── Render Results ───────────────────────────────────────────────────────

function renderResults(data) {
  const src = data.source || {};
  const sourceEl = document.getElementById('source-tag');
  if (src.type === 'url') {
    sourceEl.innerHTML = `🌐 <a href="${src.url}" target="_blank" rel="noopener">${src.title || src.url}</a>`;
  } else {
    sourceEl.innerHTML = `📸 ${src.name || 'Uploaded image'}`;
  }

  renderHeroScore(data);
  renderStyleChart(data.style);
  renderScoreGrid(data.scores);
  renderPalette(data.palette);
  renderContrast(data.contrast);
  renderLayout(data.balance, data.whitespace, data.edge_density);
  renderSuggestions(data.suggestions);
}

function scoreColor(s) {
  if (s >= 75) return '#22c55e';
  if (s >= 50) return '#f59e0b';
  return '#ef4444';
}

function renderHeroScore(data) {
  const score = data.scores.overall;
  document.getElementById('score-overall-num').textContent = Math.round(score);
  document.getElementById('score-overall-num').style.color = scoreColor(score);
  document.getElementById('style-badge').textContent =
    `${data.style.detected} · ${data.style.confidence.toFixed(0)}% confidence`;

  if (charts['overall']) charts['overall'].destroy();
  const ctx = document.getElementById('chart-overall').getContext('2d');
  charts['overall'] = new Chart(ctx, {
    type: 'doughnut',
    data: { datasets: [{ data: [score, 100 - score],
      backgroundColor: [scoreColor(score), 'rgba(255,255,255,0.05)'],
      borderWidth: 0, hoverOffset: 0 }] },
    options: { cutout: '75%',
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { animateRotate: true, duration: 900 } }
  });
}

function renderStyleChart(style) {
  const labels = Object.keys(style.scores);
  const values = Object.values(style.scores);
  const colors = labels.map(l => l === style.detected ? '#a855f7' : 'rgba(255,255,255,0.15)');

  if (charts['style']) charts['style'].destroy();
  const ctx = document.getElementById('chart-style').getContext('2d');
  charts['style'] = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 6, borderSkipped: false }] },
    options: { indexAxis: 'y',
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${c.parsed.x.toFixed(1)}%` } } },
      scales: {
        x: { max: 100, grid: { color: 'rgba(255,255,255,0.06)' }, ticks: { color: '#64748b', font: { size: 10 } } },
        y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 11 } } }
      }
    }
  });
}

function renderScoreGrid(scores) {
  const items = [
    { label: 'Contrast',      key: 'contrast' },
    { label: 'Balance',       key: 'balance' },
    { label: 'Whitespace',    key: 'whitespace' },
    { label: 'Color Variety', key: 'color_variety' },
    { label: 'Complexity',    key: 'complexity' },
    { label: 'Overall',       key: 'overall' },
  ];
  const grid = document.getElementById('score-grid');
  grid.innerHTML = '';
  items.forEach(item => {
    const val = Math.round(scores[item.key] || 0);
    const col = scoreColor(val);
    const card = document.createElement('div');
    card.className = 'score-card';
    card.innerHTML = `
      <div class="score-card-num" style="color:${col}">${val}</div>
      <div class="score-card-label">${item.label}</div>
      <div class="score-card-bar">
        <div class="score-card-bar-fill" style="width:${val}%;background:${col}"></div>
      </div>`;
    grid.appendChild(card);
  });
}

function renderPalette(palette) {
  const row = document.getElementById('palette-row');
  row.innerHTML = '';
  palette.forEach(c => {
    const item = document.createElement('div');
    item.className = 'swatch-item';
    item.title = `${c.hex}\nBrightness: ${c.brightness.toFixed(0)}\nUsage: ${c.percentage.toFixed(1)}%`;
    item.innerHTML = `
      <div class="swatch-color" style="background:${c.hex};box-shadow:0 4px 12px ${c.hex}55"></div>
      <div class="swatch-hex">${c.hex}</div>
      <div class="swatch-pct">${c.percentage.toFixed(1)}%</div>`;
    item.addEventListener('click', () => { navigator.clipboard.writeText(c.hex); showToast(`Copied ${c.hex}`); });
    row.appendChild(item);
  });

  if (charts['palette']) charts['palette'].destroy();
  const ctx = document.getElementById('chart-palette').getContext('2d');
  charts['palette'] = new Chart(ctx, {
    type: 'bar',
    data: { labels: palette.map(c => c.hex),
      datasets: [{ label: 'Usage %', data: palette.map(c => c.percentage),
        backgroundColor: palette.map(c => c.hex), borderRadius: 6 }] },
    options: { plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748b', font: { family: "'DM Mono',monospace", size: 9 } } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { size: 10 } },
          title: { display: true, text: 'Usage %', color: '#64748b', font: { size: 10 } } }
      }
    }
  });
}

function renderContrast(contrast) {
  const best = contrast.best_pair || {};
  const metrics = [
    { label: 'Best Contrast Ratio', val: `${contrast.best_ratio.toFixed(2)}:1`,
      note: contrast.best_ratio >= 4.5 ? 'WCAG AA Pass' : 'Below WCAG AA', ok: contrast.best_ratio >= 4.5 },
    { label: 'WCAG AA Pass Rate', val: `${contrast.wcag_aa_pass_rate.toFixed(1)}%`,
      note: 'of color pairs', ok: contrast.wcag_aa_pass_rate >= 50 },
    { label: 'Best Pair', val: `${best.color1 || '–'} / ${best.color2 || '–'}`,
      note: best.wcag_aaa ? 'Meets AAA' : best.wcag_aa ? 'Meets AA' : 'Does not meet AA', ok: best.wcag_aa },
  ];

  document.getElementById('contrast-metrics').innerHTML = metrics.map(m => `
    <div class="metric-box">
      <div class="metric-box-label">${m.label}</div>
      <div class="metric-box-val" style="color:${m.ok?'#22c55e':'#f59e0b'};font-family:'DM Mono',monospace;font-size:14px">${m.val}</div>
      <div class="metric-box-note">${m.note}</div>
    </div>`).join('');

  const tbody = document.querySelector('#contrast-table tbody');
  tbody.innerHTML = contrast.pairs.slice(0, 8).map(p => `
    <tr>
      <td><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${p.color1};vertical-align:middle;margin-right:6px"></span>
          <code style="font-size:11px">${p.color1}</code></td>
      <td><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${p.color2};vertical-align:middle;margin-right:6px"></span>
          <code style="font-size:11px">${p.color2}</code></td>
      <td><strong>${p.ratio.toFixed(2)}:1</strong></td>
      <td class="${p.wcag_aa?'pass':'fail'}">${p.wcag_aa?'✓ Pass':'✗ Fail'}</td>
      <td class="${p.wcag_aaa?'pass':'fail'}">${p.wcag_aaa?'✓ Pass':'✗ Fail'}</td>
    </tr>`).join('');
}

function renderLayout(balance, whitespace, edgeDensity) {
  if (charts['balance']) charts['balance'].destroy();
  const ctx = document.getElementById('chart-balance').getContext('2d');
  charts['balance'] = new Chart(ctx, {
    type: 'radar',
    data: { labels: ['L/R Balance', 'T/B Balance', 'Edge Balance', 'Whitespace', 'Neg. Space'],
      datasets: [{ label: 'Layout Metrics',
        data: [balance.lr_balance, balance.tb_balance, balance.edge_balance, whitespace.score, whitespace.score],
        backgroundColor: 'rgba(124,58,237,0.15)', borderColor: '#7c3aed',
        pointBackgroundColor: '#a855f7', borderWidth: 2, pointRadius: 4 }] },
    options: { plugins: { legend: { display: false } },
      scales: { r: { min: 0, max: 100,
        grid: { color: 'rgba(255,255,255,0.06)' }, angleLines: { color: 'rgba(255,255,255,0.06)' },
        pointLabels: { color: '#94a3b8', font: { size: 10 } }, ticks: { display: false } } } }
  });

  const items = [
    { label: 'L/R Balance',    val: `${balance.lr_balance.toFixed(1)}%`,   score: balance.lr_balance },
    { label: 'T/B Balance',    val: `${balance.tb_balance.toFixed(1)}%`,   score: balance.tb_balance },
    { label: 'Edge Balance',   val: `${balance.edge_balance.toFixed(1)}%`, score: balance.edge_balance },
    { label: 'Whitespace',     val: `${whitespace.whitespace_ratio.toFixed(1)}%`, score: whitespace.score },
    { label: 'Negative Space', val: `${whitespace.negative_space.toFixed(1)}%`,  score: whitespace.score },
    { label: 'Edge Density',   val: `${edgeDensity.toFixed(2)}%`, score: Math.max(0, 100 - edgeDensity * 5) },
  ];

  document.getElementById('layout-metrics').innerHTML = items.map(item => `
    <div class="metric-box" style="padding:10px 14px">
      <div class="metric-box-label">${item.label}</div>
      <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
        <div style="flex:1;background:rgba(255,255,255,0.08);border-radius:3px;height:5px;overflow:hidden">
          <div style="width:${Math.min(100,item.score)}%;height:100%;background:${scoreColor(item.score)};border-radius:3px"></div>
        </div>
        <span style="font-family:'DM Mono',monospace;font-size:11px;color:${scoreColor(item.score)};font-weight:600">${item.val}</span>
      </div>
    </div>`).join('');
}

function renderSuggestions(suggestions) {
  const colors = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e', Info: '#38bdf8' };
  const bgColors = { High: '#ef444420', Medium: '#f59e0b20', Low: '#22c55e20', Info: '#38bdf820' };

  document.getElementById('suggestions-list').innerHTML = suggestions.map((s, i) => {
    const col = colors[s.priority] || '#7c3aed';
    const bg  = bgColors[s.priority] || '#7c3aed20';
    return `
      <div class="suggestion-card">
        <div class="suggestion-stripe" style="background:${col}"></div>
        <div class="suggestion-body">
          <div class="suggestion-top">
            <span style="color:${col};font-family:'DM Mono',monospace;font-size:11px;font-weight:600">#${i+1}</span>
            <span class="priority-badge" style="background:${bg};color:${col}">${s.priority}</span>
            <span class="suggestion-issue">${s.issue}</span>
            <span class="cat-badge">${s.category}</span>
          </div>
          <div class="suggestion-text">${s.suggestion}</div>
        </div>
      </div>`;
  }).join('');
}

// ─── Download Report ──────────────────────────────────────────────────────

async function downloadReport() {
  if (!analysisData) return;
  const btn = document.querySelector('.btn-primary');
  btn.textContent = '⏳ Generating PDF…';
  btn.disabled = true;

  try {
    const res = await fetch('/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(analysisData),
    });
    if (!res.ok) throw new Error('Failed to generate report');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'portfolio_analysis.pdf'; a.click();
    URL.revokeObjectURL(url);
    showToast('PDF downloaded!');
  } catch (err) {
    alert('Error generating PDF: ' + err.message);
  } finally {
    btn.textContent = '📄 Download PDF Report';
    btn.disabled = false;
  }
}

// ─── Toast ────────────────────────────────────────────────────────────────

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── Event Listeners ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('file-input');
  const dropZone  = document.getElementById('drop-zone');
  const browseBtn = document.querySelector('.link-btn');

  // Browse button opens file picker
  browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  // Drop zone click opens file picker only if not clicking browse button
  dropZone.addEventListener('click', (e) => {
    if (e.target === browseBtn) return;
    fileInput.click();
  });

  // File selected from picker
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      analyzeFile(file);
      // Reset input so same file can be selected again
      fileInput.value = '';
    }
  });

  // Drag and drop
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) analyzeFile(file);
  });
});

// ─── Auth Header ──────────────────────────────────────────────────────────

async function loadAuthHeader() {
  try {
    const res = await fetch('/auth/status');
    const data = await res.json();
    const el = document.getElementById('header-auth');
    if (!el) return;

    if (data.logged_in) {
      el.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px">
          <a href="/history" style="background:rgba(124,58,237,0.2);border:1px solid rgba(124,58,237,0.4);color:#c084fc;padding:7px 14px;border-radius:8px;font-size:12px;text-decoration:none;font-family:'DM Mono',monospace">
            📊 My History
          </a>
          <span style="font-size:13px;color:var(--muted)">Hi, ${data.name.split(' ')[0]}</span>
          <a href="/logout" style="background:var(--card);border:1px solid var(--border);color:var(--muted);padding:7px 14px;border-radius:8px;font-size:12px;text-decoration:none">
            Logout
          </a>
        </div>`;
    } else {
      el.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px">
          <a href="/login" style="background:var(--card);border:1px solid var(--border);color:var(--muted);padding:7px 16px;border-radius:8px;font-size:13px;text-decoration:none">
            Log in
          </a>
          <a href="/signup" style="background:linear-gradient(135deg,#a855f7,#6366f1);border:none;color:white;padding:8px 16px;border-radius:8px;font-size:13px;text-decoration:none;font-weight:700">
            Sign up
          </a>
        </div>`;
    }
  } catch(e) {}
}

document.addEventListener('DOMContentLoaded', loadAuthHeader);
