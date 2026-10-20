"""
build_ui.py — v3：6 个 panel 数据源统一、点行 toggle、被选标红+置顶

设计：
  - 6 个 panel 全部从同一份 ITEMS 渲染（不分两份）
  - My Company 三个 panel：filter 显示「已选」集合
  - All Download 三个 panel：显示全部，但「已选」项置顶+红字
  - 点行 → toggle selected 状态
  - 没有任何 + / ↓ 按钮
  - 状态持久化到 localStorage（snapshot 按钮保留）

HTML 框架：6 个 panel + tab 切视图 + 搜索框 + Save/Load/Download all
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# HTML 模板
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!doctype html>
<html lang="en" data-js-pending="1">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Company GVA Info</title>
<style>
  :root {
    --bg: #d6d8db;
    --fg: #1f2937;
    --muted: #6b7280;
    --line: #b8bcc2;
    --accent: #0070c0;
    --accent-bg: #e7f1fb;
    --row-hover: #f3f4f6;
    --restricted: #c0392b;
    --related: #1d4ed8;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body {
    font: 13px/1.4 -apple-system, "Segoe UI", Arial, sans-serif;
    color: var(--fg); background: var(--bg);
    display: flex; flex-direction: column;
  }

  /* ---------- Header (老工具样式: 图标 + 标题 + 5 个 tab) ---------- */
  header {
    background: #f0f1f3; border-bottom: 1px solid var(--line);
    padding: 4px 10px; display: flex; align-items: center; gap: 0;
    -webkit-user-select: none; user-select: none;
  }
  .app-title {
    font-weight: 700; font-size: 13px; color: var(--fg);
    padding: 4px 14px 4px 4px; border-right: 1px solid var(--line);
    margin-right: 6px;
  }
  .app-title .ico {
    display: inline-block; width: 16px; height: 16px; vertical-align: -3px;
    background: var(--accent); border-radius: 2px; margin-right: 6px;
    position: relative;
  }
  .app-title .ico::before {
    content: ""; position: absolute; left: 3px; top: 3px;
    width: 4px; height: 10px; background: #fff;
  }
  .app-title .ico::after {
    content: ""; position: absolute; left: 9px; top: 6px;
    width: 4px; height: 7px; background: #fff;
  }
  .tabs { display: flex; gap: 0; }
  .tabs button {
    background: transparent; border: none; padding: 4px 14px;
    cursor: pointer; font: inherit; color: var(--fg);
    border-right: 1px solid var(--line);
  }
  .tabs button:first-child { border-left: 1px solid var(--line); }
  .tabs button:hover { background: #e1e3e6; }
  .tabs button.active { background: #fff; color: var(--accent); font-weight: 600; }

  /* ---------- Header tools (import/export/clear) ---------- */
  .head-tools { margin-left: auto; display: flex; align-items: center; gap: 4px; padding: 0 6px; }
  .tool-btn {
    background: transparent; border: 1px solid transparent; padding: 4px 10px;
    cursor: pointer; font: inherit; color: var(--fg); border-radius: 3px;
  }
  .tool-btn:hover { background: #e1e3e6; border-color: var(--line); }
  .head-count {
    font-size: 11px; color: var(--muted); padding: 0 8px;
    border-left: 1px solid var(--line); margin-left: 4px;
  }

  /* ---------- Main sections ---------- */
  main {
    flex: 1; min-height: 0;
    padding: 6px 8px; background: var(--bg);
    display: flex; flex-direction: column;
  }
  .row { display: flex; flex-direction: column; min-height: 0; }
  .row + .row { margin-top: 8px; }
  #row-my { flex: 0 0 auto; height: 38vh; min-height: 200px; }
  #row-all { flex: 1 1 auto; min-height: 0; }
  .row > h2 {
    font-size: 12px; margin: 0 0 2px 4px; color: var(--fg);
    font-weight: 600;
    display: flex; align-items: center; gap: 6px;
    border-bottom: 1px solid var(--line);
    padding-bottom: 2px;
  }
  .grid-3 {
    display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 6px;
    min-width: 0; min-height: 0; flex: 1 1 auto;
  }
  /* IPE 区 3 列文字长，分配更多宽度 */
  .grid-3 > .panel { min-width: 0; min-height: 0; }
  @media (max-width: 900px) { .grid-3 { grid-template-columns: 1fr; } }

  .panel {
    background: #fff; border: 1px solid var(--line);
    display: flex; flex-direction: column; min-height: 0;
    height: 100%;
  }
  .panel-h {
    padding: 3px 8px; background: #e8eaed; border-bottom: 1px solid var(--line);
    display: flex; align-items: center; gap: 6px;
    -webkit-user-select: none; user-select: none;
  }
  /* h3 在 panel 标题栏里居中显示 — flex:1 让它占满剩余空间，text-align:center 让文本居中 */
  .panel-h h3 { font-size: 12px; margin: 0; font-weight: 600; color: var(--fg); flex: 1; text-align: center; }
  /* v6.0.3 panel-h 内嵌 +/- 按钮：仅 IPE / Portfolio 有；Role 区域无 */
  .panel-h .panel-act button {
    width: 26px; height: 20px; padding: 0;
    font: 700 14px/1 -apple-system, Arial, sans-serif;
    background: #fff; border: 1px solid var(--line);
    border-radius: 3px; cursor: pointer; color: var(--fg);
    flex: 0 0 auto;
  }
  .panel-h .panel-act button.plus  { color: var(--accent); }
  .panel-h .panel-act button.minus { color: var(--restricted); }
  .panel-h .panel-act button:hover  { background: var(--row-hover); }
  .panel-h .panel-act button:disabled { opacity: 0.35; cursor: not-allowed; }
  .panel-tbl { flex: 1 1 auto; overflow: auto; background: #fff; min-height: 0; }

  /* 表格 — checkbox 列窄、Industry Portfolio 列宽、文字单行不换行 */
  .panel-tbl table {
    width: 100%; border-collapse: collapse; table-layout: fixed;
  }
  .panel-tbl th, .panel-tbl td {
    padding: 2px 6px; font-size: 12px; text-align: left;
    border-bottom: 1px solid #e6e6e6;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .panel-tbl th {
    background: #d9dadd; position: sticky; top: 0; font-weight: 600;
    -webkit-user-select: none; user-select: none;
    border-bottom: 1px solid var(--line);
  }
  .panel-tbl td.cb, .panel-tbl th.cb { width: 24px; padding: 2px 4px; text-align: center; }
  /* v6.0.8 列头不再可点排序，纯文本标签 */
  .panel-tbl td.cb input[type=checkbox], .panel-tbl th.cb input[type=checkbox] {
    cursor: pointer; z-index: 2; position: relative;
    margin: 0; cursor: pointer;
  }
  .panel-tbl tr { cursor: pointer; }
  .panel-tbl tr:hover td { background: #e8eaed; }
  .panel-tbl tr.is-in-mycompany td {
    background: #fce4e4; box-shadow: inset 3px 0 0 #c0392b;
  }
  .panel-tbl tr.is-in-mycompany td.cb { background: #fce4e4; }
  /* 草稿（已勾选但还没 Add 到 myCompany）— 浅黄提示 */
  .panel-tbl tr.is-draft td {
    background: #fff8db; box-shadow: inset 3px 0 0 #f59e0b;
  }
  .panel-tbl tr.is-draft td.cb { background: #fff8db; }
  .panel-tbl tr.is-restricted td { color: var(--restricted); }
  /* 跨轴高亮：IPE/Portfolio 蓝底，Role 红字（匹配 DS Portfolio Navigator 原版） */
  /* IPE / Portfolio 高亮（预览）：浅蓝底 + 蓝色细外框（去左侧竖线） */
  .panel-tbl[data-axis=ipe]       tr.is-highlighted td,
  .panel-tbl[data-axis=portfolio] tr.is-highlighted td {
    background: #cfe2f3; color: #1f4e79; font-weight: 600;
    box-shadow: 0 0 0 1px #6fa8dc;
  }
  /* IPE / Portfolio 高亮 + 已加入公司：保留红竖线 */
  .panel-tbl[data-axis=ipe]       tr.is-highlighted.is-in-mycompany td,
  .panel-tbl[data-axis=portfolio] tr.is-highlighted.is-in-mycompany td {
    box-shadow: inset 3px 0 0 #c0392b, 0 0 0 1px #6fa8dc;
  }
  /* Role 高亮（预览）— 亮黄底 + 棕字 + 棕色细外框（去左侧竖线） */
  .panel-tbl[data-axis=role]      tr.is-highlighted td {
    background: #fef3c7; color: #92400e; font-weight: 700;
    box-shadow: 0 0 0 1px #d97706;
  }
  /* Role 高亮 + 已加入公司：保留红竖线 */
  .panel-tbl[data-axis=role]      tr.is-highlighted.is-in-mycompany td {
    box-shadow: inset 3px 0 0 #c0392b, 0 0 0 1px #d97706;
  }
  /* Search 命中（仅 Role）— 同高亮视觉；与 is-in-mycompany 共存时保留红竖线 */
  .panel-tbl[data-axis=role]      tr.is-search-match td {
    background: #fef3c7; color: #92400e; font-weight: 700;
    box-shadow: 0 0 0 1px #d97706;
  }
  .panel-tbl[data-axis=role]      tr.is-search-match.is-in-mycompany td {
    box-shadow: inset 3px 0 0 #c0392b, 0 0 0 1px #d97706;
  }
  /* 焦点行（点击的那个）— 略加深 + 加粗外框（去左侧竖线） */
  .panel-tbl tr.is-focus td {
    background: #d6e6f5; font-weight: 700;
    box-shadow: 0 0 0 2px #1f4e79;
  }
  .panel-tbl[data-axis=role] tr.is-focus td {
    background: #fbbf24; color: #fff; font-weight: 700;
    box-shadow: 0 0 0 2px #92400e;
  }
  /* 焦点行 + 已加入公司：保留红竖线（加重叠，焦点优先） */
  .panel-tbl tr.is-focus.is-in-mycompany td {
    box-shadow: inset 3px 0 0 #c0392b, 0 0 0 2px #1f4e79;
  }
  .panel-tbl[data-axis=role] tr.is-focus.is-in-mycompany td {
    box-shadow: inset 3px 0 0 #c0392b, 0 0 0 2px #92400e;
  }

  /* 列宽 - Industry Portfolio 加宽 */
  .panel-tbl table col.col-cb { width: 24px; }
  .panel-tbl table col.col-portfolio { width: 30%; min-width: 220px; }
  .panel-tbl table col.col-solution { width: 30%; min-width: 220px; }
  .panel-tbl table col.col-process { width: auto; }
  .panel-tbl table col.col-name { width: auto; }

  .panel-empty { padding: 30px; text-align: center; color: var(--muted); font-style: italic; font-size: 12px; }

  /* ---------- 顶部提示条 ---------- */
  .tip-bar {
    background: #fffbe6; border-bottom: 1px solid #f5d76e;
    padding: 6px 12px; font-size: 12px; color: #6b5b00;
    display: flex; align-items: center; gap: 8px;
  }
  .tip-bar button {
    background: transparent; border: 1px solid #d4b85a; border-radius: 3px;
    padding: 2px 8px; cursor: pointer; font: inherit; color: inherit;
  }
  .tip-bar button:hover { background: #fff5cc; }
  .tip-bar .close { margin-left: auto; }

  /* ---------- Tab action strip (老工具的下拉菜单风格) ---------- */
  .tab-actions {
    background: #f8f9fb; border-bottom: 1px solid var(--line);
    padding: 6px 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    min-height: 32px;
  }
  .tab-actions .label { font-size: 11px; color: var(--muted); margin-right: 4px; }
  .tab-actions button {
    background: #fff; border: 1px solid var(--line); border-radius: 3px;
    padding: 4px 12px; cursor: pointer; font: inherit; color: var(--fg);
  }
  .tab-actions button:hover { background: var(--row-hover); border-color: #aaa; }
  .tab-actions button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
  .tab-actions button.danger  { background: #fff; color: var(--restricted); border-color: var(--restricted); }
  .tab-actions input.search-box {
    flex: 1; max-width: 360px; padding: 4px 28px 4px 10px;
    border: 1px solid var(--line); border-radius: 3px; font: inherit;
  }
  .tab-actions input.search-box:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
  .search-wrap { position: relative; display: inline-flex; flex: 0 0 auto; max-width: 360px; }
  .search-wrap .search-box { flex: 1; min-width: 200px; }
  .search-clear {
    position: absolute; right: 4px; top: 50%; transform: translateY(-50%);
    background: transparent; border: 0; color: #999; cursor: pointer;
    padding: 2px 6px; font-size: 14px; line-height: 1; display: none;
  }
  .search-clear:hover { color: #c0392b; }
  .search-wrap.has-value .search-clear { display: block; }
  .tab-actions .hint { font-size: 11px; color: var(--muted); margin-left: auto; }

  /* ---------- mycompany 路径条 ---------- */
  .path-bar {
    background: #f4f6f8; border-bottom: 1px solid var(--line);
    padding: 4px 12px; font-size: 11px; color: var(--muted);
    display: flex; align-items: center; gap: 8px;
  }
  .path-bar code {
    font-family: ui-monospace,Consolas,monospace;
    background: #fff; padding: 2px 6px; border: 1px solid var(--line); border-radius: 3px;
    color: var(--fg); user-select: all;
  }
  .path-bar button {
    background: #fff; border: 1px solid var(--line); border-radius: 3px;
    padding: 2px 8px; cursor: pointer; font: inherit; color: var(--fg);
  }
  .path-bar button:hover { background: var(--row-hover); }
  .path-bar button.copied { background: #d4edda; border-color: #19a974; color: #166534; }

  /* ---------- 拖拽高亮 ---------- */
  body.is-dragover::before {
    content: "📂 拖入 JSON 文件即可导入 My Company 选择";
    position: fixed; inset: 0; background: rgba(0,112,192,0.85); color: #fff;
    z-index: 9999; display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 600; pointer-events: none;
  }
</style>
</head>
<body>

<!-- v6.0.11 EXE: 自动备份走内置 HTTP server → 不再有 banner -->
<header>
  <div class="app-title"><span class="ico"></span>My Company GVA Info</div>
  <div class="tabs" id="tabs">
    <!-- v6.0.4 仅保留 Search 和 About；IPE / Portfolio / Restricted Reference Portfolio 已删除 -->
    <button data-tab="search"      class="active">Search</button>
    <button data-tab="about">About</button>
  </div>
  <!-- v6.0.12: Import / Export 已移除 — 数据自动写到 EXE 同目录的 my-company.json -->
  <div class="head-tools">
    <span class="head-count" id="head-count">0 selected</span>
  </div>
</header>

<!-- Tab action strips: 只显示 active tab 对应那个 -->
<div class="tab-actions" data-for-tab="search">
  <span class="label">Search Role:</span>
  <div class="search-wrap">
    <input type="text" class="search-box" id="role-search" placeholder="输入 Role 名搜索">
    <button class="search-clear" id="search-clear" type="button" title="清空检索 (Esc)" aria-label="清空">✕</button>
  </div>
  <span class="hint" id="search-hint">实时高亮匹配 Role；红竖线=已加入公司。先勾行 → 点面板标题栏 ＋/－ 加入或移出</span>
</div>

<div class="tab-actions" data-for-tab="about" style="display:none" style2="padding:8px 12px">
  <!-- v6.0.12：About 极简一行（数据来源 + 统计 + 数据文件位置）-->
  <div style="font-size:12px;line-height:1.5">
    <b>IPE Navigator v__VERSION__</b> · 数据来自 Portfolio Navigator (__DATA_VERSION__) · <span id="about-ipe-count">__ABOUT_IPE__</span> IPE / <span id="about-pf-count">__ABOUT_PF__</span> Portfolio / <span id="about-role-count">__ABOUT_ROLE__</span> Role / <span id="about-ise-count">__ABOUT_ISE__</span> ISE / <span id="about-ip-count">__ABOUT_IP__</span> Industry Portfolio
    <br>
    <span style="color:#666;font-size:11px">数据自动保存到 EXE 同目录的 <code>my-company.json</code></span>
  </div>
</div>

<main>
  <!-- ============ My Company ============ -->
  <section class="row" id="row-my">
    <h2>My Company</h2>
    <div class="grid-3">
      <div class="panel" data-kind="my-ipe">
        <div class="panel-h">
          <span class="panel-act"><button class="minus" data-act="rm-ipe" title="从 My Company 移除勾选的 IPE">－</button></span>
          <h3>My Company IPE List</h3>
        </div>
        <div class="panel-tbl" id="tb-my-ipe" data-axis="ipe"></div>
      </div>
      <div class="panel" data-kind="my-portfolio">
        <div class="panel-h">
          <span class="panel-act"><button class="minus" data-act="rm-pf" title="从 My Company 移除勾选的 Portfolio">－</button></span>
          <h3>My Company Portfolio List</h3>
        </div>
        <div class="panel-tbl" id="tb-my-portfolio" data-axis="portfolio"></div>
      </div>
      <!-- my-role：无 +/− 按钮（用户要求） -->
      <div class="panel" data-kind="my-role">
        <div class="panel-h">
          <h3>My Company Role List</h3>
        </div>
        <div class="panel-tbl" id="tb-my-role" data-axis="role"></div>
      </div>
    </div>
  </section>

  <!-- ============ All Download ============ -->
  <section class="row" id="row-all">
    <h2>All Download</h2>
    <div class="grid-3">
      <div class="panel" data-kind="all-ipe">
        <div class="panel-h">
          <span class="panel-act"><button class="plus" data-act="add-ipe" title="把勾选的 IPE 加入 My Company">＋</button></span>
          <h3>All Download IPE List</h3>
        </div>
        <div class="panel-tbl" id="tb-all-ipe" data-axis="ipe"></div>
      </div>
      <div class="panel" data-kind="all-portfolio">
        <div class="panel-h">
          <span class="panel-act"><button class="plus" data-act="add-pf" title="把勾选的 Portfolio 加入 My Company">＋</button></span>
          <h3>All Download Portfolio List</h3>
        </div>
        <div class="panel-tbl" id="tb-all-portfolio" data-axis="portfolio"></div>
      </div>
      <!-- all-role：无 +/− 按钮（用户要求） -->
      <div class="panel" data-kind="all-role">
        <div class="panel-h">
          <h3>All Download Role List</h3>
        </div>
        <div class="panel-tbl" id="tb-all-role" data-axis="role"></div>
      </div>
    </div>
  </section>
</main>

<!-- v6.0.11 EXE: 加载解析数据。端口 8765 由 main.py 起服务（HTTP server）。 -->
<!-- 普通 zip 模式（直接 file:// 双击）依然走 data/portfolio-r2026x.js — 失败时静默 -->
<script src="data/portfolio-r2026x.js" onerror="console.warn('[IPE] data/portfolio-r2026x.js 加载失败（zip 模式请保持 HTML 与 data 同目录）')"></script>
<!-- v6.0.11 保留：zip 模式（直接 file:// 双击）没有 server，HTML 仍用 <script> 注入 window.MY_COMPANY -->
<!--          EXE 模式下 main.py 写出来的 data/my-company.json 也是 JSONP wrapper，HTML 可直接 script 读取 -->
<script src="data/my-company.json" onerror="/* skip — 可能 EXE 模式无文件或首次运行 */"></script>

<script>
// 1) 数据 — 默认空对象，等上面脚本加载完后赋 PORTFOLIO_DATA
const DATA     = window.PORTFOLIO_DATA || { meta: { title: '(未加载)', week_label: '' }, axes: { ipe: [], portfolios: [], industry_portfolios: [], ise: [] }, items: [] };
const MYIPE    = __MY_IPE_JSON__;
const MYROLE   = __MY_ROLE_JSON__;
const RESTRICT = __RESTRICTED_JSON__;
</script>

<script>
// 2) 应用逻辑
(function () {
  // 数据准备
  const ITEMS = { ipe: [], portfolio: [], role: [] };
  for (const it of (DATA.axes.ipe || []))        ITEMS.ipe.push(it);
  for (const it of (DATA.axes.portfolios || [])) ITEMS.portfolio.push(it);
  for (const it of DATA.items) {
    if (it.axis_origin === 'croles') ITEMS.role.push(it);
  }
  for (const k of ['ipe', 'portfolio', 'role']) {
    ITEMS[k].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  }

  // 全局 id 索引
  const ITEM_INDEX = new Map();
  for (const it of ITEMS.ipe)       ITEM_INDEX.set(it.id, {kind:'ipe',       item:it});
  for (const it of ITEMS.portfolio) ITEM_INDEX.set(it.id, {kind:'portfolio', item:it});
  for (const it of ITEMS.role)      ITEM_INDEX.set(it.id, {kind:'role',      item:it});
  function findKind(id) { const e = ITEM_INDEX.get(id); return e ? e.kind : null; }
  function getItem(id)  { const e = ITEM_INDEX.get(id); return e ? e.item  : null; }

  // Restricted
  const RESTRICT_NAMES = new Set((RESTRICT || []).map(s => (s || '').toLowerCase().trim()));

  // Industry + ISE 映射
  const INDUSTRY_BY_ID = new Map();
  const ISE_BY_ID      = new Map();
  for (const ip of (DATA.axes.industry_portfolios || [])) INDUSTRY_BY_ID.set(ip.id, ip.name);
  for (const ise of (DATA.axes.ise || []))               ISE_BY_ID.set(ise.id, ise.name);
  function stripDot(name) { return (name || '').replace(/^(\d+)\.\s*/, '$1 '); }
  function esc(s)         { return (s || '').replace(/[<>]/g, c => c === '<' ? '&lt;' : '&gt;'); }
  function getIndustryForIpe(it) {
    for (const cid of (it.compat_with || [])) {
      const n = INDUSTRY_BY_ID.get(cid);
      if (n) return stripDot(n);
    }
    return '';
  }
  function getIseForIpe(it) {
    for (const cid of (it.compat_with || [])) {
      const n = ISE_BY_ID.get(cid);
      if (n) return n;
    }
    return '';
  }

  // 初始 SEEDS 为空 (用户要求初始空，加载 JSON 后填充)
  const SEEDS = new Set();

  // v6.0.8: 取消列头点击排序 — 三列 IPE 面板固定按 (industry 数字, ise 字母, ipe 原始序号) 排序
  //   砍掉：COL_SORT / getColSort / setColSort / loadColSort / ipe-v24-sort localStorage / 列头 ▲▼ / 列头 onclick
  //   如果用户浏览器有旧 ipe-v24-sort key，启动时顺手清掉
  try { localStorage.removeItem('ipe-v24-sort'); } catch (_) {}

  // 三元组合排序 key：(industry 数字, ise 字母, ipe 前导数字, ipe 原序号)
  function ipeUnitKey(it) {
    const ind = getIndustryForIpe(it);
    const ise = getIseForIpe(it);
    const indNum = parseInt((ind || '').match(/^(\d+)/)?.[1] || '9999', 10);  // 没数字的排到末尾
    const iseLow = (ise || '').toLowerCase();
    // 第 3 列：ipe 名字通常带 "01-xxx" 这种前导编号 — 提取数字按 IPE 编号递增排，跳号也按数字顺序
    // 用户要求：第三列按"01-XX 数字递增"显示，即使编号本身跳过也无所谓
    const ipeNum = parseInt((it.name || '').match(/^(\d+)/)?.[1] || '9999', 10);
    const idx    = (it._orig_idx != null) ? it._orig_idx : 999999;             // 同数字时按原序兜底
    return [indNum, iseLow, ipeNum, idx];
  }
  function compareTuple(a, b) {
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return  1;
    }
    return a.length - b.length;
  }


  // SEEDS = My Company 真实成员（只有点标题栏 Add 按钮才往里加）
  // DRAFT = 每个 panel 的"草稿"勾选状态（点 checkbox 只动这个，不动 SEEDS）
  // 然后标题栏 Add/Remove 按钮才把 DRAFT 转移到 SEEDS（或从 SEEDS 删除）
  const KIND_PREFIX = { ipe:'i', portfolio:'p', role:'r' };
  function getKey(kind, id) { return KIND_PREFIX[kind] + ':' + id; }
  function isInMyCompany(kind, id) { return SEEDS.has(getKey(kind, id)); }
  // isSelected() 保留兼容旧代码 (返回 SEEDS 状态)
  function isSelected(kind, id) { return isInMyCompany(kind, id); }
  // DRAFT 按 panelKind 分类（all-ipe / all-portfolio / all-role / my-ipe / ...）
  const DRAFT = {
    'all-ipe': new Set(), 'all-portfolio': new Set(), 'all-role': new Set(),
    'my-ipe':  new Set(), 'my-portfolio':  new Set(), 'my-role':  new Set(),
  };
  function isDraft(panelKind, kind, id) { return DRAFT[panelKind]?.has(id) || false; }
  function draftCount(panelKind) { return DRAFT[panelKind]?.size || 0; }
  function clearDraft(panelKind) { if (DRAFT[panelKind]) DRAFT[panelKind].clear(); }
  // 原地同步表头全选 tri-state（不 rerender）
  // v6.0.2 修复：total 只数可点行（cb.disabled === false），避免 all-* panel 含 disabled 行时永远勾不满
  function syncHeadCb(panelKind) {
    const headCb = document.querySelector('#tb-' + panelKind + ' .cb-select-all');
    if (!headCb) return;
    let selectable = 0;
    document.querySelectorAll('#tb-' + panelKind + ' tr[data-id]').forEach(tr => {
      const cb = tr.querySelector('input[type=checkbox]');
      if (cb && !cb.disabled) selectable++;
    });
    const drft  = draftCount(panelKind);
    headCb.checked       = selectable > 0 && drft >= selectable;
    headCb.indeterminate = drft > 0 && drft < selectable;
    headCb.disabled      = selectable === 0;
  }
  // 1-hop compat: 取出"目标 axis"集合（只走 3 主轴）
  function compatInAxes(id, allowedKinds) {
    const item = getItem(id);
    if (!item) return new Set();
    const out = new Set();
    for (const relId of (item.compat_with || [])) {
      const rk = findKind(relId);
      if (allowedKinds.has(rk)) out.add(getKey(rk, relId));
    }
    return out;
  }
  // checkbox 切换：只动 DRAFT
  function onToggle(panelKind, kind, id, checked) {
    if (checked) DRAFT[panelKind]?.add(id);
    else         DRAFT[panelKind]?.delete(id);
    rerenderAll();
  }

  // SEARCH_ROLE_MATCHES = 搜索命中的 Role key 集合（r:id）
  // 输入框改变时实时更新；render 时 Role 行据此加 is-search-match
  // 不做 panel 过滤：让匹配的 Role 在 All Download / My Company 两边同时显示高亮
  let SEARCH_ROLE_MATCHES = new Set();
  function recomputeSearchMatches(q) {
    SEARCH_ROLE_MATCHES = new Set();
    const ql = (q || '').toLowerCase().trim();
    if (!ql) return;
    for (const it of ITEMS.role) {
      if ((it.name || '').toLowerCase().includes(ql) ||
          (it.id   || '').toLowerCase().includes(ql)) {
        SEARCH_ROLE_MATCHES.add(getKey('role', it.id));
      }
    }
  }
  // RELATED = 根据点击方向决定：
  //   点 IPE / Portfolio → 只找 1-hop compat 里的 Role（IPE↔Portfolio 不互相关联）
  //   点 Role             → 找 1-hop compat 里的 IPE + Portfolio（反向）
  // 不做 BFS 闭包（避免拉入 theme/discipline 等元数据轴）
  // 区域互斥：点 My Company 只在 My Company 区联动；点 All Download 只在 All Download 区联动
  let FOCUS = null;     // {area: 'my'|'all', kind, id} | null
  let RELATED = new Set();
  // 方向性：clicked.kind → 允许高亮的 kinds
  const HIGHLIGHT_DIRECTION = {
    ipe:       new Set(['role']),          // 点 IPE → 只高亮 Role
    portfolio: new Set(['role']),          // 点 Portfolio → 只高亮 Role
    role:      new Set(['ipe', 'portfolio'])  // 点 Role → 高亮 IPE + Portfolio
  };
  function setFocus(area, kind, id) {
    // 切换区域 → 释放旧的（FOCUS/RELATED 仅在所属区域生效）
    if (FOCUS && FOCUS.area !== area) {
      FOCUS = null;
      RELATED = new Set();
    }
    // 再次点同一行 → 释放
    if (FOCUS && FOCUS.kind === kind && FOCUS.id === id) {
      FOCUS = null;
      RELATED = new Set();
    } else {
      FOCUS = { area, kind, id };
      RELATED = new Set();
      RELATED.add(getKey(FOCUS.kind, FOCUS.id));
      const allowed = HIGHLIGHT_DIRECTION[FOCUS.kind];
      const item = getItem(FOCUS.id);
      if (item && allowed) {
        for (const relId of (item.compat_with || [])) {
          const rk = findKind(relId);
          if (!allowed.has(rk)) continue;   // 方向性筛选
          RELATED.add(getKey(rk, relId));
        }
      }
    }
    rerenderAll();
  }
  function clearFocus() { if (FOCUS) { FOCUS = null; RELATED = new Set(); rerenderAll(); } }
  // 仅当本行所属 mode 与 FOCUS.area 一致时，才认为"被聚焦/被高亮"
  function isFocused(mode, kind, id)     { return FOCUS && FOCUS.area === mode && FOCUS.kind === kind && FOCUS.id === id; }
  function isHighlighted(mode, kind, id) { return FOCUS && FOCUS.area === mode && RELATED.has(getKey(kind, id)); }
  // v6.0.10.1: 「聚焦相关需前置」按 kind 区分：
  //   - focused 自身（FOCUS.id + 同 kind）→ 永远前置
  //   - 跨 kind 面板（FOCUS 是 IPE/PF，看 Role 面板）：所有关联 Role 全前置，不管 Role 是否已加入
  //   - 同 kind 面板（FOCUS 是 IPE，看 IPE 面板）：已加入的关联行不前置（保留红竖线视觉，按主 key 排）
  function isFocusRelated(mode, kind, id) {
    if (!isHighlighted(mode, kind, id)) return false;
    if (isFocused(mode, kind, id))       return true;
    if (FOCUS.kind !== kind)             return true;   // 跨 kind → 所有关联前置
    return !isSelected(kind, id);                       // 同 kind → 已加入的关联不前置
  }

  // 渲染
  function renderPanel(panelKind) {
    const [mode, kind] = panelKind.split('-');
    const items = ITEMS[kind];
    const container = document.getElementById('tb-' + panelKind);
    if (!container) return;

    let view = items;
    if (mode === 'my') {
      view = items.filter(it => isSelected(kind, it.id));
    }
    // 排序优先级 v6.0.10:
    //   1) search match（仅 Role）         → 置顶
    //   2) focused 关联 & 未加入公司        → 置顶（focused 自身 + 关联未加入的项）
    //   3) 主排序 key：IPE 用 (industry_num, ise_low, ipe_num, orig_idx)；portfolio/role 按 name 字典序
    //
    //   已加入公司（isSelected）的行不再前置 — 红竖线是视觉标记，不参与排序
    //   focused 关联但已加入的行也不前置 — 同理
    //
    // 仅在本 panel 所属区与 FOCUS.area 一致时考虑 focus-related
    view = view.slice().sort((a, b) => {
      const aSrch = (kind === 'role') && SEARCH_ROLE_MATCHES.has(getKey('role', a.id));
      const bSrch = (kind === 'role') && SEARCH_ROLE_MATCHES.has(getKey('role', b.id));
      const aRel  = isFocusRelated(mode, kind, a.id);
      const bRel  = isFocusRelated(mode, kind, b.id);
      if (aSrch !== bSrch) return aSrch ? -1 : 1;
      if (aRel !== bRel) return aRel ? -1 : 1;
      // 主排序
      const cmp = (kind === 'ipe')
        ? compareTuple(ipeUnitKey(a), ipeUnitKey(b))
        : (a.name || '').localeCompare(b.name || '');
      if (cmp !== 0) return cmp;
      // tie-breaker: 按 id
      if (a.id < b.id) return -1;
      if (a.id > b.id) return  1;
      return 0;
    });

    // Search（仅 Role）：高亮匹配项，不过滤 panel
    // 匹配态由全局 SEARCH_ROLE_MATCHES 维护，render 时判断 kind==='role' && key in matches
    // 这样 Role 在 All Download / My Company 两边都同时显示高亮，红竖线提示是否在公司

    if (view.length === 0) {
      container.innerHTML = '<div class="panel-empty">(empty)</div>';
      return;
    }

    const rows = [];
    for (const it of view) {
      const inMc = isInMyCompany(kind, it.id);
      const drft = isDraft(panelKind, kind, it.id);
      const hi   = isHighlighted(mode, kind, it.id);
      const foc  = isFocused(mode, kind, it.id);
      const srch = (kind === 'role') && SEARCH_ROLE_MATCHES.has(getKey('role', it.id));
      const restrict = RESTRICT_NAMES.has((it.name || '').toLowerCase().trim());
      // is-in-mycompany 只在 All Download 区显示（标记"已加入"）
      // My Company 区所有行本来就在公司里，再标红冗余
      const showInMc = (mode === 'all') && inMc;
      const cls = [
        foc       ? 'is-focus' : '',
        showInMc  ? 'is-in-mycompany' : '',
        drft      ? 'is-draft' : '',
        hi        ? 'is-highlighted' : '',
        srch      ? 'is-search-match' : '',
        restrict  ? 'is-restricted' : ''
      ].filter(Boolean).join(' ');
      const nameEsc = esc(it.name || '');
      const idEsc   = esc(it.id || '');
      const cbDisabled = (mode === 'all' && inMc) ? ' disabled' : '';
      const cb = `<td class="cb"><input type="checkbox"${drft ? ' checked' : ''}${cbDisabled}></td>`;

      let cols;
      if (kind === 'ipe') {
        const industry = esc(getIndustryForIpe(it));
        const ise      = esc(getIseForIpe(it));
        cols = cb
             + `<td>${industry}</td>`
             + `<td>${ise}</td>`
             + `<td>${nameEsc}</td>`;
      } else if (kind === 'portfolio') {
        cols = cb + `<td>${nameEsc}</td>`;
      } else {
        cols = cb + `<td>${nameEsc}</td>`;
      }
      rows.push(`<tr data-kind="${kind}" data-id="${idEsc}" class="${cls}">${cols}</tr>`);
    }
    container.innerHTML = '<table>' + theadHTML(kind) + '<tbody>' + rows.join('') + '</tbody></table>';
    // v6.0.8 取消列头点击排序 — render 中改用组合 key 默认序，无需列头交互

    // 如果本 panel 有高亮项或搜索命中项，滚动到最上面（让用户立即看到）
    // 高亮：仅在本 panel 所属区与 FOCUS.area 一致时滚动
    // 搜索：仅 Role panel
    const hasHigh = (FOCUS && FOCUS.area === mode) &&
                    view.some(it => isHighlighted(mode, kind, it.id));
    const hasSrch = (kind === 'role') && SEARCH_ROLE_MATCHES.size > 0 &&
                    view.some(it => SEARCH_ROLE_MATCHES.has(getKey('role', it.id)));
    if (hasHigh || hasSrch) container.scrollTop = 0;

    // 直接给每个 checkbox 绑 onchange / onclick
    // 关键：onchange 处理器只更新 DRAFT + 原地改 CSS class，**不调 rerenderAll**
    // 避免 innerHTML 替换导致 checkbox 状态丢失/闪烁
    for (const tr of container.querySelectorAll('tr[data-id]')) {
      const kind = tr.getAttribute('data-kind');
      const id   = tr.getAttribute('data-id');
      const cb   = tr.querySelector('input[type=checkbox]');
      cb.onchange = () => {
        // 走 draft 工作流（v6.0.3 恢复）：点 checkbox 加入 draft，标题栏 +/– 按钮再 commit
        if (cb.checked) DRAFT[panelKey_of(panelKind)].add(id);
        else            DRAFT[panelKey_of(panelKind)].delete(id);
        // 原地更新视觉（不 rerender）
        tr.classList.toggle('is-draft', cb.checked);
        // 同步表头全选 tri-state + panel-h +/- 按钮 disabled
        syncHeadCb(panelKind);
        syncPanelActBtns();
        autosave();
      };
      tr.onclick = e => {
        if (e.target.tagName === 'INPUT') return;  // checkbox 自己处理
        setFocus(mode, kind, id);                   // mode = 'my' | 'all'，区域互斥
      };
    }
    // 表头全选：直接绑 onclick
    // v6.0.3 恢复走 draft 工作流：headCb 全选/取消 → 加进 draft，标题栏 +/– 按钮再 commit
    const headCb = container.querySelector('.cb-select-all');
    if (headCb) {
      headCb.onclick = () => {
        const draft = DRAFT[panelKey_of(panelKind)];
        // 只数可点行（v6.0.2 修复：避免含 disabled 的 panel 永远勾不满）
        let selectable = 0;
        for (const tr2 of container.querySelectorAll('tr[data-id]')) {
          const cb2 = tr2.querySelector('input[type=checkbox]');
          if (cb2 && !cb2.disabled) selectable++;
        }
        const isAllChecked = draft && selectable > 0 && draft.size >= selectable;
        if (!isAllChecked) {
          for (const tr2 of container.querySelectorAll('tr[data-id]')) {
            const cb2 = tr2.querySelector('input[type=checkbox]');
            if (cb2 && !cb2.disabled) {
              cb2.checked = true;
              draft.add(tr2.getAttribute('data-id'));
              tr2.classList.add('is-draft');
            }
          }
        } else {
          for (const tr2 of container.querySelectorAll('tr[data-id]')) {
            const cb2 = tr2.querySelector('input[type=checkbox]');
            if (cb2 && !cb2.disabled) {
              cb2.checked = false;
              tr2.classList.remove('is-draft');
            }
          }
          draft.clear();
        }
        syncHeadCb(panelKey_of(panelKind));
        syncPanelActBtns();
        autosave();
      };
    }
  }

  function theadHTML(kind) {
    // v6.0.8 简化：取消 ▲▼ 排序按钮，列头只是文字标签
    const selAll = '<input type="checkbox" class="cb-select-all" title="全选/取消全选本 panel 可见行">';
    if (kind === 'ipe') {
      return '<colgroup><col class="col-cb"><col class="col-portfolio"><col class="col-solution"><col class="col-process"></colgroup>'
           + '<thead><tr>'
           + '<th class="cb">' + selAll + '</th>'
           + '<th>Industry Portfolio</th>'
           + '<th>Industry Solution Experience</th>'
           + '<th>Industry Process Experience</th>'
           + '</tr></thead>';
    }
    return '<colgroup><col class="col-cb"><col class="col-name"></colgroup>'
         + '<thead><tr>'
         + '<th class="cb">' + selAll + '</th>'
         + (kind === 'portfolio' ? '<th>Portfolio Name</th>' : '<th>Role Item Id</th>')
         + '</tr></thead>';
  }

  function rerenderAll() {
    for (const k of ['my-ipe','my-portfolio','my-role','all-ipe','all-portfolio','all-role']) {
      renderPanel(k);
    }
    syncPanelActBtns();
    updateHeadCount();
    autosave();
  }
  // v6.0.3 恢复：panel-h 上 +/– 按钮的 disabled 联动（仅 IPE / Portfolio 有，Role 无按钮所以 no-op）
  function syncPanelActBtns() {
    const kindKey = { 'add-ipe': 'all-ipe', 'rm-ipe': 'my-ipe',
                      'add-pf':  'all-portfolio', 'rm-pf':  'my-portfolio' };
    for (const btn of document.querySelectorAll('button[data-act^="add-"], button[data-act^="rm-"]')) {
      const panelKind = kindKey[btn.getAttribute('data-act')];
      if (!panelKind) continue;
      btn.disabled = (DRAFT[panelKind]?.size || 0) === 0;
    }
  }
  function updateHeadCount() {
    const el = document.getElementById('head-count');
    if (!el) return;
    let s = SEEDS.size + ' selected';
    if (FOCUS) {
      const fname = getItem(FOCUS.id)?.name || FOCUS.id;
      s += ' · focused: ' + fname + ' (' + RELATED.size + ' highlighted)';
    }
    el.textContent = s;
  }
  // 自动保存到 localStorage（每次 toggle）
  function autosave() {
    try { localStorage.setItem('ipe-v24-snap', JSON.stringify({ts: Date.now(), seeds: [...SEEDS]})); } catch (e) {}
  }
  // 启动时尝试恢复 — localStorage 优先（快），data/my-company.json 兜底（防清缓存）
  function autoload() {
    // 1. 优先 localStorage（快，但可能清缓存丢失）
    let lsSeeds = null;
    try {
      const txt = localStorage.getItem('ipe-v24-snap');
      if (txt) {
        const obj = JSON.parse(txt);
        lsSeeds = (obj.seeds || []);
      }
    } catch (e) {}
    if (lsSeeds !== null) {
      for (const k of lsSeeds) SEEDS.add(k);
      return;
    }
    // 2. localStorage 空 → 试 data/my-company.json（来自 <script> 注入的 window.MY_COMPANY）
    try {
      if (window.MY_COMPANY && Array.isArray(window.MY_COMPANY.seeds)) {
        for (const k of window.MY_COMPANY.seeds) SEEDS.add(k);
        // 回填 localStorage，下次打开直接命中 localStorage
        autosave();
      }
    } catch (e) {}
  }
  // v6.0.8 列头排序已删除（无需 loadColSort）

  // v6.0.12: Import / Export / showToast / btn-clear / btn-show-all / setupDragDrop 全部已删除


  // Esc 优先级：先清搜索 → 再清 FOCUS
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (searchInput.value || document.activeElement === searchInput) {
      if (searchInput.value) clearSearch();
      else searchInput.blur();
    } else if (FOCUS) {
      clearFocus();
    }
  });
  // 点击空白（main 区域空白处）也释放 FOCUS
  document.querySelector('main').addEventListener('click', e => {
    if (e.target.tagName === 'MAIN' || e.target.classList.contains('panel-empty')) {
      if (FOCUS) setFocus(FOCUS.kind, FOCUS.id);
    }
  });

  // tabs 切换 → 显示对应 action strip
  document.getElementById('tabs').addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') return;
    for (const b of e.target.parentElement.querySelectorAll('button')) b.classList.remove('active');
    e.target.classList.add('active');
    const tab = e.target.dataset.tab;
    // 隐藏所有 tab-action strip
    for (const s of document.querySelectorAll('.tab-actions')) s.style.display = 'none';
    const target = document.querySelector(`.tab-actions[data-for-tab="${tab}"]`);
    if (target) target.style.display = '';
    // 滚动定位
    if (tab === 'ipe' || tab === 'portfolio' || tab === 'search') {
      document.getElementById('row-all').scrollIntoView({block:'start'});
    }
    if (tab === 'restricted') {
      // 滚到第一个标红行
      for (const tr of document.querySelectorAll('.panel-tbl tr.is-restricted')) {
        tr.scrollIntoView({block:'center'}); break;
      }
    }
  });

  // ---- Search tab: 实时高亮匹配 Role（不过滤 panel）----
  const searchInput = document.getElementById('role-search');
  const searchClear = document.getElementById('search-clear');
  const searchWrap  = searchInput.parentElement;   // .search-wrap
  function syncSearchClear() {
    searchWrap.classList.toggle('has-value', !!searchInput.value.trim());
  }
  function clearSearch() {
    if (!searchInput.value) return;
    searchInput.value = '';
    recomputeSearchMatches('');
    syncSearchClear();
    rerenderAll();
    searchInput.focus();
  }
  syncSearchClear();   // 初始（可能从 localStorage/autoload 恢复值）
  searchInput.addEventListener('input', e => {
    recomputeSearchMatches(e.target.value);
    syncSearchClear();
    rerenderAll();
  });
  searchClear.addEventListener('click', clearSearch);

  // ---- panel-h 内嵌 +/- 按钮（仅 IPE / Portfolio；Role 区无按钮） ----
  for (const btn of document.querySelectorAll('button[data-act^="add-"], button[data-act^="rm-"]')) {
    const act = btn.getAttribute('data-act');          // 'add-ipe' / 'add-pf' / 'rm-ipe' / 'rm-pf'
    const m = act.match(/^(add|rm)-(ipe|pf)$/);
    if (!m) continue;
    const mode = m[1] === 'add' ? 'add' : 'rm';
    const kind = m[2] === 'pf' ? 'portfolio' : 'ipe';
    btn.addEventListener('click', () => bulkToggle(kind, mode));
  }

  // v6.0.4 Restricted Reference Portfolio tab 已删除（act-mark-pf / bulkMark 等不再用）

  // panelKind (e.g. 'all-ipe') → DRAFT key (same string in our case)
  function panelKey_of(panelKind) { return panelKind; }

  // Add/Remove Selected IPE/Portfolio（v6.0.3 恢复；Role 区无按钮）
  //  + Add:  把 DRAFT[all-{kind}] 的项目 + 1-hop compat Role 加入 SEEDS
  //  - Rm:   把 DRAFT[my-{kind}] 的项目 + 1-hop compat Role 从 SEEDS 删除
  function bulkToggle(kind, mode) {
    const panelKey = mode === 'add' ? `all-${kind}` : `my-${kind}`;
    const container = document.getElementById('tb-' + panelKey);
    if (!container) return;
    const draft = DRAFT[panelKey];
    if (!draft || draft.size === 0) {
      alert('没有勾选的行 — 先在 ' + panelKey + ' 里勾选几行');
      return;
    }
    let nAdded = 0, nRoleAdded = 0, nRemoved = 0, nRoleRemoved = 0;
    if (mode === 'add') {
      const allowed = (kind === 'role') ? new Set() : new Set(['role']);
      for (const id of [...draft]) {
        const k = getKey(kind, id);
        if (!SEEDS.has(k)) { SEEDS.add(k); nAdded++; }
        for (const rk of compatInAxes(id, allowed)) {
          if (!SEEDS.has(rk)) { SEEDS.add(rk); nRoleAdded++; }
        }
      }
      console.log(`[+ Add Selected ${kind}] ${nAdded} ${kind} + ${nRoleAdded} role(s)`);
    } else {
      const allowed = (kind === 'role') ? new Set() : new Set(['role']);
      for (const id of [...draft]) {
        const k = getKey(kind, id);
        if (SEEDS.has(k)) { SEEDS.delete(k); nRemoved++; }
        for (const rk of compatInAxes(id, allowed)) {
          if (SEEDS.has(rk)) { SEEDS.delete(rk); nRoleRemoved++; }
        }
      }
      console.log(`[- Rm Selected ${kind}] ${nRemoved} ${kind} + ${nRoleRemoved} role(s)`);
    }
    draft.clear();
    rerenderAll();
  }

  // v6.0.4 bulkMark 已删除（Restricted Reference Portfolio tab 一并删除）

  // 把 search 过滤应用到 renderPanel（已经有 input 监听）

  // ======== v6.0.11 EXE: 内置 HTTP server 自动备份 ========
  // v6.0.5 的 File System Access API 整段已删除（FS_HANDLE / FS_DEBOUNCE / IndexedDB / banner / _setStatus...）
  // 现在的自动备份走 main.py 的 /api/load 和 /api/save：
  //   - 启动时 fetch('/api/load') 拿服务端 SEEDS，跟 localStorage 合并
  //   - autosave 时 fetch POST '/api/save'，由 main.py 写 <EXE 同目录>/data/my-company.json
  //   - 不再有 banner，不需要 user gesture，不怕清缓存
  function _exportObj() {
    const seeds = [...SEEDS];
    return {
      ts: new Date().toISOString(),
      seeds,
      my_ipe:        seeds.filter(k => k[0]==='i').map(k => ({id: k.slice(2)})),
      my_portfolios: seeds.filter(k => k[0]==='p').map(k => ({id: k.slice(2)})),
      my_role:       seeds.filter(k => k[0]==='r').map(k => ({id: k.slice(2)})),
    };
  }

  // 启动时尝试从服务器拉 — 如果数据存在，跟 localStorage 合并（保留本地未同步的项）
  (async () => {
    try {
      const resp = await fetch('/api/load');
      if (!resp.ok) return;
      const j = await resp.json();
      if (!j.ok || !j.data || !j.data.seeds) return;
      let n = 0;
      for (const k of j.data.seeds) {
        if (!SEEDS.has(k)) { SEEDS.add(k); n++; }
      }
      if (n > 0) {
        rerenderAll();
        autosave();   // 把来自服务端的 seeds 同步写回 localStorage
        console.log('[EXE back] 从服务器恢复', n, '项');
      }
    } catch (e) {
      // 网络错误 — 在普通 zip 模式打开时（不是 EXE）也会抛错，可忽略
      console.log('[EXE back] 服务端不可达，正常 zip 模式跳过');
    }
  })();

  // 给 autosave 套个壳：1.5 秒防抖后调用 /api/save
  const _origAutosave = autosave;
  let _saveDebounce = null;
  const _SAVE_DEBOUNCE_MS = 1500;
  autosave = function() {
    _origAutosave();
    clearTimeout(_saveDebounce);
    _saveDebounce = setTimeout(async () => {
      try {
        const obj = _exportObj();
        const body = JSON.stringify(obj).replace(/<\/script>/gi, '<\\/script>');
        const resp = await fetch('/api/save', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body
        });
        if (resp.ok) {
          const j = await resp.json();
          console.log('[EXE back] 已写', obj.seeds.length, '项 →', j.saved || '');
        }
      } catch (e) {
        console.log('[EXE back] save failed:', e);
      }
    }, _SAVE_DEBOUNCE_MS);
  };

  // ============ 启动 ============
  autoload();
  rerenderAll();

  // v6.0.12: 拖拽导入已删除（数据走 EXE 同目录自动保存，不需要手动导入）

  // 全局调试
  window.IPE = { DATA, ITEMS, SEEDS, RELATED };
  console.log('[IPE v2.9]',
    ITEMS.ipe.length, 'IPE,',
    ITEMS.portfolio.length, 'Portfolio,',
    ITEMS.role.length, 'Role;',
    'selected:', SEEDS.size, 'compat:', RELATED.size - SEEDS.size);
  // v6.0: 标记 JS 启动成功（便于排查）
  document.documentElement.setAttribute('data-js-ran', '1');
  document.documentElement.removeAttribute('data-js-pending');
})();
try { } catch (e) {}
// 全局错误捕获（不影响主流程）
window.addEventListener('error', e => {
  console.error('[IPE v2.9 runtime error]', e.message, '@', e.filename, ':', e.lineno);
  document.documentElement.setAttribute('data-js-error', String(e.message || e));
});
</script>

</body>
</html>
"""

