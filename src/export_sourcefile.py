"""
export_sourcefile.py — 把 Portfolio Navigator JSON 拆分成跟 DS 内部分发版一致的 sourcefile CSV

目标：让本工具产出的 CSV 跟 DS 内部 IPESummary / MyCompanyInfo 期望的格式兼容。
      用户可以拿这些 CSV 当 sourcefile 喂养任何下游工具。

输入：samples/<version>.json（extract_from_html.py 的输出）
输出：
    <out>/sourcefile/
      Portfolio/<portfolio name>.csv
      IPE/<industry tree>/<item>.csv
      Restricted Reference Portfolio.txt

DS 内部 CSV 格式（Catalog of sourcefile/Portfolio/CATIA Composer.csv）：
    - 顶部 disclaimer（约 6 行）
    - 几行 CSS（约 25 行）
    - Preview Mode 帮助段（约 8 行）
    - Criteria selected：
        Portfolio Name,Role Availability
        CATIA Composer,GA
        <空行>
        Portfolio Name,Role item Id
        CATIA Composer,C4P-C
        ,C4P-N
        ,CCK-C
        ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# CSV 文件头部模板（尽量复刻 DS 内部版式）
# ---------------------------------------------------------------------------
CSV_HEADER_TEMPLATE = """\
\t\t\tThe description of the 3DS Offering is provided herein under for information purpose. Solely the information available in
\t\t\tDSx.CLIENT CARE & ORDER may have a contractual value.
\t\t\t
\t\t\t\t
\t\t\t\t\tDo not share this tool with customers
\t\t\t\t
\

\ta#bpreview \t\t\t { position:absolute; top:-58px; right:-618px; border-radius:8px;
\t\t\t\t\t\t\t\tbackground-image: url("../../resources/thirdparty/DSXOFFER/www_images/poff.png");
\t\t\t\t\t\t\t\tdisplay:inline-block; width:35px; height:35px; padding:0; margin:0; }
\ta.on#bpreview \t\t { background-image: url("../../resources/thirdparty/DSXOFFER/www_images/pon.png"); }
\t\t\t\t\t\t\t
\ta:hover#bpreview { box-shadow:inset 2px 2px 2px 1px silver, inset -2px -2px 2px 1px silver;\t}

\t#prevexp\t{ display:none;
\t\t\t\t  position:absolute; z-index:1000000000;
\t\t\t\t  top:-58px; right:-950px; width:200px; height:55px;
\t\t\t\t  border:1px gray solid; border-radius:4px; background-color:white;
\t\t\t\t  box-shadow: 2px 2px 2px 1px silver, -2px -2px 2px 1px silver;
\t\t\t\t  padding:3px; font-style: normal; text-align: justify; font-size:smaller;
\t\t\t  }
\tli.visib#prevexp\t{ display:inline-block; }

\t\t\t
\t\t\t\t
\t\t\t\t
\t\t\t\t\t\t\t
\t\t\t\t\t\t\t
\t\t\t\t\t\t\t\t Preview Mode
\t\t\t\t\t\t\t
\t\t\t\t\t\tNarrow down your selection with fast preview.
\t\t\t\t\t\t
\t\t\t\t\t\t
\t\t\t\t\t\tSwitch on and off button.
\t\t\t\t\t\t
\t\t\t\t

