"""
extract_from_html.py — 从 Dassault Systemes Portfolio Navigator HTML 抽取稳定 JSON schema

设计目标：
- 解析层跟具体版本解耦（DS 改 HTML 模板时，本脚本可以快速适配）
- 输出一个固定的 JSON schema，下游 ipecalc.py 完全只看这个 schema
- 兼容 R2024x（旧 class="xN" 结构）和 R2026x（smart-compat 属性 + crolelist /croleline 结构）

用法：
    python extract_from_html.py <html_path> -o <json_path>

依赖：beautifulsoup4
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Axis mapping — Portfolio Navigator HTML 里 ul 的 id -> 我们 schema 里的字段名
# 未来 DS 改了 ul id，这里改一行就行。axis 的顺序不影响计算。
# ---------------------------------------------------------------------------
AXIS_UL_IDS: list[tuple[str, str]] = [
    # 跨版本通用
    ("brands",               "cbrand"),
    ("portfolios",           "cportfolioname"),
    ("themes",               "ctheme"),
    ("disciplines",          "cdiscipline"),
    ("item_types",           "citemtype"),
    ("license_types",        "clicensetype"),
    ("ds_offerings",         "cdsoffering"),
    ("industry_portfolios",  "cindustryportfolio"),
    ("ise",                  "cise"),
    ("ipe",                  "cipe"),
    ("segments",             "csegment"),
    ("media_names",          "cmedianames"),
    # R2026x 引入
    ("ipe_occupations",      "cipeocc"),
    ("portfolio_releases",   "cportfoliorelease"),
    ("version_long_names",   "cversionlongname"),
    ("release_origins",      "creleaseorigin"),
    ("role_effectiveness",   "croleeffectiveness"),
    ("role_availability",    "croleavailability"),
    ("ipe_effectiveness",    "ipeeffectiveness"),
    ("ipe_sustainability",   "ipesustainability"),
    ("ipe_maturity",         "ipematurity"),
    ("app_validation_kit",   "cappvalidationkit"),
    ("app_links",            "capplink"),
    # 注意：crolelist 在 R2026x 是一个分组容器，内部用 class="croleline" 拆组
    # 它的 li 单独处理，不通过 AXIS_UL_IDS
]

# 版本/周次信息 — 在 <style id="date"> 里
DATE_VAR_RE = re.compile(r'--PNdate\s*:\s*"([^"]+)"')


# axis 查询字典（ul_id -> schema_name 的反向索引）
AXIS_DICT: dict[str, str] = {ul_id: schema_name for schema_name, ul_id in AXIS_UL_IDS}


# ---------------------------------------------------------------------------
# Compat 提取 — R2024x 用 class="xN xN..."；R2026x 用 smart-compat="xN xN..."
# ---------------------------------------------------------------------------
def _extract_compat_with(li_el) -> list[str]:
    # R2026x：优先用 data-compat（完整，含跨轴 Portfolio/Role 关联）
    dc = li_el.get("data-compat")
    if dc:
        return dc.split()
    # R2024x：class 中的 xN
    cls = li_el.get("class") or []
    compat = [c for c in cls if c.startswith("x")]
    if compat:
        return compat
    # R2026x 兜底：smart-compat（精简版，仅同轴 sibling）
    sc = li_el.get("smart-compat")
    if sc:
        return sc.split()
    return []


# ---------------------------------------------------------------------------
# Hook span — <span class="hook oc|op|arrow" data-idpage="...">
# ---------------------------------------------------------------------------
def _extract_hooks(li_el) -> dict[str, str | None]:
    hooks: dict[str, str | None] = {"cloud": None, "premise": None, "myoffer": None}
    for span in li_el.find_all("span"):
        cls = (span.get("class") or [])
        if "oc" in cls:
            hooks["cloud"] = span.get("data-idpage")
        elif "op" in cls:
            hooks["premise"] = span.get("data-idpage")
        elif "arrow" in cls:
            hooks["myoffer"] = span.get("data-idpage")
    return hooks


def _extract_text(li_el) -> str:
    """li 的显示文本（剥 hook span 之类干扰）"""
    return li_el.get_text(" ", strip=True).strip()


def _extract_li(axis: str | None, li_el) -> dict[str, Any]:
    return {
        "id":          li_el.get("id"),
        "name":        _extract_text(li_el),
        "axis_origin": axis,           # 用 schema_name（不是 ul_id）方便下游使用
        "compat_with": _extract_compat_with(li_el),
        "data_filter": li_el.get("data-filter"),
        "hooks":       _extract_hooks(li_el),
    }


def _ul_id_to_schema(ul_id: str) -> str | None:
    for schema_name, mapped_ul_id in AXIS_UL_IDS:
        if mapped_ul_id == ul_id:
            return schema_name
    return None


# ---------------------------------------------------------------------------
# Axis 维度抽取
# ---------------------------------------------------------------------------
def extract_axis_items(soup: BeautifulSoup, ul_id: str, schema_name: str | None = None) -> list[dict[str, Any]]:
    """给一个 ul id，把这个 ul 下所有 li 抽成 axis 维度条目。"""
    ul = soup.find("ul", {"id": ul_id})
    if ul is None:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    axis_label = schema_name or _ul_id_to_schema(ul_id) or ul_id
    for li in ul.find_all("li", recursive=True):
        item_id = li.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        out.append(_extract_li(axis=axis_label, li_el=li))
    return out


# ---------------------------------------------------------------------------
# crolelist / croleline 特殊处理（R2026x 结构：嵌套分组）
# ---------------------------------------------------------------------------
def extract_croles(soup: BeautifulSoup) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    抽 crolist 下的所有 croline（角色分组）：
    返回 (roles, role_items)：
      - roles  — 主条目（li.crolename），其 id 既是 x 也是 grouping key
      - role_items — 同一 croline 下的所有 li（含主 li + 子 li/trigram/role_item_id）
    每个项都带 croline_title 和 croline_group 字段，让你向上找组名。
    """
    cl = soup.find("ul", {"id": "crolelist"})
    if cl is None:
        return [], []

    roles: list[dict[str, Any]] = []
    role_items: list[dict[str, Any]] = []
    for croline_ul in cl.find_all("ul", class_="croleline", recursive=True):
        title_div = croline_ul.find("div", class_="crolename", recursive=False)
        title = title_div.get_text(" ", strip=True) if title_div else None
        first_li = croline_ul.find("li", recursive=False)
        group_id = first_li.get("id") if first_li else None

        main_li: dict[str, Any] | None = None
        for li in croline_ul.find_all("li", recursive=False):
            item = _extract_li(axis="croles", li_el=li)   # 用 schema_name
            item["croline_title"]  = title
            item["croline_group"]  = group_id
            role_items.append(item)
            if main_li is None:
                main_li = item
        if main_li is not None:
            roles.append(main_li)

    return roles, role_items


