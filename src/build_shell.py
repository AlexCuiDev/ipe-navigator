"""
build_shell.py — 从 samples/MyCompanyInfo_V2.9.html 生成"动态壳"版本

原理：
  原 HTML 把 Portfolio Navigator 数据烤进 HTML（4MB）
  现在改成：HTML 是壳（~50KB），用户点"加载数据"按钮选 Portfolio Navigator HTML
  JS 在浏览器内解析 → 渲染 6 panel

PoC 范围（v1）：
  - 顶部加"加载数据"按钮 + 文件选择
  - JS 移植 extract_from_html.py 核心（axes / croles / GA filter）
  - 6 panel 渲染逻辑不变
  - 缺失提示 + 多文件选择（v2 再做）

依赖：Python 3.x（标准库）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SAMPLE_HTML = ROOT / "samples" / "MyCompanyInfo_V2.9.html"
OUTPUT_HTML = ROOT / "samples" / "MyCompanyInfo_V2.9_shell.html"


# JS parser — 移植自 extract_from_html.py（v2 多版本兼容增强）
PARSER_JS = r"""
// ============================================================================
// Portfolio Navigator HTML → slim data parser (v2.0 — 多版本兼容)
// ============================================================================
// 改进点：
//   1. Auto-discover axes：启发式扫所有 <ul id="c*">，按 id 命名归类
//   2. 多 pattern compat 提取：试 6+ 种属性名
//   3. crolist 鲁棒探测：多 selector 找容器
//   4. 调试模式：暴露 inspectParse() 到 window
// ============================================================================
const DATE_VAR_RE = /--PNdate\s*:\s*"([^"]+)"/;

// ============ 1. 启发式 axis 分类（替代硬编码 AXIS_UL_IDS）============
function classifyAxis(ulId) {
  const l = ulId.toLowerCase();
  // IPE 主轴
  if (l === 'cipe' || /^cipe\d*$/.test(l)) return 'ipe';
  // Portfolio 主轴
  if (l === 'cportfolioname' || /^cportfolioname\d*$/.test(l)) return 'portfolios';
  if (l === 'cportfolios' || /^cportfolios\d*$/.test(l)) return 'portfolios';
  // Industry Portfolio
  if (l === 'cindustryportfolio' || /^cindustryportfolio\d*$/.test(l)) return 'industry_portfolios';
  // ISE
  if (l === 'cise' || /^cise\d*$/.test(l)) return 'ise';
  // R2026x croles 容器
  if (l === 'crolelist' || l === 'croles' || l.includes('crolelist') || /^crole[s_-]?(list|group)/.test(l)) return 'croles_container';
  // meta axes（themes/disciplines/brands/...）→ 返回 null 跳过
  return null;
}

// ============ 2. 多 pattern compat 提取 ============
function extractCompat(li) {
  // 尝试多种属性名（按优先级）
  const COMPAT_ATTRS = [
    'data-compat', 'data-related', 'data-roles', 'data-affinity',
    'data-link', 'data-x', 'data-related-to', 'data-cross',
    'data-connections', 'smart-compat'
  ];
  for (const attr of COMPAT_ATTRS) {
    const v = li.getAttribute(attr);
    if (v) return v.split(/\s+/).filter(Boolean);
  }
  // Fallback: class xN（R2024x）
  const cls = (li.getAttribute('class') || '').split(/\s+/);
  const fromClass = cls.filter(c => /^x\d/i.test(c) || c === 'x');
  if (fromClass.length) return fromClass;
  return [];
}

function extractHooks(li) {
  const h = {cloud: null, premise: null, myoffer: null};
  for (const s of li.querySelectorAll('span')) {
    const cls = (s.getAttribute('class') || '').split(/\s+/);
    if (cls.includes('oc'))        h.cloud   = s.getAttribute('data-idpage');
    else if (cls.includes('op'))   h.premise = s.getAttribute('data-idpage');
    else if (cls.includes('arrow'))h.myoffer = s.getAttribute('data-idpage');
  }
  return h;
}

function extractLi(axis, li) {
  return {
    id: li.id || null,
    name: (li.textContent || '').replace(/\s+/g, ' ').trim(),
    axis_origin: axis,
    compat_with: extractCompat(li),
    hooks: extractHooks(li),
  };
}