Criteria selected:
__CRITERIA__
Portfolio Name,Role item Id
__ROLES__
"""

CRITERIA_PORTFOLIO_TEMPLATE = "Portfolio Name,Role Availability\n{name},{availability}\n\n"
CRITERIA_IPE_TEMPLATE      = "IPE Name,IPE Availability\n{name},{availability}\n\n"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _safe_filename(s: str) -> str:
    """Windows/Linux 通用的合法文件名"""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if not s:
        s = "unnamed"
    return s[:240]


def _looks_like_trigram(name: str | None) -> bool:
    """判断 name 是否像 role item id（短、含大写字母数字横线、不含空格）"""
    if not name:
        return False
    n = name.strip()
    if len(n) > 12:
        return False
    if ' ' in n:
        return False
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$", n):
        return False
    return True


def _build_index(source: dict) -> dict:
    """建几个反向/索引方便后面查找"""
    items = source.get("items", [])
    return {
        "items":            items,
        "items_by_id":      {it["id"]: it for it in items if it.get("id")},
        "axes":             source.get("axes", {}),
        "items_by_axis":    source.get("axes", {}),  # 每个 axis 是 list of items
    }


def _items_compat_contains_target(items, target_id: str) -> list[dict]:
    """返回所有 compat_with 含 target_id 的 item"""
    return [it for it in items
            if it.get("id") and target_id in (it.get("compat_with") or [])]


def _filter_to_role_items(items: Iterable[dict]) -> list[dict]:
    """
    一个 item 是 role 类的简化规则：
      - axis_origin 是 ''、None 或 'croles'/'role_item_ids'/'role_effectiveness'/'role_availability'/'app_links'/'capplink'/'ropeitemid'/'rolemname'
      - 名字看起来像 trigram
    """
    ROLE_AXES = {None, "", "croles", "role_item_ids", "role_effectiveness",
                 "role_availability", "app_links", "capplink", "app_validation_kit",
                 "items"}  # 'items' 是 fallback 后没有 axis_origin
    out = []
    for it in items:
        ax = it.get("axis_origin")
        if ax in ROLE_AXES and _looks_like_trigram(it.get("name")):
            out.append(it)
    # 按名字排序保持稳定
    out.sort(key=lambda x: (x.get("name") or ""))
    return out


# ---------------------------------------------------------------------------
# 导出 Portfolio CSV
# ---------------------------------------------------------------------------
def export_portfolio_csv(out_root: Path, source: dict, portfolio_axes: list[str]) -> int:
    """
    对 portfolios axis 的每一个 li 写一份 CSV：
    /Portfolio/<safe_name>.csv
    """
    idx = _build_index(source)
    all_items = idx["items"]

    written = 0
    for axis_name in portfolio_axes:
        for p_item in idx["axes"].get(axis_name, []):
            pid = p_item.get("id")
            pname = (p_item.get("name") or "").strip()
            if not pid or not pname:
                continue

            # 这个 portfolio 的"角色" = 所有 compat_with 含 pid 的角色类 items
            candidates = _items_compat_contains_target(all_items, pid)
            role_items = _filter_to_role_items(candidates)
            if not role_items:
                continue

            criteria_block = CRITERIA_PORTFOLIO_TEMPLATE.format(
                name=pname, availability="GA")
            role_lines = "\n".join(f"{pname if i == 0 else ''},{it.get('name','')}"
                                   for i, it in enumerate(role_items))

            content = CSV_HEADER_TEMPLATE.replace("__CRITERIA__", criteria_block) \
                                           .replace("__ROLES__", role_lines)
            target = out_root / "Portfolio" / f"{_safe_filename(pname)}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written += 1
    return written


# ---------------------------------------------------------------------------
# 导出 IPE CSV（按 industry tree）
# ---------------------------------------------------------------------------
def export_ipe_csv(out_root: Path, source: dict) -> int:
    """IPE axis 里 li 把"name"当行业路径（如 '08 Life Sciences'、'03 Marine...'）"""
    idx = _build_index(source)
    all_items = idx["items"]

    written = 0
    for ipe_item in idx["axes"].get("ipe", []):
        iid  = ipe_item.get("id")
        iname = (ipe_item.get("name") or "").strip()
        if not iid or not iname:
            continue

        candidates = _items_compat_contains_target(all_items, iid)
        role_items = _filter_to_role_items(candidates)
        if not role_items:
            continue

        # name 一般形如 '01-Asset Commissioning' —— 用 'NN-...' 当文件名
        # 行业路径按 digits 开头分割
        m = re.match(r"^(\d{2})\s*[-_]?\s*(.*)$", iname)
        if m:
            num, rest = m.group(1), m.group(2).strip() or iname
            filename = f"{num} - {rest}.csv"
            # 子目录按前导数字（"08 Life Sciences..."）自动分——这里简化为放一个 IPE/ 平面下
            target = out_root / "IPE" / filename
        else:
            target = out_root / "IPE" / f"{_safe_filename(iname)}.csv"
        target.parent.mkdir(parents=True, exist_ok=True)

        criteria_block = CRITERIA_IPE_TEMPLATE.format(name=iname, availability="GA")
        role_lines = "\n".join(f"{iname if i == 0 else ''},{it.get('name','')}"
                               for i, it in enumerate(role_items))
        content = CSV_HEADER_TEMPLATE.replace("__CRITERIA__", criteria_block) \
                                       .replace("__ROLES__", role_lines)
        target.write_text(content, encoding="utf-8")
        written += 1
    return written


def export_restricted_reference(out_root: Path, source: dict) -> int:
    """
    把 Restricted Reference Portfolio 写成一个 .txt。

    在 R2026x 里 'restricted_reference' 没有显式 axis —— 我们用 portfolio name 匹配预定义清单
    （也接受 source 中的限定 axes 如 rp / restricted 如果未来出现）。
    """
    # 由于 DS 源里 R2024x 的 txt 是固定的 15 个名字，这里生成一个轴里所有含有 "Restricted Reference" 标记的项。
    # 一个简单实现：如果 source 里 items 有 data-something 标记 restricted —— 简化方式：把 brand 轴里被标记的列入。
    candidates: list[str] = []

    # 1. 探测每个 axis 是否有 "restricted"-like 标记（兼容未来 DS 增加标记）
    for ax_name, items in source["axes"].items():
        if "restrict" in ax_name.lower() or "restricted" in ax_name.lower():
            for it in items:
                name = (it.get("name") or "").strip()
                if name:
                    candidates.append(name)

    # 2. 固定关键字（兜底）
    KEYWORDS = [
        "SIMULIA Abaqus", "Q-Checker", "GEOVIA",
        "DELMIA Apriso", "3DEXCITE DELTAGEN", "Quintiq", "DELMIA Ortems",
    ]
    for it in source["items"]:
        name = (it.get("name") or "").strip()
        if any(k in name for k in KEYWORDS) and name not in candidates:
            candidates.append(name)

    if not candidates:
        return 0

    out = out_root / "Restricted Reference Portfolio.txt"
    out.write_text("\n".join(candidates) + "\n", encoding="utf-8")
    return 1


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="把 Portfolio Navigator JSON 拆分成 sourcefile 结构的 CSV")
    ap.add_argument("--source", required=True, type=Path, help="JSON 路径（extract_from_html.py 的输出）")
    ap.add_argument("--out", required=True, type=Path, help="输出根目录（会产生 sourcefile/ 子目录）")
    ap.add_argument("--skip-portfolio", action="store_true", help="不导出 Portfolio/")
    ap.add_argument("--skip-ipe", action="store_true", help="不导出 IPE/")
    args = ap.parse_args(argv)

    if not args.source.exists():
        print(f"[ERR] source 不存在: {args.source}", file=sys.stderr)
        return 1
    source = json.loads(args.source.read_text(encoding="utf-8"))

    args.out.mkdir(parents=True, exist_ok=True)
    src_root = args.out / "sourcefile"
    src_root.mkdir(parents=True, exist_ok=True)

    total = 0
    if not args.skip_portfolio:
        n = export_portfolio_csv(src_root, source,
                                 portfolio_axes=["portfolios", "portfolio_releases"])
        print(f"[OK] Portfolio/ 写 {n} 个 CSV")
        total += n
    if not args.skip_ipe:
        n = export_ipe_csv(src_root, source)
        print(f"[OK] IPE/ 写 {n} 个 CSV")
        total += n
    n = export_restricted_reference(src_root, source)
    if n:
        print(f"[OK] Restricted Reference Portfolio.txt 写了 {n} 个条目")

    print(f"[DONE] 全部 {total} 个 CSV 写到 {src_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