# ---------------------------------------------------------------------------
# 数据准备
# ---------------------------------------------------------------------------
def load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[ERR] file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def split_company(company: dict) -> tuple[list, list, list]:
    return (
        company.get("my_ipe", []) or [],
        company.get("my_role", []) or [],
        company.get("restricted_reference", []) or [],
    )


def _slim_source(source: dict) -> dict:
    """v6.0+ 输出：
       - croles 只保留 children（短 trigram），跳过 parents（长名字）
       - IPE / Portfolio / ISE / Industry Portfolio 全部按 GA 过滤
    """
    FOCUS_AXES = ("ipe", "portfolios", "industry_portfolios", "ise")
    FOCUS_ORIGINS = ("ipe", "portfolio", "portfolio_releases", "croles")

    items_by_id = {it["id"]: it for it in source["items"] if it.get("id")}

    # 1) 找出 role_availability 里的 GA / CA id
    ra_axis = source["axes"].get("role_availability", [])
    ga_ids = {r["id"] for r in ra_axis if (r.get("name") or "").upper() == "GA"}

    # 2) 过滤 axes — 按 GA 过滤 IPE/Portfolio/ISE/Industry Portfolio
    def _ga_kept(it):
        cw = set(it.get("compat_with") or [])
        return bool(cw & ga_ids)

    slim_axes = {
        "ipe":                 [it for it in source["axes"].get("ipe", []) if _ga_kept(it)],
        "portfolios":          [it for it in source["axes"].get("portfolios", []) if _ga_kept(it)],
        "industry_portfolios": [it for it in source["axes"].get("industry_portfolios", []) if _ga_kept(it)],
        "ise":                 [it for it in source["axes"].get("ise", []) if _ga_kept(it)],
    }

    # 3) 收集 focus ids:
    #    - axes 里的 id（已 GA 过滤）
    #    - items 里 axis_origin=ipe/portfolio/portfolio_releases（已 GA 过滤）
    #    - items 里 axis_origin=croles 且 id != croline_group 的 children
    focus_ids = set()
    for ax in FOCUS_AXES:
        for it in slim_axes[ax]:
            if it.get("id"):
                focus_ids.add(it["id"])
    for it in source["axes"].get("portfolio_releases", []):
        if it.get("id"):
            focus_ids.add(it["id"])
    for it in source["items"]:
        if not it.get("id"):
            continue
        ao = it.get("axis_origin")
        if ao in ("ipe", "portfolio", "portfolio_releases"):
            if _ga_kept(it):
                focus_ids.add(it["id"])
        elif ao == "croles":
            # 只收 croles children（跳过 parents 长名字）
            if not it.get("croline_group") or it["id"] != it["croline_group"]:
                focus_ids.add(it["id"])

    # 4) 生成 slim items：跳过 parents 长名字，保留互引 compat
    slim_items = []
    for iid in focus_ids:
        it = items_by_id.get(iid)
        if not it:
            continue
        if it.get("axis_origin") == "croles":
            if it.get("croline_group") and it["id"] == it["croline_group"]:
                continue
        slim_items.append({
            "id":           iid,
            "name":         it.get("name") or "",
            "axis_origin":  it.get("axis_origin") or "",
            "compat_with":  [c for c in (it.get("compat_with") or []) if c in focus_ids],
            "hooks":        it.get("hooks") or {},
            # v6.0.8: 保留原始出现顺序，用于 IPE 三元组合 key 的最末 tie-breaker
            "_orig_idx":    len(slim_items),
        })

    return {
        "meta":     source["meta"],
        "axes":     slim_axes,
        "items":    slim_items,
        "prereqs":  [],
    }