// ============ Auto-discover axes（替换硬编码 AXIS_UL_IDS）============
function extractAllAxes(doc) {
  const axes = {};
  let scannedCount = 0;
  for (const ul of doc.querySelectorAll('ul[id^="c"]')) {
    scannedCount++;
    const cat = classifyAxis(ul.id);
    if (!cat) continue;
    if (!axes[cat]) axes[cat] = [];
    const seen = new Set();
    for (const li of ul.querySelectorAll('li')) {
      if (!li.id || seen.has(li.id)) continue;
      seen.add(li.id);
      axes[cat].push(extractLi(cat, li));
    }
  }
  return { axes, scannedCount };
}

// ============ 3. 鲁棒的 crolist 探测（多 selector）============
function extractCroles(doc) {
  const candidates = new Set();
  // (a) 常见 id
  for (const id of ['crolelist', 'croles', 'crolistgroup', 'croleslist', 'croles_container']) {
    const el = doc.getElementById(id);
    if (el) candidates.add(el);
  }
  // (b) class 含 crolist/croles
  for (const el of doc.querySelectorAll('[class*="crolist"], [class*="croles"]')) {
    if (el.tagName === 'UL' || el.tagName === 'DIV') candidates.add(el);
  }
  // (c) 找含 croline 子结构的容器
  for (const c of doc.querySelectorAll('.croleline, [class*="croline"]')) {
    if (c.parentElement) candidates.add(c.parentElement);
  }
  // 选 croline 子结构最多的（排除 li 包装器，只考虑 ul/div 容器）
  let bestContainer = null;
  let bestScore = 0;
  for (const c of candidates) {
    if (c.tagName === 'LI') continue;   // 排除 li 包装器（避免选错）
    const score = c.querySelectorAll('.croleline, [class*="croline"]').length;  // 所有后代
    if (score > bestScore) { bestScore = score; bestContainer = c; }
  }
  if (!bestContainer || bestScore === 0) return [[], []];

  const roles = [];
  const roleItems = [];
  // 找所有后代 croline（不限定直接子级，因为 crolist > li > ul.croleline）
  for (const croline of bestContainer.querySelectorAll('.croleline, [class*="croline"]')) {
    const titleDiv = croline.querySelector(':scope > div.crolename, :scope > [class*="crolename"]');
    const title = titleDiv ? titleDiv.textContent.trim() : null;
    const firstLi = croline.querySelector(':scope > li');
    const groupId = firstLi ? firstLi.id : null;
    let mainLi = null;
    for (const li of croline.querySelectorAll(':scope > li')) {
      const item = extractLi('croles', li);
      item.croline_title = title;
      item.croline_group = groupId;
      roleItems.push(item);
      if (!mainLi) mainLi = item;
    }
    if (mainLi) roles.push(mainLi);
  }
  return [roles, roleItems];
}

function extractAllItems(doc, axes, roleItems) {
  const seen = new Map();
  for (const cat of Object.keys(axes)) {
    if (cat === 'croles_container') continue;
    for (const item of axes[cat]) {
      if (item.id && !seen.has(item.id)) seen.set(item.id, item);
    }
  }
  // roleItems 是 crolist 里的所有 li（父+子），已带 croline_title/croline_group
  for (const item of (roleItems || [])) {
    if (item.id && !seen.has(item.id)) seen.set(item.id, item);
  }
  if (doc.body) {
    for (const li of doc.body.querySelectorAll('li')) {
      const id = li.id;
      if (!id || seen.has(id)) continue;
      if (id.startsWith('x')) seen.set(id, extractLi(null, li));
    }
  }
  return [...seen.values()];
}

function extractMeta(doc) {
  let week = null;
  for (const st of doc.querySelectorAll('style')) {
    const m = st.textContent.match(DATE_VAR_RE);
    if (m) { week = m[1]; break; }
  }
  const titleEl = doc.querySelector('title');
  return {
    title: titleEl ? titleEl.textContent.trim() : null,
    week_label: week,
    extracted_at: new Date().toISOString(),
    tool_version: '2.0-multi-version',
  };
}

function filterGA(data) {
  const raAxis = data.axes.role_availability || [];
  const raMap = {};
  raAxis.forEach(r => raMap[r.id] = (r.name || '').toUpperCase());
  const gaIds = new Set(Object.keys(raMap).filter(k => raMap[k] === 'GA'));
  if (gaIds.size === 0) return 0;
  let removed = 0;
  data.items = data.items.filter(it => {
    const ao = it.axis_origin;
    if (ao && ao !== 'croles') return true;
    const cw = new Set(it.compat_with || []);
    if ([...cw].some(x => gaIds.has(x))) return true;
    removed++;
    return false;
  });
  return removed;
}

