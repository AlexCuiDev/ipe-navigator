"""
v6.0+ 改动：给 IPE/Portfolio/Role 表格加列头排序
- IPE 三列（industry / ise / name）可点排序
- Portfolio/Role Name 列也可点
- 单击切换 asc/desc；切换列时默认 asc；列按 alt/空 name 排最后
- 排序状态存 localStorage（key: ipe-v24-sort）
- 在原本 search>highlight>selected 优先级之后插入 sort 比较
"""
import os

PATH = r'D:\.0WORK\GiteeCode\dne-code\IPE\tools\ipe-stats\build_ui.py'
src = open(PATH, encoding='utf-8').read()

# ---------------------------------------------------------------------
# 1) 加 COL_SORT 全局 state + 持久化（在 SEEDS 后面）
# ---------------------------------------------------------------------
OLD_SEEDS = '''  const SEEDS = new Set();'''
NEW_SEEDS = '''  const SEEDS = new Set();

  // v6.0+ 列头排序状态
  //   key: panelKind (如 'all-ipe' / 'my-portfolio')
  //   value: { col: 'industry'|'ise'|'name', dir: 'asc'|'desc' }
  const COL_SORT = new Map();
  function getColSort(panelKind) {
    return COL_SORT.get(panelKind) || {col: 'name', dir: 'asc'};
  }
  function setColSort(panelKind, col, dir) {
    COL_SORT.set(panelKind, {col, dir});
    try { localStorage.setItem('ipe-v24-sort',
      JSON.stringify({ts: Date.now(), sorts: Object.fromEntries(COL_SORT)})); } catch (e) {}
  }
  function loadColSort() {
    try {
      const txt = localStorage.getItem('ipe-v24-sort');
      if (!txt) return;
      const obj = JSON.parse(txt);
      const sorts = obj.sorts || {};
      for (const k of Object.keys(sorts)) COL_SORT.set(k, sorts[k]);
    } catch (e) {}
  }
  // 取 item 的 sort key（用于 build-sort comparator）
  function sortKeyOf(kind, col, it) {
    if (col === 'industry') return (kind === 'ipe') ? getIndustryForIpe(it) : '';
    if (col === 'ise')      return (kind === 'ipe') ? getIseForIpe(it)      : '';
    return it.name || '';
  }
'''

if OLD_SEEDS not in src:
    print('OLD_SEEDS 找不到')
    raise SystemExit(1)
src = src.replace(OLD_SEEDS, NEW_SEEDS, 1)

# ---------------------------------------------------------------------
# 2) loadColSort() 在 autoload 后调
# ---------------------------------------------------------------------
OLD_AUTOLOAD = '''  function autoload() {
    try {
      const txt = localStorage.getItem('ipe-v24-snap');
      if (!txt) return;
      const obj = JSON.parse(txt);
      for (const k of (obj.seeds || [])) SEEDS.add(k);
    } catch (e) {}
  }'''
NEW_AUTOLOAD = '''  function autoload() {
    try {
      const txt = localStorage.getItem('ipe-v24-snap');
      if (!txt) return;
      const obj = JSON.parse(txt);
      for (const k of (obj.seeds || [])) SEEDS.add(k);
    } catch (e) {}
  }
  // v6.0+ 列头排序持久化（紧随 SEEDS autoload）
  loadColSort();'''
if OLD_AUTOLOAD not in src:
    print('OLD_AUTOLOAD 找不到')
    raise SystemExit(1)
src = src.replace(OLD_AUTOLOAD, NEW_AUTOLOAD, 1)

