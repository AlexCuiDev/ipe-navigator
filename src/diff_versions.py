"""
diff_versions.py — 比较两份 Portfolio Navigator JSON 的差异

用法：
    python diff_versions.py <old.json> <new.json>

输出：
    - 控制台摘要（哪些 axes 新增 / 删除）
    - 控制台详细（新增 item、删除 item、改名 item、compat 变化 item）
    - HTML diff 报告（默认写 out/diff_old_vs_new.html）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from jinja2 import Template


# ---------------------------------------------------------------------------
# 比较
# ---------------------------------------------------------------------------
def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_id(source: dict) -> dict[str, dict]:
    return {it["id"]: it for it in source["items"] if it.get("id")}


def diff(old: dict, new: dict) -> dict:
    """
    diff 结果结构：
    {
      "old_meta": ..., "new_meta": ...,
      "axis_changes": { "<axis>": {"old": n, "new": m, "delta": m-n}, ... },
      "added_ids":   [ {"id":, "name":, "axis":}, ... ],
      "removed_ids": [ {"id":, "name":, "axis":}, ... ],
      "renamed_ids": [ {"id":, "old_name":, "new_name":, "axis":}, ... ],
      "compat_changes": [ {"id":, "axis":, "added": [...], "removed": [...]}, ... ]
    }
    """
    # 1) axis 数量变化
    old_axes = old.get("axes", {})
    new_axes = new.get("axes", {})
    axis_keys = sorted(set(old_axes.keys()) | set(new_axes.keys()))
    axis_changes = {}
    for k in axis_keys:
        o = len(old_axes.get(k, []))
        n = len(new_axes.get(k, []))
        axis_changes[k] = {"old": o, "new": n, "delta": n - o}

    # 2) item 比较
    old_idx = _index_by_id(old)
    new_idx = _index_by_id(new)

    old_ids = set(old_idx.keys())
    new_ids = set(new_idx.keys())

    # 注意：HTML 用 smart-compat / class="xN" 时，相同名字可能 id 不同或省略 id
    # 我们仅按 id 比对，未匹配的另外做"按 name 联动"
    added_ids    = [new_idx[i] for i in (new_ids - old_ids)]
    removed_ids  = [old_idx[i] for i in (old_ids - new_ids)]

    # 3) 重命名（id 相同但名字不一样）— 在 common 子集里
    renamed = []
    compat_changes = []
    common = old_ids & new_ids
    for iid in common:
        o = old_idx[iid]; n = new_idx[iid]
        if (o.get("name") or "") != (n.get("name") or ""):
            renamed.append({
                "id":       iid,
                "old_name": o.get("name") or "",
                "new_name": n.get("name") or "",
                "axis":     n.get("axis_origin") or o.get("axis_origin") or "",
            })
        old_cw = set(o.get("compat_with") or [])
        new_cw = set(n.get("compat_with") or [])
        add    = sorted(new_cw - old_cw)
        rm     = sorted(old_cw - new_cw)
        if add or rm:
            compat_changes.append({
                "id":      iid,
                "axis":    n.get("axis_origin") or o.get("axis_origin") or "",
                "name":    n.get("name") or "",
                "added":   add,
                "removed": rm,
            })

    return {
        "old_meta":       old.get("meta", {}),
        "new_meta":       new.get("meta", {}),
        "axis_changes":   axis_changes,
        "added_ids":      sorted(added_ids, key=lambda x: x.get("name") or ""),
        "removed_ids":    sorted(removed_ids, key=lambda x: x.get("name") or ""),
        "renamed_ids":    sorted(renamed, key=lambda x: x["id"]),
        "compat_changes": sorted(compat_changes, key=lambda x: x["id"]),
        "computed_at":    _dt.datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 控制台
# ---------------------------------------------------------------------------
def print_console(d: dict) -> None:
    print()
    print(f"Diff: {d['old_meta'].get('source_file')} ({d['old_meta'].get('week_label')})")
    print(f"  -> {d['new_meta'].get('source_file')} ({d['new_meta'].get('week_label')})")
    print()
    print("axis 数量变化：")
    print(f"  {'axis':<22}  {'old':>6}  {'new':>6}  {'Δ':>5}")
    for k, v in d["axis_changes"].items():
        if v["old"] or v["new"]:
            print(f"  {k:<22}  {v['old']:>6}  {v['new']:>6}  {v['delta']:>+5}")
    print()
    print(f"新增 items: {len(d['added_ids'])}")
    print(f"删除 items: {len(d['removed_ids'])}")
    print(f"重命名 items: {len(d['renamed_ids'])}")
    print(f"compat 变化 items: {len(d['compat_changes'])}")


# ---------------------------------------------------------------------------
# HTML diff 报告
# ---------------------------------------------------------------------------
DIFF_HTML = Template(r"""
<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Portfolio Navigator diff</title>
<style>
  body { font: 13px/1.5 -apple-system,"Segoe UI",sans-serif; margin: 32px; color: #222; }
  h1 { font-size: 20px; }
  h2 { margin-top: 28px; font-size: 16px; border-bottom: 1px solid #ddd; padding-bottom: 3px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0 24px; }
  th, td { padding: 4px 8px; border-bottom: 1px solid #eee; font-size: 12px; text-align: left; vertical-align: top; }
  th { background: #f5f5f5; }
  .id { font-family: ui-monospace, Consolas, monospace; color: #a04; font-size: 11px; }
  .added   { background: #f0fff0; }
  .removed { background: #fff0f0; color: #800; }
  .changed { background: #fff8e0; }
  details { margin-bottom: 8px; }
  summary { cursor: pointer; }
  .meta { color: #666; font-size: 12px; margin-bottom: 12px; }
</style>
</head>
<body>
<h1>Portfolio Navigator diff</h1>
<div class="meta">
  Old: {{ d.old_meta.week_label }} — {{ d.old_meta.source_file }}<br>
  New: {{ d.new_meta.week_label }} — {{ d.new_meta.source_file }}<br>
  Computed at {{ d.computed_at }}
</div>

<h2>axis 数量变化</h2>
<table><thead><tr><th>axis</th><th>old</th><th>new</th><th>Δ</th></tr></thead><tbody>
{% for k, v in d.axis_changes.items() %}
  {% if v.old or v.new %}
  <tr>
    <td>{{ k }}</td><td>{{ v.old }}</td><td>{{ v.new }}</td>
    <td>{{ "%+d"|format(v.delta) }}</td>
  </tr>
  {% endif %}
{% endfor %}
</tbody></table>

<h2>新增 item（{{ d.added_ids | length }}）</h2>
{% if d.added_ids %}
<table><thead><tr><th>ID</th><th>名称</th><th>轴</th></tr></thead>
<tbody>
{% for it in d.added_ids %}
<tr class="added">
  <td class="id">{{ it.id }}</td>
  <td>{{ it.name }}</td>
  <td>{{ it.axis_origin or "" }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}
<p>(无)</p>
{% endif %}

<h2>删除 item（{{ d.removed_ids | length }}）</h2>
{% if d.removed_ids %}
<table><thead><tr><th>ID</th><th>名称</th><th>轴</th></tr></thead>
<tbody>
{% for it in d.removed_ids %}
<tr class="removed">
  <td class="id">{{ it.id }}</td>
  <td>{{ it.name }}</td>
  <td>{{ it.axis_origin or "" }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}
<p>(无)</p>
{% endif %}

<h2>重命名 item（{{ d.renamed_ids | length }}）</h2>
{% if d.renamed_ids %}
<table><thead><tr><th>ID</th><th>old</th><th>new</th><th>轴</th></tr></thead>
<tbody>
{% for it in d.renamed_ids %}
<tr class="changed">
  <td class="id">{{ it.id }}</td>
  <td><s>{{ it.old_name }}</s></td>
  <td><b>{{ it.new_name }}</b></td>
  <td>{{ it.axis }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}
<p>(无)</p>
{% endif %}

<h2>compat 变化 item（{{ d.compat_changes | length }}）</h2>
<details>
<summary>展开查看</summary>
{% if d.compat_changes %}
<table><thead><tr><th>ID</th><th>名称</th><th>添加 compat</th><th>移除 compat</th></tr></thead>
<tbody>
{% for it in d.compat_changes %}
<tr>
  <td class="id">{{ it.id }}</td>
  <td>{{ it.name }}</td>
  <td>{{ it.added | join(", ") }}</td>
  <td>{{ it.removed | join(", ") }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}<p>(无)</p>{% endif %}
</details>

</body></html>
""")


def render_html(d: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(DIFF_HTML.render(d=d), encoding="utf-8")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="比较两份 Portfolio Navigator JSON")
    ap.add_argument("old", type=Path, help="旧版本 JSON")
    ap.add_argument("new", type=Path, help="新版本 JSON")
    ap.add_argument("--out", type=Path, help="HTML diff 报告路径（默认写到 out/ 下）")
    args = ap.parse_args(argv)

    if not args.old.exists():
        print(f"[ERR] {args.old} 不存在", file=sys.stderr)
        return 1
    if not args.new.exists():
        print(f"[ERR] {args.new} 不存在", file=sys.stderr)
        return 1

    old = load_json(args.old)
    new = load_json(args.new)
    d = diff(old, new)

    print_console(d)

    if args.out:
        out = args.out
    else:
        out = Path("out") / "diff.html"
    render_html(d, out)
    print(f"[OK] HTML 报告 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