function slimSource(data) {
  const FOCUS_AXES = new Set(['ipe', 'portfolios', 'industry_portfolios', 'ise']);
  const FOCUS_ORIGINS = new Set(['ipe', 'portfolio', 'portfolio_releases', 'croles']);
  // 判断此版本是否含 Role 数据：crolist 父项 或 ipe_occupations 任一非空
  const hasCroles = (data.axes.croles || []).length > 0;
  const hasOccupations = (data.axes.ipe_occupations || []).length > 0;
  const hasRoleData = hasCroles || hasOccupations;
  const itemsById = {};
  data.items.forEach(it => { if (it.id) itemsById[it.id] = it; });
  const explicitlyAssigned = new Set();
  for (const ax of FOCUS_AXES) {
    for (const it of (data.axes[ax] || [])) {
      if (it.id) explicitlyAssigned.add(it.id);
    }
  }
  for (const it of (data.axes.portfolio_releases || [])) {
    if (it.id) explicitlyAssigned.add(it.id);
  }
  for (const it of (data.axes.croles || [])) {
    if (it.id) explicitlyAssigned.add(it.id);
  }
  // v6.0: R2024x 等老版本没有 crolist/ipe_occupations，body fallback 的 product offerings 不是 Role
  const focusIds = new Set();
  for (const it of data.items) {
    if (it.croline_group && it.id === it.croline_group) continue;
    if (it.id && explicitlyAssigned.has(it.id)) {
      focusIds.add(it.id);
      continue;
    }
    const ao = it.axis_origin;
    let include = false;
    if (ao && FOCUS_ORIGINS.has(ao)) include = true;
    // 仅当此版本确认含 Role 数据且该 item 不是已被占用的显式 axis item 时才推断为 Role
    else if (!ao && hasRoleData && it.id && !explicitlyAssigned.has(it.id)) {
      include = true;
    }
    if (include && it.id) focusIds.add(it.id);
  }
  const slimItems = [];
  for (const iid of focusIds) {
    const it = itemsById[iid];
    if (!it) continue;
    const isInferredRole = !it.axis_origin && hasRoleData && !explicitlyAssigned.has(iid);
    slimItems.push({
      id: iid,
      name: it.name || '',
      axis_origin: it.axis_origin || (isInferredRole ? 'croles' : ''),
      compat_with: (it.compat_with || []).filter(c => focusIds.has(c)),
      hooks: it.hooks || {},
    });
  }
  const slimAxes = {
    ipe:                 (data.axes.ipe || []).filter(it => focusIds.has(it.id)),
    portfolios:          (data.axes.portfolios || []).filter(it => focusIds.has(it.id)),
    industry_portfolios: (data.axes.industry_portfolios || []).filter(it => focusIds.has(it.id)),
    ise:                 (data.axes.ise || []).filter(it => focusIds.has(it.id)),
  };
  return { meta: { ...data.meta, has_roles: hasRoleData }, axes: slimAxes, items: slimItems };
}

// ============ 4. 调试模式：inspectParse() 暴露给 window ============
function inspectParse() {
  const stats = {
    meta: DATA.meta,
    axes_summary: {},
    items_total: DATA.items.length,
    items_by_origin: {},
    ga_kept: 0,
  };
  for (const ax of ['ipe', 'portfolios', 'industry_portfolios', 'ise', 'croles']) {
    if (DATA.axes[ax]) stats.axes_summary[ax] = DATA.axes[ax].length;
  }
  const originCount = {};
  for (const it of DATA.items) {
    const o = it.axis_origin || '(null)';
    originCount[o] = (originCount[o] || 0) + 1;
  }
  stats.items_by_origin = originCount;
  const raAxis = DATA.axes.role_availability || [];
  const gaIds = new Set(raAxis.filter(r => (r.name || '').toUpperCase() === 'GA').map(r => r.id));
  let gaCount = 0;
  for (const it of DATA.items) {
    const cw = new Set(it.compat_with || []);
    if ([...cw].some(x => gaIds.has(x))) gaCount++;
  }
  stats.ga_kept = gaCount;
  console.log('[inspect-parse]', JSON.stringify(stats, null, 2));
  return stats;
}

