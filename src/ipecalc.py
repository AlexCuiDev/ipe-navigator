"""
ipecalc.py — 覆盖度计算 + 报告生成

读 source（HTML 解出来的 JSON）和 company.json（用户订阅），
算"我订阅的 portfolio 能激活多少 IPE / portfolio / 角色"。

算法（兼容图，bounded closure）：
    - 第 0 层：my_ids（用户订阅的 portfolio 集合）
    - 第 N 层（≤ max_hop）：item.compat_with 与上一层的 covered 集合有交集
    - max_hop 控制传导距离，1 是默认（只扩 1 层，能命中直接兼容的角色/学科/主题，
      但不会扩散到全图）

用法：
    python ipecalc.py --source samples/r2026x_w18.3.json --company company.json --out report.html
    python ipecalc.py --source samples/r2026x_w18.3.json --company company.json --hop 2 --console
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import html
import json
import sys
from pathlib import Path

from jinja2 import Template


# ---------------------------------------------------------------------------
# 计算
# ---------------------------------------------------------------------------
def load_json(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[ERR] 文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def my_portfolio_ids(company: dict) -> set[str]:
    return {ent["id"] for ent in company.get("portfolios", []) if ent.get("id")}


def compute(source: dict, company: dict, max_hop: int = 1) -> dict:
    """
    返回结构化统计结果，可被 report module 渲染。

    算法：图可达性 (transitive closure over compat_with)
      - my_ids 是用户订阅的 portfolio 集合
      - 沿 compat_with 边做 BFS，最远走 max_hop 层
    """
    my_ids = my_portfolio_ids(company)
    if not my_ids:
        return {
            "company_name":     company.get("company", "My Company"),
            "my_count":         0,
            "my_ids":           [],
            "max_hop":          max_hop,
            "version_label":    source["meta"].get("week_label"),
            "version_title":    source["meta"].get("title"),
            "computed_at":      _dt.datetime.now().isoformat(timespec="seconds"),
            "axis_stats":       [],
            "activated":        {},
            "not_activated":    {},
            "role_items_total": 0,
        }

    # 1) 拼所有 items + 给 item 加 axis 元信息
    all_items: list[dict] = list(source["items"])
    id_to_axis: dict[str, str] = {}
    for axis_name, items in source["axes"].items():
        for it in items:
            if it.get("id") and it["id"] not in id_to_axis:
                id_to_axis[it["id"]] = axis_name

    # 2) 建反向索引：compat_with[x_id] -> [item.id with that compat]
    iindex: dict[str, list[str]] = collections.defaultdict(list)
    item_by_id: dict[str, dict] = {}
    for it in all_items:
        iid = it.get("id")
        if not iid:
            continue
        item_by_id[iid] = it
        for cid in (it.get("compat_with") or []):
            iindex[cid].append(iid)

    # 3) Bounded BFS
    covered: set[str] = set()
    queue = collections.deque()
    for mid in my_ids:
        if mid not in covered:
            covered.add(mid)
            queue.append(mid)
    hop = 0
    while queue and hop < max_hop:
        nxt_queue = []
        for nid in queue:
            for nxt in iindex.get(nid, ()):
                if nxt not in covered:
                    covered.add(nxt)
                    nxt_queue.append(nxt)
        queue = nxt_queue
        hop += 1

    # 4) 按 axis 分组
    activated:    dict[str, list[dict]] = collections.defaultdict(list)
    not_activated: dict[str, list[dict]] = collections.defaultdict(list)
    for it in all_items:
        iid = it.get("id")
        if not iid:
            continue
        ax = it.get("axis_origin") or id_to_axis.get(iid) or "items"
        if iid in covered:
            activated[ax].append(it)
        else:
            not_activated[ax].append(it)

    # 5) 汇总
    axis_names = sorted(activated.keys() | not_activated.keys())
    axis_stats: list[dict] = []
    for ax in axis_names:
        a = activated[ax]
        na = not_activated[ax]
        axis_stats.append({
            "axis":          ax,
            "total":         len(a) + len(na),
            "activated":     len(a),
            "not_activated": len(na),
        })

    return {
        "company_name":     company.get("company", "My Company"),
        "my_count":         len(my_ids),
        "my_ids":           sorted(my_ids),
        "max_hop":          max_hop,
        "version_label":    source["meta"].get("week_label"),
        "version_title":    source["meta"].get("title"),
        "computed_at":      _dt.datetime.now().isoformat(timespec="seconds"),
        "axis_stats":       axis_stats,
        "activated":        dict(activated),
        "not_activated":    dict(not_activated),
        "role_items_total": len(all_items),
    }


# ---------------------------------------------------------------------------
# 控制台输出（紧凑摘要）
# ---------------------------------------------------------------------------
def print_console(report: dict) -> None:
    print(f"\nIPE Statistics — {report['company_name']}")
    print(f"版本：{report['version_label'] or '?'}   {report['version_title'] or ''}")
    print(f"计算于 {report['computed_at']}")
    print(f"我的订阅 portfolio：{report['my_count']} 个")
    print()
    print(f"  {'axis':<22}  {'总数':>5}  {'可激活':>7}  {'未激活':>7}")
    print(f"  {'-'*22}  {'-'*5}  {'-'*7}  {'-'*7}")
    for s in report["axis_stats"]:
        print(f"  {s['axis']:<22}  {s['total']:>5}  {s['activated']:>7}  {s['not_activated']:>7}")


# ---------------------------------------------------------------------------
# HTML 报告（用 jinja2 内联模板）
# ---------------------------------------------------------------------------
REPORT_HTML = Template(r"""
<!doctype html>
<html lang="zh-cn">
<head>
<meta charset="utf-8">
<title>IPE Statistics — {{ report.company_name }}</title>
<style>
  body { font: 14px/1.45 -apple-system, "Segoe UI", Arial, sans-serif; margin: 32px; color: #222; }
  h1 { font-size: 22px; }
  h2 { margin-top: 36px; font-size: 18px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  .meta { color: #666; margin-bottom: 16px; font-size: 12px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0 24px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #eee; text-align: left; font-size: 13px; vertical-align: top; }
  th { background: #f5f5f5; }
  tr.activated td { background: #f0fff0; }
  tr.not_activated td { background: #fff8f8; color: #888; }
  .tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
  .tag.ok  { background: #cfe; color: #060; }
  .tag.no  { background: #fdd; color: #800; }
  .id { font-family: ui-monospace, Consolas, monospace; color: #a04; font-size: 11px; }
  summary { cursor: pointer; }
  details { margin-bottom: 8px; }
</style>
</head>
<body>

<h1>IPE Statistics — {{ report.company_name | e }}</h1>
<div class="meta">
  版本：{{ report.version_label or "?" }} — {{ report.version_title or "" }}<br>
  计算于 {{ report.computed_at }}<br>
  closure 跳数 max_hop = {{ report.max_hop }}<br>
  我的 portfolio 订阅：{{ report.my_count }} 个（{{ report.my_ids | join(", ") | e }}）
</div>

<h2>覆盖度概览</h2>
<table>
  <thead>
    <tr><th>axis</th><th>总数</th><th>可激活</th><th>未激活</th><th>覆盖比例</th></tr>
  </thead>
  <tbody>
    {% for s in report.axis_stats %}
    {% set p = (s.activated * 100 // (s.activated + s.not_activated)) if (s.activated + s.not_activated) else 0 %}
    <tr>
      <td>{{ s.axis }}</td>
      <td>{{ s.total }}</td>
      <td>{{ s.activated }}</td>
      <td>{{ s.not_activated }}</td>
      <td>{{ p }}%</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>可激活的 Portfolio / ISE / IPE</h2>
{% set show_axes = ['portfolios','portfolio_releases','ise','ipe','ise','industry_portfolios','segments'] %}
{% for axis_name in show_axes %}
  {% set items = report.activated.get(axis_name, []) %}
  {% if items %}
  <details open>
    <summary><strong>{{ axis_name }}</strong> — {{ items | length }} 项可激活</summary>
    <table>
      <thead><tr><th>ID</th><th>名称</th></tr></thead>
      <tbody>
        {% for it in items | sort(attribute='name') %}
        <tr class="activated">
          <td class="id">{{ it.id }}</td>
          <td>{{ it.name }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </details>
  {% endif %}
{% endfor %}

<h2>可激活的角色（Croles）</h2>
{% set croles = report.activated.get('croles', []) %}
{% if croles %}
<details open>
  <summary><strong>croles</strong> — {{ croles | length }} 个角色可激活</summary>
  <table>
    <thead><tr><th>ID</th><th>名称</th></tr></thead>
    <tbody>
      {% for it in croles | sort(attribute='name') %}
      <tr class="activated">
        <td class="id">{{ it.id }}</td>
        <td>{{ it.name }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</details>
{% endif %}

<h2>未激活的内容（前 50）</h2>
<p>下面列出的内容若用户已订阅相关 portfolio 但未能命中 compat，可能是因为 compat 维度过严或订阅缺失。</p>
{% for axis_name in show_axes %}
  {% set items = report.not_activated.get(axis_name, []) %}
  {% if items %}
  <details>
    <summary><strong>{{ axis_name }}</strong> — {{ items | length }} 项未激活</summary>
    <table>
      <thead><tr><th>ID</th><th>名称</th></tr></thead>
      <tbody>
        {% for it in items | sort(attribute='name') %}
        <tr class="not_activated">
          <td class="id">{{ it.id }}</td>
          <td>{{ it.name }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </details>
  {% endif %}
{% endfor %}

</body>
</html>
""")


def render_html(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_str = REPORT_HTML.render(report=report)
    out_path.write_text(html_str, encoding="utf-8")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="覆盖率计算 + 报告生成")
    ap.add_argument("--source", required=True, type=Path, help="Portfolio Navigator JSON (extract_from_html.py 的输出)")
    ap.add_argument("--company", required=True, type=Path, help="company.json (company.py 的输出)")
    ap.add_argument("--out", type=Path, default=Path("report.html"), help="HTML 报告输出路径")
    ap.add_argument("--hop", type=int, default=2,
                    help="兼容图 BFS 的最大跳数（默认 2：用户订阅 + 一次兼容跳；"
                         "1 = 仅直接命中；≥3 通常会把全图覆盖）")
    ap.add_argument("--console", action="store_true", help="额外打印控制台摘要")
    args = ap.parse_args(argv)

    source = load_json(args.source)
    company = load_json(args.company)
    report = compute(source, company, max_hop=args.hop)

    render_html(report, args.out)
    print(f"[OK] HTML 报告 -> {args.out}")
    print(f"     公司={report['company_name']}  订阅 portfolio={report['my_count']}  "
          f"周次={report['version_label']}")

    if args.console:
        print_console(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