# ---------------------------------------------------------------------------
# 全部 items（去重）
# ---------------------------------------------------------------------------
def extract_all_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """全页面所有 li，去重 by id。"""
    seen: dict[str, dict[str, Any]] = {}
    # 普通 axis：按已知顺序优先收录
    for _schema_name, ul_id in AXIS_UL_IDS:
        for item in extract_axis_items(soup, ul_id):
            iid = item["id"]
            if iid and iid not in seen:
                seen[iid] = item
    # crolelist：每个 croline 里的 li
    _roles, role_items = extract_croles(soup)
    for item in role_items:
        iid = item["id"]
        if iid and iid not in seen:
            seen[iid] = item
    # 兜底：body 内仍未收录的 li（任何 id）
    if soup.body is not None:
        for li in soup.body.find_all("li"):
            iid = li.get("id")
            if not iid or iid in seen:
                continue
            if iid.startswith("x"):
                seen[iid] = _extract_li(axis=None, li_el=li)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Prereq / Meta
# ---------------------------------------------------------------------------
def extract_prereqs(soup: BeautifulSoup) -> list[dict[str, str]]:
    """抽出前提条件表达式（纯文本逻辑表达式）"""
    ul = soup.find("ul", {"id": "cprereqlist"})
    if ul is None:
        return []
    out = []
    seen: set[str] = set()
    for li in ul.find_all("li", recursive=True):
        item_id = li.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        expr = li.get_text(" ", strip=True)
        if expr:
            out.append({"id": item_id, "expr": expr})
    return out