async function parsePortfolioHTML(htmlText, onProgress) {
  const yield_ = () => new Promise(r => setTimeout(r, 0));
  onProgress && onProgress('解析 HTML…', 20);
  const doc = new DOMParser().parseFromString(htmlText, 'text/html');
  await yield_();
  onProgress && onProgress('提取元数据…', 30);
  const meta = extractMeta(doc);
  await yield_();
  onProgress && onProgress('Auto-discover axes…', 45);
  // 关键：排除 crolist/croles 容器本身的 li（它是 wrapper，不是 role）
  const { axes, scannedCount } = extractAllAxes(doc);
  // 移除 crolist 容器里的 wrapper li（这些会被 extractCroles 重新提取）
  if (axes.croles_container) {
    // 不删 axes.croles_container，让它去 slim 时被识别为 meta
    // 但要从 items 里排除（避免重复）
  }
  console.log('[parse] scanned', scannedCount, 'c* ul; axes:',
    Object.keys(axes).filter(k => k !== 'croles_container').map(k => k + '=' + (axes[k] || []).length).join(', '));
  await yield_();
  onProgress && onProgress('提取 Role (crolist heuristic)…', 65);
  const [roles, roleItems] = extractCroles(doc);
  // 真正的 roles：父项（4021 个）
  axes.croles = roles;
  // roleItems（父+子）会被 extractAllItems 合并到 items
  console.log('[parse] croles: parents=' + roles.length + ' all=' + roleItems.length);
  await yield_();
  onProgress && onProgress('收集全部 items…', 80);
  const items = extractAllItems(doc, axes, roleItems);
  // 移除 croles_container 里的 wrapper li（防止重复 — 它们 id 跟 children 一样）
  // 实际上 wrapper li 是单独的 id，不会重复，但为了干净，删了
  delete axes.croles_container;
  const raw = { meta, axes, items };
  await yield_();
  onProgress && onProgress('GA 过滤…', 90);
  const removed = filterGA(raw);
  await yield_();
  onProgress && onProgress('生成 slim 数据…', 95);
  const slim = slimSource(raw);
  onProgress && onProgress('完成', 100);
  return { slim, removedGA: removed, rawItemCount: items.length };
}
"""



# File picker UI
LOADER_HTML = r"""
<!-- 数据加载横幅（无数据时显示） -->
<div id="data-loader" style="position:fixed;inset:0;background:rgba(245,247,250,0.97);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:16px;font-family:inherit">
  <div style="font-size:48px">📁</div>
  <div style="font-size:18px;font-weight:600;color:#1f4e79">选择 Portfolio Navigator 文件</div>
  <div style="font-size:13px;color:#666;max-width:480px;text-align:center;line-height:1.6">
    请选择达索提供的 <code>Portfolio_Navigator_xxx.html</code> 文件<br>
    （通常是 30-60MB，浏览器会花 5-15 秒解析）
  </div>
  <label style="background:#1f4e79;color:#fff;padding:10px 24px;border-radius:4px;cursor:pointer;font-size:14px;display:inline-block">
    📂 选择 HTML 文件
    <input type="file" id="file-input" accept=".html,text/html" style="display:none">
  </label>
  <div id="loader-status" style="font-size:12px;color:#888;min-height:18px"></div>
  <div id="loader-progress" style="width:320px;height:6px;background:#e0e0e0;border-radius:3px;overflow:hidden;display:none">
    <div id="loader-bar" style="height:100%;background:#1f4e79;width:0%;transition:width 0.3s"></div>
  </div>
  <div id="loader-error" style="font-size:12px;color:#c0392b;max-width:480px;text-align:center;line-height:1.5;display:none"></div>
  <button id="btn-debug-parse" style="background:transparent;color:#1f4e79;border:1px dashed #1f4e79;padding:4px 12px;border-radius:3px;cursor:pointer;font-size:11px;margin-top:8px" title="加载后用 F12 Console 跑 inspectParse() 看解析详情">🔍 检查解析（数据加载后可用）</button>
</div>