# ---------------------------------------------------------------------
# 3) theadHTML 加点击 + 排序指示
# ---------------------------------------------------------------------
OLD_THEAD = '''  function theadHTML(kind) {
    // 表头第一列 .cb 加全选 checkbox
    const selAll = \'<input type="checkbox" class="cb-select-all" title="全选/取消全选本 panel 可见行">\';
    if (kind === \'ipe\') {
      return \'<colgroup><col class="col-cb"><col class="col-portfolio"><col class="col-solution"><col class="col-process"></colgroup>\'
           + \'<thead><tr>\'
           + \'<th class="cb">\' + selAll + \'</th>\'
           + \'<th>Industry Portfolio</th>\'
           + \'<th>Industry Solution Experience</th>\'
           + \'<th>Industry Process Experience</th>\'
           + \'</tr></thead>\';
    }
    return \'<colgroup><col class="col-cb"><col class="col-name"></colgroup>\'
         + \'<thead><tr>\'
         + \'<th class="cb">\' + selAll + \'</th>\'
         + (kind === \'portfolio\' ? \'<th>Portfolio Name</th>\' : \'<th>Role Item Id</th>\')
         + \'</tr></thead>\';
  }'''

NEW_THEAD = '''  function theadHTML(kind, panelKind) {
    // panelKind 用于读取 sort 状态
    const ps  = (panelKind && getColSort(panelKind)) || {col: 'name', dir: 'asc'};
    const indicator = (col) => {
      if (ps.col !== col) return \'<span class="sort-ind"></span>\';
      return ps.dir === \'asc\'
        ? \'<span class="sort-ind asc">▲</span>\'
        : \'<span class="sort-ind desc">▼</span>\';
    };
    const sortable = (col, label) =>
      `<th class="th-sortable" data-col="${col}" title="点击按此列排序">${label}${indicator(col)}</th>`;
    const selAll = \'<input type="checkbox" class="cb-select-all" title="全选/取消全选本 panel 可见行">\';
    if (kind === \'ipe\') {
      return \'<colgroup><col class="col-cb"><col class="col-portfolio"><col class="col-solution"><col class="col-process"></colgroup>\'
           + \'<thead><tr>\'
           + \'<th class="cb">\' + selAll + \'</th>\'
           + sortable(\'industry\', \'Industry Portfolio\')
           + sortable(\'ise\',      \'Industry Solution Experience\')
           + sortable(\'name\',     \'Industry Process Experience\')
           + \'</tr></thead>\';
    }
    return \'<colgroup><col class="col-cb"><col class="col-name"></colgroup>\'
         + \'<thead><tr>\'
         + \'<th class="cb">\' + selAll + \'</th>\'
         + sortable(\'name\', kind === \'portfolio\' ? \'Portfolio Name\' : \'Role Item Id\')
         + \'</tr></thead>\';
  }'''
if OLD_THEAD not in src:
    print('OLD_THEAD 找不到')
    raise SystemExit(1)
src = src.replace(OLD_THEAD, NEW_THEAD, 1)

# ---------------------------------------------------------------------
# 4) renderPanel 应用 sort + bind click on sortable th
# ---------------------------------------------------------------------
OLD_SORT_BLOCK = '''    view = view.slice().sort((a, b) => {
      const aH = isHighlighted(mode, kind, a.id), bH = isHighlighted(mode, kind, b.id);
      const aS = isSelected(kind, a.id),         bS = isSelected(kind, b.id);
      const aSrch = (kind === \'role\') && SEARCH_ROLE_MATCHES.has(getKey(\'role\', a.id));
      const bSrch = (kind === \'role\') && SEARCH_ROLE_MATCHES.has(getKey(\'role\', b.id));
      if (aSrch !== bSrch) return aSrch ? -1 : 1;
      if (aH !== bH) return aH ? -1 : 1;
      if (aS !== bS) return aS ? -1 : 1;
      return (a.name || \'\').localeCompare(b.name || \'\');
    });'''

