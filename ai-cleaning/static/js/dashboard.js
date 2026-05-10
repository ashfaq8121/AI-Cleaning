/* AI Smart Data Analyzer — Dashboard JS v2.0 */

/* ── State ────────────────────────────────────────────────────────────────── */
let analysisResult = null;
let currentSection = 'upload';

const SECTIONS = {
  upload:   { title: 'Upload Data',        nav: 'nav-upload'   },
  overview: { title: 'Executive Overview', nav: 'nav-overview' },
  quality:  { title: 'Data Quality',       nav: 'nav-quality'  },
  charts:   { title: 'Visualizations',     nav: 'nav-charts'   },
  insights: { title: 'AI Insights',        nav: 'nav-insights' },
  history:  { title: 'History',            nav: null           },
};

/* ── Boot ─────────────────────────────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', async () => {
  applyTheme(localStorage.getItem('theme') || 'light');
  await loadUser();
  await loadHistory();
});

async function loadUser() {
  try {
    const r = await fetch('/api/me');
    const d = await r.json();
    if (!d.authenticated) { location.href = '/'; return; }
    document.getElementById('unm').textContent  = d.name;
    document.getElementById('uem').textContent  = d.email;
    document.getElementById('uava').textContent = d.name[0].toUpperCase();
  } catch (e) { console.error('loadUser:', e); }
}

async function doLogout() {
  await fetch('/api/logout', { method: 'POST' });
  location.href = '/';
}

/* ── Navigation ───────────────────────────────────────────────────────────── */
function gotoSection(name) {
  if (!(name in SECTIONS)) return;
  currentSection = name;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(`section-${name}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navId = SECTIONS[name]?.nav;
  if (navId) document.getElementById(navId)?.classList.add('active');
  document.getElementById('page-title').textContent = SECTIONS[name]?.title || name;
  if (name === 'history') loadHistory();
}

function unlockNav() {
  ['nav-overview','nav-quality','nav-charts','nav-insights'].forEach(id => {
    document.getElementById(id)?.classList.remove('locked');
  });
  const dlActs = document.getElementById('dl-actions');
  if (dlActs) dlActs.style.display = 'flex';
}

/* ── Theme ────────────────────────────────────────────────────────────────── */
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = t === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('theme', t);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  applyTheme(cur === 'dark' ? 'light' : 'dark');
}

/* ── File Upload ──────────────────────────────────────────────────────────── */
function onDragOver(e)  { e.preventDefault(); document.getElementById('upload-zone').classList.add('drag-over'); }
function onDragLeave()  { document.getElementById('upload-zone').classList.remove('drag-over'); }
function onDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('drag-over');
  const f = e.dataTransfer?.files?.[0];
  if (f) uploadFile(f);
}
function onFileSelect(e) {
  const f = e.target?.files?.[0];
  if (f) uploadFile(f);
}

async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['csv','xlsx','xls'].includes(ext)) {
    showToast('❌ Only CSV and Excel files supported', 'red'); return;
  }

  const zone = document.getElementById('upload-zone');
  zone.style.opacity = '.5'; zone.style.pointerEvents = 'none';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.error) { showToast('❌ ' + d.error, 'red'); return; }
    renderUploadPreview(d, file.name);
    showToast('✅ File loaded — ready to analyze', 'green');
  } catch(e) {
    showToast('❌ Upload failed — check your connection', 'red');
    console.error(e);
  } finally {
    zone.style.opacity = '1'; zone.style.pointerEvents = 'auto';
  }
}

function renderUploadPreview(d, filename) {
  document.getElementById('zone-wrapper').style.display  = 'none';
  document.getElementById('preview-area').style.display  = 'block';

  document.getElementById('upload-kpis').innerHTML = [
    kpiCard('📋', 'Total Rows',    d.rows.toLocaleString(),   '', 'var(--primary)'),
    kpiCard('📑', 'Columns',       d.columns,                 '', 'var(--teal)'),
    kpiCard('📄', 'File',          truncate(filename, 16),     getExt(filename).toUpperCase(), 'var(--amber)'),
    kpiCard('✅', 'Status',        'Ready',                   'Upload complete', 'var(--green)'),
  ].join('');

  // Null bars
  const maxNull = Math.max(...Object.values(d.null_counts), 1);
  document.getElementById('null-summary').innerHTML = d.column_names.map(col => {
    const nc  = d.null_counts[col] || 0;
    const pct = nc / d.rows * 100;
    return `<div class="null-bar">
      <span style="width:140px;flex-shrink:0;font-family:var(--font-mono);font-size:11px">${truncate(col, 18)}</span>
      <div class="null-bar-track"><div class="null-bar-fill" style="width:${pct}%"></div></div>
      <span style="min-width:80px;text-align:right;font-size:11px">
        ${nc > 0 ? `<span style="color:var(--amber)">${nc} null (${pct.toFixed(1)}%)</span>` : '<span style="color:var(--green)">✓ complete</span>'}
      </span>
    </div>`;
  }).join('');

  // Preview table
  const cols = d.column_names;
  let html = `<table><thead><tr>${cols.map(c => `<th>${escHtml(c)}</th>`).join('')}</tr></thead><tbody>`;
  (d.preview || []).forEach(row => {
    html += `<tr>${cols.map(c => `<td>${escHtml(String(row[c] ?? ''))}</td>`).join('')}</tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('preview-table-wrap').innerHTML = html;
}

/* ── Analysis ─────────────────────────────────────────────────────────────── */
async function runAnalysis() {
  document.getElementById('preview-area').style.display  = 'none';
  document.getElementById('progress-area').style.display = 'block';

  const steps = [
    { w: 10, msg: 'Loading and validating dataset…' },
    { w: 22, msg: 'Normalizing column names and detecting types…' },
    { w: 36, msg: 'Cleaning currency, percentages, and text fields…' },
    { w: 50, msg: 'Smart missing value imputation…' },
    { w: 62, msg: 'Removing duplicates and resolving business keys…' },
    { w: 74, msg: 'Parsing dates and creating time features…' },
    { w: 84, msg: 'Outlier detection (IQR + Z-score)…' },
    { w: 91, msg: 'Generating Power BI-style visualizations…' },
    { w: 96, msg: 'Computing AI insights and quality score…' },
  ];

  let si = 0;
  const bar = document.getElementById('prog-bar');
  const msg = document.getElementById('prog-msg');
  const iv  = setInterval(() => {
    if (si < steps.length) { const s = steps[si++]; bar.style.width = s.w+'%'; msg.textContent = s.msg; }
  }, 800);

  try {
    const r = await fetch('/api/analyze', { method: 'POST' });
    const d = await r.json();
    clearInterval(iv);
    bar.style.width = '100%';
    msg.textContent = '✅ Complete!';

    if (d.error) {
      showToast('❌ ' + d.error, 'red');
      document.getElementById('progress-area').style.display = 'none';
      document.getElementById('preview-area').style.display  = 'block';
      return;
    }

    analysisResult = d;
    setTimeout(() => {
      document.getElementById('progress-area').style.display = 'none';
      renderAll(d);
      unlockNav();
      gotoSection('overview');
      showToast('✅ Analysis complete — all sections unlocked', 'green');
    }, 600);

  } catch(e) {
    clearInterval(iv);
    showToast('❌ Analysis failed — check console', 'red');
    console.error(e);
    document.getElementById('progress-area').style.display = 'none';
    document.getElementById('preview-area').style.display  = 'block';
  }
}

/* ── Render All ───────────────────────────────────────────────────────────── */
function renderAll(d) {
  renderOverview(d);
  renderQuality(d);
  renderCharts(d.charts);
  renderInsights(d.insights);
}

/* ── Executive Overview ───────────────────────────────────────────────────── */
function renderOverview(d) {
  const cr     = d.cleaning_report || {};
  const schema = cr.schema || {};
  const cols   = d.columns || [];

  let numC=0, catC=0, dateC=0;
  Object.values(schema).forEach(v => {
    if (['numeric','currency','pct'].includes(v.role)) numC++;
    else if (v.role === 'categorical') catC++;
    else if (v.role === 'date') dateC++;
  });

  document.getElementById('overview-kpis').innerHTML = [
    kpiCard('📋','Clean Records', d.cleaned_rows.toLocaleString(), `from ${d.original_rows.toLocaleString()} original`, 'var(--primary)'),
    kpiCard('📑','Columns',       cols.length, `${numC} numeric · ${catC} categorical`, 'var(--teal)'),
    kpiCard('⭐','Quality Score', d.quality_after+'/100', `improved from ${d.quality_before}`, 'var(--amber)'),
    kpiCard('🗑️','Removed',       (d.original_rows-d.cleaned_rows), 'duplicates + cleaning', 'var(--red)'),
  ].join('');

  // Quality bars
  animQBar('qbar-before', d.quality_before);
  animQBar('qbar-after',  d.quality_after);
  document.getElementById('qnum-before').textContent = d.quality_before;
  document.getElementById('qnum-after').textContent  = d.quality_after;

  // Column roles
  const roleColors = { numeric:'blue', categorical:'green', date:'amber',
    currency:'blue', pct:'blue', id:'red', email:'red', phone:'red', text:'green' };
  document.getElementById('col-type-summary').innerHTML =
    Object.entries(schema).map(([col, info]) =>
      `<div style="display:flex;align-items:center;justify-content:space-between;
        padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:var(--text2);font-family:var(--font-mono)">${truncate(col, 20)}</span>
        <span class="badge badge-${roleColors[info.role]||'blue'}">${info.role}</span>
      </div>`
    ).join('') || '<div style="color:var(--text4);font-size:12px">No schema info</div>';

  // Stats table
  if (d.stats && Object.keys(d.stats).length) {
    const statCols = Object.keys(d.stats);
    let html = `<table><thead><tr>
      <th>Field</th><th>Mean</th><th>Median</th><th>Std Dev</th>
      <th>Min</th><th>Max</th><th>Skew</th><th>Missing</th>
    </tr></thead><tbody>`;
    statCols.forEach(col => {
      const s = d.stats[col];
      const skewWarn = Math.abs(s.skew) > 1.5;
      html += `<tr>
        <td style="font-weight:600;color:var(--text);font-family:var(--font)">${escHtml(col)}</td>
        <td>${fmtNum(s.mean)}</td><td>${fmtNum(s.median)}</td><td>${fmtNum(s.std)}</td>
        <td>${fmtNum(s.min)}</td><td>${fmtNum(s.max)}</td>
        <td style="color:${skewWarn?'var(--amber)':'inherit'}">${s.skew}</td>
        <td style="color:${s.missing>0?'var(--red)':'var(--green)'}">${s.missing > 0 ? '⚠ '+s.missing : '✓ 0'}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('stats-table-wrap').innerHTML = html;
  } else {
    document.getElementById('stats-table-wrap').innerHTML =
      '<div style="padding:20px;color:var(--text4);font-size:13px;text-align:center">No numeric fields found</div>';
  }
}

function animQBar(id, val) {
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el) el.style.width = Math.min(Math.max(val, 0), 100) + '%';
  }, 300);
}

/* ── Data Quality ─────────────────────────────────────────────────────────── */
function renderQuality(d) {
  const cr = d.cleaning_report || {};

  // Before/After comparison
  const nullBefore = sumValues(cr.null_before || {});
  const nullAfter  = sumValues(cr.null_after  || {});
  document.getElementById('ba-grid').innerHTML = `
    <div class="compare-card">
      <div class="compare-label">📊 Before Cleaning</div>
      <div class="compare-row"><span class="compare-key">Total Rows</span><span class="compare-val">${d.original_rows.toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Missing Values</span><span class="compare-val" style="color:var(--red)">${nullBefore.toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Duplicates</span><span class="compare-val" style="color:var(--red)">${(cr.dup_before||0).toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Quality Score</span><span class="compare-val" style="color:var(--amber)">${cr.quality_before||0}/100</span></div>
    </div>
    <div class="compare-card">
      <div class="compare-label">✅ After Cleaning</div>
      <div class="compare-row"><span class="compare-key">Total Rows</span><span class="compare-val improved">${d.cleaned_rows.toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Missing Values</span><span class="compare-val improved">${nullAfter.toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Duplicates</span><span class="compare-val improved">${(cr.dup_after||0).toLocaleString()}</span></div>
      <div class="compare-row"><span class="compare-key">Quality Score</span><span class="compare-val improved">${cr.quality_after||0}/100</span></div>
    </div>`;

  // Cleaning steps
  const steps = cr.steps || ['No cleaning steps required — data was already clean.'];
  document.getElementById('cleaning-steps').innerHTML = steps.map(s =>
    `<div class="step-item"><div class="step-dot"></div><span>${escHtml(s)}</span></div>`
  ).join('');

  // Missing detail
  const missing = cr.missing_handled || {};
  document.getElementById('missing-detail').innerHTML = Object.keys(missing).length
    ? Object.entries(missing).map(([col, info]) =>
        `<div style="display:flex;justify-content:space-between;align-items:flex-start;
          padding:7px 0;border-bottom:1px solid var(--border);font-size:12px">
          <span style="color:var(--text2);font-family:var(--font-mono)">${truncate(col,18)}</span>
          <div style="text-align:right">
            <span class="badge badge-amber">${info.strategy}</span>
            <div style="font-size:10px;color:var(--text4);margin-top:2px">
              ${info.count} filled · ${info.pct}% was null
            </div>
          </div>
        </div>`).join('')
    : '<div style="color:var(--green);font-size:12px;padding:8px 0">✅ No missing values detected</div>';

  // Outliers
  const outliers = cr.outliers_capped || {};
  document.getElementById('outlier-detail').innerHTML = Object.keys(outliers).length
    ? Object.entries(outliers).map(([col, info]) =>
        `<div style="display:flex;justify-content:space-between;align-items:flex-start;
          padding:7px 0;border-bottom:1px solid var(--border);font-size:12px">
          <span style="color:var(--text2);font-family:var(--font-mono)">${truncate(col,18)}</span>
          <div style="text-align:right">
            <span class="badge badge-amber">${info.iqr_count} capped (${info.pct_affected}%)</span>
            <div style="font-size:10px;color:var(--text4);margin-top:2px">
              Fence: [${info.lower_fence}, ${info.upper_fence}]
            </div>
          </div>
        </div>`).join('')
    : '<div style="color:var(--green);font-size:12px;padding:8px 0">✅ No significant outliers detected</div>';

  // Schema changes
  const renames  = cr.column_renames || {};
  const currency = cr.currency_cols  || [];
  const pct      = cr.pct_cols       || [];
  const dates    = cr.dates_parsed   || [];
  const derived  = cr.date_features  || [];

  let html = '';
  if (Object.keys(renames).length) {
    html += `<div style="margin-bottom:10px">
      <div style="font-size:10px;color:var(--text4);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Column Renames</div>
      ${Object.entries(renames).map(([k,v])=>
        `<div style="display:flex;gap:8px;align-items:center;font-size:12px;padding:3px 0">
          <code style="color:var(--text3)">${escHtml(k)}</code>
          <span style="color:var(--text4)">→</span>
          <code style="color:var(--primary)">${escHtml(v)}</code>
        </div>`).join('')}
    </div>`;
  }
  if (currency.length) html += stepLine(`Currency stripped: ${currency.join(', ')}`);
  if (pct.length)      html += stepLine(`Percentages → decimals: ${pct.join(', ')}`);
  if (dates.length)    html += stepLine(`Dates parsed: ${dates.join(', ')}`);
  if (derived.length)  html += stepLine(`Derived features added: ${derived.join(', ')}`);
  if (!html) html = '<div style="color:var(--green);font-size:12px;padding:8px 0">✅ No schema changes needed</div>';
  document.getElementById('schema-detail').innerHTML = html;
}

/* ── Charts ───────────────────────────────────────────────────────────────── */
function renderCharts(charts) {
  const el = document.getElementById('charts-grid');
  if (!charts || !charts.length) {
    el.innerHTML = `<div class="empty-state" style="grid-column:span 2">
      <div class="empty-icon">📊</div><div class="empty-msg">No charts generated</div></div>`;
    return;
  }
  const wideTypes = ['heatmap','box','grouped'];
  const icons     = { histogram:'📊', bar:'📉', line:'📈', kpi:'⭐', heatmap:'🔥', box:'📦', grouped:'🔗' };
  el.innerHTML = charts.map(c =>
    `<div class="chart-card${wideTypes.includes(c.type) ? ' wide' : ''}">
      <div class="chart-header">
        <span>${icons[c.type]||'📊'}</span>
        <span style="font-size:13px;font-weight:600;flex:1">${escHtml(c.title)}</span>
        <span class="chart-type-tag">${c.type}</span>
      </div>
      <img class="chart-img" src="${c.url}" alt="${escHtml(c.title)}" loading="lazy">
    </div>`
  ).join('');
}

/* ── Insights ─────────────────────────────────────────────────────────────── */
function renderInsights(insights) {
  const el = document.getElementById('insights-grid');
  if (!insights || !insights.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">🤖</div>
      <div class="empty-msg">No insights generated</div></div>`;
    return;
  }
  const sevMap = { info:'var(--primary)', success:'var(--green)',
                   warning:'var(--amber)', error:'var(--red)' };
  el.innerHTML = insights.map(ins =>
    `<div class="insight-card" style="--c:${sevMap[ins.severity]||'var(--primary)'}">
      <div class="insight-ico">${ins.icon||'💡'}</div>
      <div style="flex:1">
        <div class="insight-cat">${escHtml(ins.category)}</div>
        <div class="insight-ttl">${escHtml(ins.title)}</div>
        <div class="insight-det">${escHtml(ins.detail)}</div>
      </div>
    </div>`
  ).join('');
}

/* ── History ──────────────────────────────────────────────────────────────── */
async function loadHistory() {
  try {
    const r = await fetch('/api/history');
    const d = await r.json();
    const el = document.getElementById('history-list');
    if (!d.length) {
      el.innerHTML = `<div class="empty-state"><div class="empty-icon">🕑</div>
        <div class="empty-msg">No analyses yet — upload a file to get started</div></div>`;
      return;
    }
    el.innerHTML = d.map(a => {
      const qColor = a.quality_after >= 80 ? 'green' : a.quality_after >= 60 ? 'amber' : 'red';
      const removed = a.original_rows - a.cleaned_rows;
      return `<div class="hist-row">
        <div style="font-size:24px">📊</div>
        <div style="flex:1">
          <div class="hist-file">${escHtml(a.filename)}</div>
          <div class="hist-meta">
            ${a.original_rows.toLocaleString()} rows →
            ${a.cleaned_rows.toLocaleString()} clean
            ${removed > 0 ? `· ${removed} removed` : ''} ·
            ${a.created_at}
          </div>
        </div>
        <div style="text-align:right">
          <span class="badge badge-${qColor}">Quality ${a.quality_after}/100</span>
          <div style="font-size:10px;color:var(--text4);margin-top:4px">from ${a.quality_before}</div>
        </div>
      </div>`;
    }).join('');
  } catch(e) { console.error('loadHistory:', e); }
}

/* ── Downloads ────────────────────────────────────────────────────────────── */
function doDownloadPDF() {
  showToast('⏳ Generating PDF report…', 'primary');
  window.location.href = '/api/download_report';
}
function doDownloadCSV() {
  showToast('⏳ Preparing cleaned CSV…', 'primary');
  window.location.href = '/api/download_clean_csv';
}

/* ── UI Helpers ───────────────────────────────────────────────────────────── */
function kpiCard(icon, label, value, sub, color) {
  return `<div class="kpi-card" style="--c:${color}">
    <div class="kpi-icon">${icon}</div>
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
    ${sub ? `<div class="kpi-sub">${sub}</div>` : ''}
  </div>`;
}

function stepLine(text) {
  return `<div class="step-item" style="margin-bottom:6px">
    <div class="step-dot"></div><span style="font-size:12px">${escHtml(text)}</span>
  </div>`;
}

function sumValues(obj) {
  return Object.values(obj).reduce((s,v) => s + (Number(v)||0), 0);
}

function fmtNum(n) {
  if (n === undefined || n === null) return '—';
  n = parseFloat(n);
  if (isNaN(n)) return '—';
  if (Math.abs(n) >= 1e6)  return (n/1e6).toFixed(1) + 'M';
  if (Math.abs(n) >= 1000) return (n/1000).toFixed(1) + 'K';
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function truncate(s, n) {
  s = String(s);
  return s.length <= n ? s : s.slice(0, n-1) + '…';
}

function getExt(fn) {
  return fn.includes('.') ? fn.split('.').pop() : '';
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let _toastTimer;
function showToast(msg, type = 'primary') {
  const colorMap = { primary:'var(--primary)', green:'var(--green)',
                     red:'var(--red)', amber:'var(--amber)' };
  const el = document.getElementById('toast');
  el.style.setProperty('--c', colorMap[type] || colorMap.primary);
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.style.display = 'none'; }, 3500);
}