<!-- 顶栏：当前数据源 + 重新选择 + 清缓存 -->
<div id="data-source-bar" style="display:none;background:#1f4e79;color:#fff;padding:6px 16px;font-size:12px;display:flex;align-items:center;gap:12px">
  <span>📊 数据源：</span>
  <span id="data-source-info" style="font-weight:600"></span>
  <span style="flex:1"></span>
  <button id="btn-clear-cache" style="background:transparent;color:#fff;border:1px solid #fff;padding:3px 12px;border-radius:3px;cursor:pointer;font-size:12px" title="清掉当前文件解析缓存（下次打开会重新解析 5-15 秒）">🗑 清缓存</button>
  <button id="btn-reload-data" style="background:transparent;color:#fff;border:1px solid #fff;padding:3px 12px;border-radius:3px;cursor:pointer;font-size:12px">📂 重新选择</button>
</div>
"""


LOADER_JS = r"""
// ============================================================================
// File loader UI logic
// ============================================================================
// DATA 已在前面声明为 const 默认空对象（build_shell.py step 1 注入）
// 这里只声明辅助状态
let parsedInfo = null;

function showLoader() {
  document.getElementById('data-loader').style.display = 'flex';
  document.getElementById('data-source-bar').style.display = 'none';
}
function hideLoader() {
  document.getElementById('data-loader').style.display = 'none';
  document.getElementById('data-source-bar').style.display = 'flex';
}
function setStatus(text) {
  document.getElementById('loader-status').textContent = text;
}
function setError(text) {
  const el = document.getElementById('loader-error');
  if (text) { el.textContent = text; el.style.display = 'block'; }
  else { el.style.display = 'none'; el.textContent = ''; }
}
function setProgress(pct) {
  const wrap = document.getElementById('loader-progress');
  const bar  = document.getElementById('loader-bar');
  if (pct > 0) wrap.style.display = 'block';
  bar.style.width = pct + '%';
}
// ============================================================================
// 缓存：用 localStorage 存 slim 数据，key = file.name + file.size
// SCHEMA_VERSION：parser 逻辑改了之后版本号 +1，让旧缓存自动失效
// ============================================================================
const CACHE_PREFIX = 'mycompany-cache:';
const FINGERPRINT_KEY = 'mycompany-last-fingerprint';
const SCHEMA_VERSION = 6;  // v6：hasRoleData 判定（R2024x 等老版本 body fallback 里的 product offerings 不再误判 Role）
function cacheKey(file) { return CACHE_PREFIX + file.name + '|' + file.size; }
function loadFromCache(file) {
  try {
    const raw = localStorage.getItem(cacheKey(file));
    if (!raw) return null;
    const obj = JSON.parse(raw);
    // 版本不匹配：旧缓存失效
    if (obj._schema !== SCHEMA_VERSION) {
      console.log('[cache] schema mismatch, discarding old cache');
      localStorage.removeItem(cacheKey(file));
      return null;
    }
    return obj;
  } catch (e) { return null; }
}
function saveToCache(file, slim) {
  try {
    const payload = Object.assign({_schema: SCHEMA_VERSION}, slim);
    localStorage.setItem(cacheKey(file), JSON.stringify(payload));
    localStorage.setItem(FINGERPRINT_KEY, file.name + '|' + file.size);
  } catch (e) {
    console.warn('[cache] save failed:', e);
  }
}
function clearCache() {
  try {
    for (const k of Object.keys(localStorage)) {
      if (k.startsWith(CACHE_PREFIX) || k === FINGERPRINT_KEY) localStorage.removeItem(k);
    }
  } catch (e) {}
}

// 上次用的文件指纹（无 file 对象时用于首屏自动加载）
let lastFingerprint = null;
try { lastFingerprint = localStorage.getItem(FINGERPRINT_KEY); } catch (e) {}

