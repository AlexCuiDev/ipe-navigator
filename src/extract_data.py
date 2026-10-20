"""
v6.2.0 slim data extraction.

Reads:
  - samples/r2026x_w31.2.json   (R2026x W31.2 source, parsed from HTML)

Writes:
  - dist/IPE-Navigator-v2.9/data/portfolio-r2026x.js  (JSONP wrapped slim)

v6.2.0 changes:
  - Removed baseline-w18.3.json dependency (was v6.1.0 compat delta tracking)
  - Removed _compat_changed / _compat_added / _compat_removed / _deleted_in_w31 flags
  - Slim is just W31.2 current state; "已删除" IPE detection is done at render time
    by comparing my-company.json triple (ip, ise, ipe_name) against slim items

Each slim item keeps:
  - id, name, axis_origin, compat_with, hooks, _orig_idx
"""
import json
import os
from pathlib import Path

ROOT = Path(r"D:\WORK\GiteeCode\DNE\IPE\tools\ipe-stats")
SRC = ROOT / "samples" / "r2026x_w31.2.json"
OUT_JS = ROOT / "dist" / "IPE-Navigator-v2.9" / "data" / "portfolio-r2026x.js"

OUT_JS.parent.mkdir(parents=True, exist_ok=True)

print(f"Loading source:    {SRC}")
data = json.load(open(SRC, encoding="utf-8"))
print(f"  ipe: {len(data['axes'].get('ipe', []))}, "
      f"ise: {len(data['axes'].get('ise', []))}, "
      f"pf: {len(data['axes'].get('portfolios', []))}, "
      f"items: {len(data.get('items', [])):,}")


def slim_source(source):
    """slim: keep only GA-tagged IPE/Portfolio/ISE/IndustryPortfolio items."""
    FOCUS_AXES = ("ipe", "portfolios", "industry_portfolios", "ise")
    items_by_id = {it["id"]: it for it in source["items"] if it.get("id")}
    ra_axis = source["axes"].get("role_availability", [])
    ga_ids = {r["id"] for r in ra_axis if (r.get("name") or "").upper() == "GA"}

    def _ga_kept(it):
        cw = set(it.get("compat_with") or [])
        return bool(cw & ga_ids)

    slim_axes = {
        "ipe":                 [it for it in source["axes"].get("ipe", []) if _ga_kept(it)],
        "portfolios":          [it for it in source["axes"].get("portfolios", []) if _ga_kept(it)],
        "industry_portfolios": [it for it in source["axes"].get("industry_portfolios", []) if _ga_kept(it)],
        "ise":                 [it for it in source["axes"].get("ise", []) if _ga_kept(it)],
    }
    focus_ids = set()
    for ax in FOCUS_AXES:
        for it in slim_axes[ax]:
            if it.get("id"):
                focus_ids.add(it["id"])
    for it in source["axes"].get("portfolio_releases", []):
        if it.get("id"):
            focus_ids.add(it["id"])
    focus_ids |= ga_ids
    for it in source["items"]:
        if not it.get("id"):
            continue
        ao = it.get("axis_origin")
        if ao in ("ipe", "portfolio", "portfolio_releases"):
            if _ga_kept(it):
                focus_ids.add(it["id"])
        elif ao == "croles":
            if not it.get("croline_group") or it["id"] != it.get("croline_group"):
                focus_ids.add(it["id"])

    slim_items = []
    for iid in focus_ids:
        it = items_by_id.get(iid)
        if not it:
            continue
        if it.get("axis_origin") == "croles":
            if it.get("croline_group") and it["id"] == it.get("croline_group"):
                continue

        # slim compat_with: only keep compat ids that are in focus_ids
        slim_compat = [c for c in (it.get("compat_with") or []) if c in focus_ids]

        slim_items.append({
            "id": iid,
            "name": it.get("name") or "",
            "axis_origin": it.get("axis_origin") or "",
            "compat_with": slim_compat,
            "hooks": it.get("hooks") or {},
            "_orig_idx": len(slim_items),
        })
    return {
        "meta":  source["meta"],
        "axes":  slim_axes,
        "items": slim_items,
        "prereqs": [],
    }


slim = slim_source(data)

print(f"\nSlim stats:")
print(f"  total: {len(slim['items']):,}")
print(f"  ipe: {len(slim['axes']['ipe'])}, "
      f"pf: {len(slim['axes']['portfolios'])}, "
      f"ise: {len(slim['axes']['ise'])}, "
      f"ip: {len(slim['axes']['industry_portfolios'])}, "
      f"role: {sum(1 for x in slim['items'] if x.get('axis_origin') == 'croles')}")

js_body = json.dumps(slim, ensure_ascii=False).replace("</", "<\\/")
output = (
    "/* IPE Navigator \u2014 R2026x slim data (v6.2.0)\n"
    " * Auto-loaded via <script src=\"data/portfolio-r2026x.js\"> in zip mode\n"
    " * EXE mode: served by main.py HTTP server (port 8765)\n"
    " * v6.2.0: pure W31.2 current state, no baseline comparison\n"
    f" * data source: {data['meta'].get('week_label', '?')}, items={len(slim['items'])}\n"
    " */\n"
    "window.PORTFOLIO_DATA = " + js_body + ";\n"
)

OUT_JS.write_text(output, encoding="utf-8")
print(f"\n[OK] {OUT_JS}")
print(f"     size: {len(output):,} chars  ({len(output) / 1024 / 1024:.2f} MB)")
print(f"     slim items: {len(slim['items']):,}")