NEW_SORT_BLOCK = '''    // 排序优先级：search match > highlight > selected > COL_SORT > fallback (按 name)
    const ps = getColSort(panelKind);
    const dirMul = ps.dir === \'desc\' ? -1 : 1;
    view = view.slice().sort((a, b) => {
      const aH = isHighlighted(mode, kind, a.id), bH = isHighlighted(mode, kind, b.id);
      const aS = isSelected(kind, a.id),         bS = isSelected(kind, b.id);
      const aSrch = (kind === \'role\') && SEARCH_ROLE_MATCHES.has(getKey(\'role\', a.id));
      const bSrch = (kind === \'role\') && SEARCH_ROLE_MATCHES.has(getKey(\'role\', b.id));
      if (aSrch !== bSrch) return aSrch ? -1 : 1;
      if (aH !== bH) return aH ? -1 : 1;
      if (aS !== bS) return aS ? -1 : 1;
      // 按 COL_SORT
      const ka = sortKeyOf(kind, ps.col, a);
      const kb = sortKeyOf(kind, ps.col, b);
      const cmp = (ka || \'\').localeCompare(kb || \'\');
      if (cmp !== 0) return cmp * dirMul;
      // tie-breaker: 按 name 字母序
      return (a.name || \'\').localeCompare(b.name || \'\');
    });'''
if OLD_SORT_BLOCK not in src:
    print('OLD_SORT_BLOCK 找不到')
    raise SystemExit(1)
src = src.replace(OLD_SORT_BLOCK, NEW_SORT_BLOCK, 1)

# ---------------------------------------------------------------------
# 5) container.innerHTML = theadHTML(kind) → theadHTML(kind, panelKind)
# ---------------------------------------------------------------------
OLD_INNER = '''container.innerHTML = \'<table>\' + theadHTML(kind) + \'<tbody>\' + rows.join(\'\') + \'</tbody></table>\';'''
NEW_INNER = '''container.innerHTML = \'<table>\' + theadHTML(kind, panelKind) + \'<tbody>\' + rows.join(\'\') + \'</tbody></table>\';
    // 表头排序列 onclick：点击切换 asc/desc；同列切换、不同列重置为 asc
    for (const th of container.querySelectorAll(\'th.th-sortable\')) {
      th.onclick = e => {
        // 点排序图标不冒泡（避免双触发）；点文本触发同样逻辑
        const col = th.getAttribute(\'data-col\');
        const cur = getColSort(panelKind);
        let dir = \'asc\';
        if (cur.col === col) dir = (cur.dir === \'asc\') ? \'desc\' : \'asc\';
        setColSort(panelKind, col, dir);
        rerenderAll();
      };
    }'''
if OLD_INNER not in src:
    print('OLD_INNER 找不到')
    raise SystemExit(1)
src = src.replace(OLD_INNER, NEW_INNER, 1)

# ---------------------------------------------------------------------
# 6) CSS: 加 th-sortable 样式 + sort-ind
# ---------------------------------------------------------------------
OLD_CSS = '''  .panel-tbl td.cb, .panel-tbl th.cb { width: 24px; padding: 2px 4px; text-align: center; }'''
NEW_CSS = '''  .panel-tbl td.cb, .panel-tbl th.cb { width: 24px; padding: 2px 4px; text-align: center; }
  /* v6.0+ 表头排序：可点列头 + 排序指示 */
  .panel-tbl th.th-sortable {
    cursor: pointer; user-select: none;
    transition: background-color 0.1s;
  }
  .panel-tbl th.th-sortable:hover { background: #cfd2d5; }
  .panel-tbl th.th-sortable .sort-ind {
    display: inline-block; margin-left: 4px; font-size: 9px;
    color: #888; opacity: 0; transition: opacity 0.1s;
  }
  .panel-tbl th.th-sortable:hover .sort-ind { opacity: 0.5; }
  .panel-tbl th.th-sortable .sort-ind.asc,
  .panel-tbl th.th-sortable .sort-ind.desc {
    color: var(--accent); opacity: 1; font-weight: 700;
  }'''
if OLD_CSS not in src:
    print('OLD_CSS 找不到')
    raise SystemExit(1)
src = src.replace(OLD_CSS, NEW_CSS, 1)

open(PATH, 'w', encoding='utf-8').write(src)
print(f'[OK] patched, new size {len(src)}')