async function loadFile(file) {
  setError('');
  // 1) 尝试用缓存（无进度条）
  const cached = loadFromCache(file);
  if (cached) {
    setStatus('使用缓存数据…');
    DATA.meta = cached.meta;
    DATA.axes = cached.axes;
    DATA.items = cached.items;
    parsedInfo = { fileName: file.name, fromCache: true };
    initFromData();
    hideLoader();
    updateSourceBar();
    return;
  }
  // 2) 无缓存：解析 + 显示进度
  setStatus('读取文件…  (' + (file.size/1024/1024).toFixed(1) + ' MB)');
  setProgress(5);
  try {
    await new Promise(r => setTimeout(r, 50));
    const text = await file.text();
    setStatus('解析 HTML…');
    setProgress(20);
    await new Promise(r => setTimeout(r, 50));
    const { slim, removedGA, rawItemCount } = await parsePortfolioHTML(text, (msg, pct) => {
      setStatus(msg);
      setProgress(pct);
    });
    // 替换 DATA 的内容（DATA 是 const，不能重新赋值）
    DATA.meta = slim.meta;
    DATA.axes = slim.axes;
    DATA.items = slim.items;
    parsedInfo = { fileName: file.name, removedGA, rawItemCount, slimItemCount: slim.items.length };
    // 存到缓存
    saveToCache(file, slim);
    initFromData();
    hideLoader();
    updateSourceBar();
  } catch (e) {
    console.error(e);
    setError('解析失败：' + e.message + '\n\n可能原因：\n• 文件不是 Portfolio Navigator HTML\n• HTML 太大浏览器拒绝\n• 文件被其他程序占用');
    setProgress(0);
    setStatus('');
  }
}

// 首屏自动加载缓存（无 file 对象时）
async function tryAutoLoadFromCache() {
  if (!lastFingerprint) return false;
  const [name, sizeStr] = lastFingerprint.split('|');
  const size = parseInt(sizeStr, 10);
  if (!name || !size) return false;
  const fakeFile = { name, size };
  const cached = loadFromCache(fakeFile);
  if (!cached) return false;
  // 静默加载
  DATA.meta = cached.meta;
  DATA.axes = cached.axes;
  DATA.items = cached.items;
  parsedInfo = { fileName: name, fromCache: true, autoLoaded: true };
  setTimeout(() => {
    try {
      if (window.initFromData) window.initFromData();
      hideLoader();
      updateSourceBar();
    } catch (e) { console.error('[auto-load]', e); }
  }, 100);
  return true;
}