def _attach_company(slim: dict, company: dict) -> dict:
    out = dict(slim)
    out["_my_portfolios"] = company.get("portfolios", []) or []
    out["_my_ipe"]        = company.get("my_ipe", []) or []
    out["_my_role"]       = company.get("my_role", []) or []
    return out


def build_html(source: dict, company: dict | None) -> str:
    if not company:
        company = {"company": "", "portfolios": [], "my_ipe": [],
                   "my_role": [], "restricted_reference": [], "notes": ""}
    my_ipe, my_role, restricted = split_company(company)
    week = source["meta"].get("week_label", "?")
    title = source["meta"].get("title", "")
    company_name = company.get("company", "")

    slim = _slim_source(source)
    full = _attach_company(slim, company)

    data_json = json.dumps(full, ensure_ascii=False).replace("</script>", "<\\/script>")
    my_ipe_json  = json.dumps(my_ipe, ensure_ascii=False).replace("</script>", "<\\/script>")
    my_role_json = json.dumps(my_role, ensure_ascii=False).replace("</script>", "<\\/script>")
    rest_json    = json.dumps(restricted, ensure_ascii=False).replace("</script>", "<\\/script>")

    page = (HTML_TEMPLATE
            .replace("__COMPANY__",  html_mod.escape(company_name) if company_name else "(no company)")
            .replace("__WEEK__",     html_mod.escape(f"{week} · {title}"))
            .replace("__DATA_JSON__",       data_json)
            .replace("__MY_IPE_JSON__",     my_ipe_json)
            .replace("__MY_ROLE_JSON__",    my_role_json)
            .replace("__RESTRICTED_JSON__", rest_json)
            # v6.0: 动态 About 计数（不再写死）
            .replace("__VERSION__",    "6.0.12")
            .replace("__ABOUT_IPE__",  str(len(slim["axes"].get("ipe", []))))
            .replace("__ABOUT_PF__",   str(len(slim["axes"].get("portfolios", []))))
            .replace("__ABOUT_ISE__",  str(len(slim["axes"].get("ise", []))))
            .replace("__ABOUT_IP__",   str(len(slim["axes"].get("industry_portfolios", []))))
            .replace("__ABOUT_ROLE__", str(sum(1 for it in slim["items"] if it.get("axis_origin") == "croles"))))
    return page


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="生成 MyCompanyInfo_V{VER}.html (6 panel 统一数据源)")
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--company", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    source = load_json(args.source)
    company = load_json(args.company) if args.company else None
    if company is None:
        company = {"company": "", "portfolios": [], "my_ipe": [],
                   "my_role": [], "restricted_reference": [], "notes": ""}
    slim = _slim_source(source)
    html_str = build_html(source, company)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_str, encoding="utf-8")

    print(f"[OK] v2.9 interactive HTML -> {args.out}")
    print(f"     size:           {len(html_str):,} chars")
    print(f"     slim items:     {len(slim['items']):,}")
    print(f"     slim IPE axis:  {len(slim['axes']['ipe']):,}")
    print(f"     slim Portfolio: {len(slim['axes']['portfolios']):,}")
    print(f"     company:        {company.get('company','')!r}")
    print(f"     portfolios:     {len(company.get('portfolios',[]))}")
    print(f"     my_ipe:         {len(company.get('my_ipe',[]))}")
    print(f"     my_role:        {len(company.get('my_role',[]))}")
    print(f"     restricted:     {len(company.get('restricted_reference',[]))}")
    print(f"     open in browser (Ctrl+Shift+R for fresh load)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