def extract_meta(soup: BeautifulSoup, html_path: Path) -> dict[str, Any]:
    """版本 / 周次 / 导出时间"""
    week = None
    for st in soup.find_all("style"):
        if not hasattr(st, "get_text"):
            continue
        m = DATE_VAR_RE.search(st.get_text())
        if m:
            week = m.group(1)
            break

    title_el = soup.find("title")
    title = title_el.get_text(" ", strip=True) if title_el else None

    return {
        "title":        title,
        "week_label":   week,                  # 例如 "2026 Week 18.3"
        "source_file":  str(html_path),
        "extracted_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "tool_version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def extract(html_path: Path) -> dict[str, Any]:
    raw = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")

    axes: dict[str, list[dict[str, Any]]] = {}
    for schema_name, ul_id in AXIS_UL_IDS:
        axes[schema_name] = extract_axis_items(soup, ul_id, schema_name=schema_name)

    roles, _role_items = extract_croles(soup)
    axes["croles"] = roles          # 把 roles 主条目也塞进 axes 方便按 axis 查

    items = extract_all_items(soup)
    # 修正 axis_origin：把 ul_id 形式（如 "croleeffectiveness"）转成 schema_name
    for it in items:
        ax = it.get("axis_origin")
        if ax and ax.startswith("c") and ax not in AXIS_DICT:
            mapped = _ul_id_to_schema(ax)
            if mapped:
                it["axis_origin"] = mapped
    prereqs = extract_prereqs(soup)

    return {
        "meta":    extract_meta(soup, html_path),
        "axes":    axes,
        "items":   items,
        "prereqs": prereqs,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Extract Portfolio Navigator HTML -> stable JSON schema")
    ap.add_argument("html", type=Path, help="输入 HTML 路径")
    ap.add_argument("-o", "--output", type=Path, required=True, help="输出 JSON 路径")
    ap.add_argument("--pretty", action="store_true", help="美化输出（默认紧凑）")
    ap.add_argument("--role-filter", choices=["all", "ga_only", "ga_available"], default="ga_available",
                    help="Role 过滤：ga_available (默认) 保留 GA 在可用列表里的；ga_only 仅保留纯 GA；all 不过滤")
    args = ap.parse_args(argv)

    if not args.html.exists():
        print(f"[ERR] HTML 文件不存在: {args.html}", file=sys.stderr)
        return 1

    data = extract(args.html)
    ga_only_count = filter_ca_only_roles(data, keep=args.role_filter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if args.pretty else None
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")

    counts = {k: len(v) for k, v in data["axes"].items()}
    print(f"[OK] Extracted to {args.output}")
    print(f"  meta.week_label = {data['meta'].get('week_label')!r}")
    print(f"  meta.title      = {data['meta'].get('title')!r}")
    print(f"  items total     = {len(data['items'])}")
    print(f"  prereqs         = {len(data['prereqs'])}")
    print(f"  Role filter: {args.role_filter}, removed CA-only: {ga_only_count}")
    for axis, n in counts.items():
        print(f"  axis[{axis:<22}] = {n}")
    return 0


def filter_ca_only_roles(data: dict, keep: str = "ga_available") -> int:
    """从 data['items'] 移除 Role items 中 availability 只有 CA 的（keep='ga_available' 时）。

    通过 item 的 compat_with 找到 role_availability axis item（'GA' 或 'CA'），
    保留 GA 在可用列表里的 Role（GA-only 和 GA+CA 都保留）。
    返回被过滤掉的数量。
    """
    axes = data.get("axes", {})
    items = data.get("items", [])
    ra_axis = axes.get("role_availability", [])
    if not ra_axis:
        return 0
    # 找出 GA / CA 对应的 id
    ra_map = {r["id"]: (r.get("name") or "").upper() for r in ra_axis}
    ga_ids = {i for i, n in ra_map.items() if n == "GA"}
    ca_ids = {i for i, n in ra_map.items() if n == "CA"}
    if not ga_ids:
        return 0

    removed = 0
    new_items = []
    for it in items:
        if it.get("axis_origin") != "croles":
            new_items.append(it); continue
        cw = set(it.get("compat_with") or [])
        # 兼容多 release 的 Role：保留至少有一个 release 标了 GA 的
        has_ga = bool(cw & ga_ids)
        has_ca = bool(cw & ca_ids)
        if keep == "ga_available":
            # 保留条件：标了 GA（不管有没有 CA）
            if has_ga:
                new_items.append(it)
            else:
                removed += 1
        elif keep == "ga_only":
            if has_ga and not has_ca:
                new_items.append(it)
            else:
                removed += 1
        else:  # 'all'
            new_items.append(it)
    data["items"] = new_items
    return removed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