function updateSourceBar() {
  if (!parsedInfo) return;
  const ax = DATA.axes;
  const week = DATA.meta.week_label || '?';
  const ipeN = ax.ipe.length;
  const pfN  = ax.portfolios.length;
  const roleN = (DATA.items || []).filter(i => i.axis_origin === 'croles').length;
  const tag = parsedInfo.fromCache ? ' ⚡缓存' : '';
  document.getElementById('data-source-info').textContent =
    parsedInfo.fileName + '  ·  ' + week + '  ·  ' +
    ipeN + ' IPE / ' + pfN + ' Portfolio / ' + roleN + ' Role' + tag;
}
document.addEventListener('DOMContentLoaded', () => {
  const fi = document.getElementById('file-input');
  fi.addEventListener('change', e => {
    const f = e.target.files[0];
    if (f) loadFile(f);
  });
  document.getElementById('btn-reload-data').addEventListener('click', () => {
    showLoader();
    setStatus('');
    setProgress(0);
    setError('');
    fi.value = '';
    fi.click();
  });
  // 清缓存按钮
  document.getElementById('btn-clear-cache').addEventListener('click', () => {
    if (!confirm('清掉所有 Portfolio Navigator 缓存？\n（你的 My Company 选择保留在 localStorage，不影响）\n\n清完后下次打开会重新解析 5-15 秒。')) return;
    const before = Object.keys(localStorage).filter(k => k.startsWith(CACHE_PREFIX) || k === FINGERPRINT_KEY).length;
    clearCache();
    alert('已清理 ' + before + ' 个缓存条目。\n刷新页面后会重新让你选择文件。');
    location.reload();
  });
  // 首屏自动加载缓存（如果有上次用过的文件）
  tryAutoLoadFromCache();
  // Debug 按钮：F12 console 跑 inspectParse() 看解析详情
  document.getElementById('btn-debug-parse').addEventListener('click', () => {
    if (typeof inspectParse === 'function') {
      inspectParse();
      alert('已输出到 F12 Console（标签：inspect-parse）');
    } else {
      alert('还没加载数据，请先选 Portfolio Navigator 文件');
    }
  });
});
"""


def main() -> int:
    if not SAMPLE_HTML.exists():
        print(f"[ERR] {SAMPLE_HTML} not found. Run build_ui.py first.")
        return 1

    print(f"[..] Reading {SAMPLE_HTML} ({SAMPLE_HTML.stat().st_size/1024:.0f} KB)")
    src = SAMPLE_HTML.read_text(encoding='utf-8')

    # 1) 把 baked DATA 替换成默认空对象（让 IIFE 不再因 null 崩溃）
    src = re.sub(
        r'const\s+DATA\s*=\s*\{[^;]*?\};',
        'const DATA = { meta: { title: "", week_label: "" }, axes: { ipe: [], portfolios: [], industry_portfolios: [], ise: [] }, items: [] };  // 壳模式默认空，loadFile 时 Object.assign 更新',
        src,
        count=1,
        flags=re.DOTALL,
    )

    # 2) 在 <main> 之前插入 loader UI
    src = src.replace(
        '<main>',
        LOADER_HTML + '\n<main>',
        1,
    )

    # 3) 在 const DATA 那行后面插入 parser JS + loader JS
    data_marker = 'const DATA = { meta: { title: "", week_label: "" }, axes: { ipe: [], portfolios: [], industry_portfolios: [], ise: [] }, items: [] };  // 壳模式默认空，loadFile 时 Object.assign 更新'
    if data_marker in src:
        src = src.replace(data_marker, data_marker + '\n' + PARSER_JS + '\n' + LOADER_JS, 1)
        print('[OK] PARSER_JS + LOADER_JS 已注入')
    else:
        print('[ERR] DATA marker not found - PARSER_JS/LOADER_JS 未注入！')
        sys.exit(1)

    # 5) 修原代码 pre-existing bug：REACHED 引用了但没定义 → IIFE 末尾崩溃
    src = src.replace(
        'window.IPE = { DATA, ITEMS, SEEDS, REACHED };',
        'const REACHED = SEEDS;  // 兜底别名（兼容原代码引用）\n  window.IPE = { DATA, ITEMS, SEEDS, REACHED };',
        1,
    )
    print('[OK] REACHED bug 已修')

    # 4) 把启动代码包成 bootApp()，等 DATA 加载好再调
    boot_old = """  // ============ 启动 ============
  autoload();
  rerenderAll();
  setupFirstTip();
  setupMycompanyPath();
  setupDragDrop();
  setupExportReminder();"""
    boot_new = """  // ============ 启动（壳模式：等 DATA 加载完成再 boot）===========
  function rebuildDataStructures() {
    // 重建 ITEMS / ITEM_INDEX / INDUSTRY_BY_ID / ISE_BY_ID from DATA
    ITEMS.ipe.length = 0;
    ITEMS.portfolio.length = 0;
    ITEMS.role.length = 0;
    for (const it of (DATA.axes.ipe || [])) ITEMS.ipe.push(it);
    for (const it of (DATA.axes.portfolios || [])) ITEMS.portfolio.push(it);
    for (const it of DATA.items) {
      if (it.axis_origin === 'croles') ITEMS.role.push(it);
    }
    ITEM_INDEX.clear();
    for (const it of ITEMS.ipe)       ITEM_INDEX.set(it.id, {kind:'ipe',       item:it});
    for (const it of ITEMS.portfolio) ITEM_INDEX.set(it.id, {kind:'portfolio', item:it});
    for (const it of ITEMS.role)      ITEM_INDEX.set(it.id, {kind:'role',      item:it});
    INDUSTRY_BY_ID.clear();
    for (const ip of (DATA.axes.industry_portfolios || [])) INDUSTRY_BY_ID.set(ip.id, ip.name);
    ISE_BY_ID.clear();
    for (const ise of (DATA.axes.ise || [])) ISE_BY_ID.set(ise.id, ise.name);
  }
  function bootApp() {
    rebuildDataStructures();
    autoload();
    rerenderAll();
    setupFirstTip();
    setupMycompanyPath();
    setupDragDrop();
    setupExportReminder();
  }
  bootApp();   // DATA 是默认空对象，先 boot 一次（空 panel）
  window.initFromData = function() {
    // 壳模式：loadFile 调这里，DATA 已被 Object.assign 更新
    try { bootApp(); console.log('[shell] initFromData done'); }
    catch (e) { console.error('[shell] initFromData failed:', e); }
  };"""
    if boot_old in src:
        src = src.replace(boot_old, boot_new, 1)
    else:
        print('[WARN] 启动段未找到，IIFE 会在 DATA=null 时崩溃')

    OUTPUT_HTML.write_text(src, encoding='utf-8')
    print(f"[OK] {OUTPUT_HTML} ({OUTPUT_HTML.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
