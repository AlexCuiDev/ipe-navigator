"""
company.py — 公司订阅管理 CLI (v2 schema)

管理 4 个集合：
  - portfolios:          公司订阅的 portfolio
  - my_ipe:              公司申报的 IPE
  - my_role:             公司申报的 role item id
  - restricted_reference: Restricted Reference Portfolio 列表

用法：
    python company.py init
    python company.py list                       # 列出所有
    python company.py list-portfolios
    python company.py list-ipe
    python company.py list-role
    python company.py list-restricted
    python company.py search "CATIA"             # 在 source 里搜任意 axis
    python company.py add "CATIA Composer"       # 默认进 portfolios
    python company.py add-ipe "01-Asset Commissioning"
    python company.py add-role "C4P-C"
    python company.py add-restricted "SIMULIA Abaqus Unified FEA"
    python company.py remove "CATIA Composer"
    python company.py clear
    python company.py show
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT_CONFIG = HERE / "company.json"
DEFAULT_SOURCE = HERE / "samples" / "r2026x_w18.3.json"


# ---------------------------------------------------------------------------
# Config schema
# ---------------------------------------------------------------------------
def empty_config(company_name: str = "My Company") -> dict:
    return {
        "schema_version":         "2.0",
        "company":                company_name,
        "portfolios":             [],
        "my_ipe":                 [],
        "my_role":                [],
        "restricted_reference":   [],
        "notes":                  "",
    }


def load_config(path: Path) -> dict:
    if not path.exists():
        return empty_config()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    # 升级老 schema（v1 没有 my_ipe/my_role/restricted_reference）
    if "my_ipe" not in cfg:               cfg["my_ipe"] = []
    if "my_role" not in cfg:              cfg["my_role"] = []
    if "restricted_reference" not in cfg: cfg["restricted_reference"] = []
    if "schema_version" not in cfg:       cfg["schema_version"] = "2.0"
    return cfg


def save_config(path: Path, cfg: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------
def load_source(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[ERR] source JSON 不存在：{path}\n      先跑 extract_from_html.py 生成它")
    return json.loads(path.read_text(encoding="utf-8"))


def all_portfolios(source: dict) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for axis_name in ("portfolios", "portfolio_releases"):
        for it in source["axes"].get(axis_name, []):
            if not it["id"] or it["id"] in seen:
                continue
            seen.add(it["id"])
            out.append({"id": it["id"], "name": it.get("name") or "", "_axis": axis_name})
    return out


def all_ipes(source: dict) -> list[dict]:
    return [
        {"id": it["id"], "name": it.get("name") or ""}
        for it in source["axes"].get("ipe", []) if it.get("id")
    ]


def all_roles(source: dict) -> list[dict]:
    """从 crolist 抽 role item id（按 name 短字符 = trigram 优先）"""
    out: list[dict] = []
    seen: set[str] = set()
    for it in source["items"]:
        if (it.get("axis_origin") == "croles") and it.get("id") and it["id"] not in seen:
            seen.add(it["id"])
            out.append({"id": it["id"], "name": it.get("name") or ""})
    return out


def find_by_id(items: list[dict], x_id: str) -> dict | None:
    for p in items:
        if p["id"] == x_id:
            return p
    return None


def find_by_name(items: list[dict], needle: str, fuzzy: bool = False) -> list[dict]:
    needle_l = needle.lower()
    exact, contains = [], []
    for p in items:
        n = (p.get("name") or "").lower()
        if n == needle_l:           exact.append(p)
        elif fuzzy and needle_l in n: contains.append(p)
    return exact or contains


# ---------------------------------------------------------------------------
# Generic add helper
# ---------------------------------------------------------------------------
def _add_to(cfg: dict, key: str, candidate: dict) -> bool:
    """把 candidate = {id, name} 追加到 cfg[key]，已存在则跳过"""
    bucket = cfg.setdefault(key, [])
    if any(e.get("id") == candidate["id"] for e in bucket):
        print(f"(已经存在) {candidate['id']} -> {candidate['name']}")
        return True
    bucket.append({"id": candidate["id"], "name": candidate.get("name") or ""})
    print(f"[OK] {key} + {candidate['id']} -> {candidate['name']}")
    return True


def _add_by_id_or_name(cfg: dict, key: str, candidates: list[dict],
                       target: str, fuzzy: bool) -> bool:
    """从 candidates 找匹配 target（id 或 name）追加到 cfg[key]"""
    if not candidates:
        print(f"[ERR] source 里没有这个 axis 的数据", file=sys.stderr)
        return False
    # id 优先
    if target.startswith("x") and target[1:].isdigit():
        ent = find_by_id(candidates, target)
        if not ent:
            print(f"[ERR] 在 source 找不到 id={target}", file=sys.stderr)
            return False
        return _add_to(cfg, key, ent)
    # name
    matches = find_by_name(candidates, target, fuzzy=False)
    if not matches:
        matches = find_by_name(candidates, target, fuzzy=True)
        if not matches:
            print(f"[ERR] 找不到名字匹配 {target!r}", file=sys.stderr)
            return False
        if len(matches) > 1:
            short = [c for c in matches if target.lower() in (c["name"] or "").lower()]
            if len(short) > 1:
                print(f"[ERR] {target!r} 匹配多个：" + ", ".join(c["id"] for c in short[:5]))
                return False
            matches = short
    return _add_to(cfg, key, matches[0])


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_init(args) -> int:
    cfg = empty_config(company_name=args.name)
    save_config(args.config, cfg)
    print(f"[OK] 初始化 v2 配置 -> {args.config}")
    print(f"     公司名 = {cfg['company']!r}")
    return 0


def _list_bucket(cfg: dict, key: str, name_label: str, ids_by_id: dict) -> None:
    items = cfg.get(key, [])
    print(f"  {name_label}（共 {len(items)} 个）")
    if not items:
        return
    print(f"    {'ID':<10}  {'名称':<60}")
    print(f"    {'-'*10}  {'-'*60}")
    for ent in items:
        meta = ids_by_id.get(ent["id"], {})
        name = ent.get("name") or meta.get("name") or "(未知名称)"
        print(f"    {ent['id']:<10}  {name[:60]}")


def cmd_list(args) -> int:
    cfg = load_config(args.config)
    src = load_source(args.source)
    p_by_id = {p["id"]: p for p in all_portfolios(src)}
    ipe_by_id = {p["id"]: p for p in all_ipes(src)}
    role_by_id = {p["id"]: p for p in all_roles(src)}

    print(f"公司：{cfg.get('company')}")
    _list_bucket(cfg, "portfolios",           "Portfolio (订阅)",  p_by_id)
    _list_bucket(cfg, "my_ipe",               "My IPE (申报)",     ipe_by_id)
    _list_bucket(cfg, "my_role",              "My Role (申报)",    role_by_id)
    _list_bucket(cfg, "restricted_reference", "Restricted Ref",    {})
    return 0


def cmd_list_one(key: str, name_label: str):
    def fn(args) -> int:
        cfg = load_config(args.config)
        src = load_source(args.source)
        if key == "portfolios":
            ids = {p["id"]: p for p in all_portfolios(src)}
        elif key == "my_ipe":
            ids = {p["id"]: p for p in all_ipes(src)}
        elif key == "my_role":
            ids = {p["id"]: p for p in all_roles(src)}
        else:
            ids = {}
        _list_bucket(cfg, key, name_label, ids)
        return 0
    return fn


def cmd_search(args) -> int:
    src = load_source(args.source)
    all_items = all_portfolios(src) + all_ipes(src) + all_roles(src)
    # 按 axis 顺序：先看 portfolios
    found = []
    for pool in (all_portfolios(src), all_ipes(src), all_roles(src)):
        found.extend([("portfolio", x) for x in find_by_name(pool, args.needle, fuzzy=not args.exact)])
        if found:
            break
    found = list({f[1]["id"]: f for f in found}.values())  # dedup
    if not found:
        print(f"(没找到 {args.needle!r})")
        return 0
    print(f"找到 {len(found)} 个：")
    for kind, p in found[:args.limit]:
        print(f"  [{kind:10}] {p['id']:<10}  {p['name'][:60]}")
    if len(found) > args.limit:
        print(f"  ... 还有 {len(found)-args.limit} 个")
    return 0


def cmd_add(args) -> int:
    """默认加 portfolios（向后兼容）"""
    cfg = load_config(args.config)
    src = load_source(args.source)
    if not _add_by_id_or_name(cfg, "portfolios", all_portfolios(src), args.target, fuzzy=True):
        return 1
    save_config(args.config, cfg)
    return 0


def cmd_add_typed(key: str):
    def fn(args) -> int:
        cfg = load_config(args.config)
        src = load_source(args.source)
        if key == "portfolios":
            cand = all_portfolios(src)
        elif key == "my_ipe":
            cand = all_ipes(src)
        elif key == "my_role":
            cand = all_roles(src)
        elif key == "restricted_reference":
            # restricted_reference 是名字列表（不是 ID 列表）
            # 直接把 target 当 name 加入（去重）
            existing = cfg.get(key, [])
            if args.target in existing:
                print(f"(已经存在) {args.target}")
            else:
                cfg.setdefault(key, []).append(args.target)
                print(f"[OK] restricted_reference + {args.target}")
            save_config(args.config, cfg)
            return 0
        else:
            print(f"[ERR] 未知 key {key}", file=sys.stderr); return 1
        if not _add_by_id_or_name(cfg, key, cand, args.target, fuzzy=True):
            return 1
        save_config(args.config, cfg)
        return 0
    return fn


def cmd_remove(args) -> int:
    """从 4 个 list 里同时找 target 并删"""
    cfg = load_config(args.config)
    target = args.target
    removed_total = 0
    for key in ("portfolios", "my_ipe", "my_role"):
        new = []
        for ent in cfg.get(key, []):
            if ent["id"] == target or (ent.get("name") or "").lower() == target.lower():
                removed_total += 1
                print(f"[OK] {key} - {ent['id']} <- {ent.get('name','')}")
            else:
                new.append(ent)
        cfg[key] = new
    # restricted_reference 是 plain name list
    if target in cfg.get("restricted_reference", []):
        cfg["restricted_reference"] = [x for x in cfg["restricted_reference"] if x != target]
        print(f"[OK] restricted_reference - {target}")
        removed_total += 1
    if removed_total == 0:
        print(f"(没匹配 {target!r})")
        return 0
    save_config(args.config, cfg)
    return 0


def cmd_clear(args) -> int:
    cfg = load_config(args.config)
    if args.target == "all":
        for k in ("portfolios", "my_ipe", "my_role", "restricted_reference"):
            cfg[k] = []
        save_config(args.config, cfg)
        print("[OK] 清空所有 4 个 list")
    else:
        if args.target not in ("portfolios","my_ipe","my_role","restricted_reference"):
            print(f"[ERR] 未知 kind: {args.target}", file=sys.stderr); return 1
        cfg[args.target] = []
        save_config(args.config, cfg)
        print(f"[OK] 清空 {args.target}")
    return 0


def cmd_show(args) -> int:
    cfg = load_config(args.config)
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# arg parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="公司订阅管理 CLI (v2 schema)")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init"); p.add_argument("--name", default="My Company")
    p.set_defaults(func=cmd_init)

    sub.add_parser("list", help="列出全部 4 个 list").set_defaults(func=cmd_list)
    sub.add_parser("list-portfolios", help="只列 portfolios").set_defaults(func=cmd_list_one("portfolios", "Portfolio (订阅)"))
    sub.add_parser("list-ipe",         help="只列 my_ipe").set_defaults(func=cmd_list_one("my_ipe", "My IPE (申报)"))
    sub.add_parser("list-role",        help="只列 my_role").set_defaults(func=cmd_list_one("my_role", "My Role (申报)"))
    sub.add_parser("list-restricted",  help="只列 restricted_reference").set_defaults(func=cmd_list_one("restricted_reference", "Restricted Reference"))

    s = sub.add_parser("search")
    s.add_argument("needle"); s.add_argument("--exact", action="store_true"); s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    a = sub.add_parser("add"); a.add_argument("target"); a.set_defaults(func=cmd_add)

    p = sub.add_parser("add-ipe");           p.add_argument("target"); p.set_defaults(func=cmd_add_typed("my_ipe"))
    p = sub.add_parser("add-role");          p.add_argument("target"); p.set_defaults(func=cmd_add_typed("my_role"))
    p = sub.add_parser("add-restricted");    p.add_argument("target"); p.set_defaults(func=cmd_add_typed("restricted_reference"))

    r = sub.add_parser("remove"); r.add_argument("target"); r.set_defaults(func=cmd_remove)

    c = sub.add_parser("clear")
    c.add_argument("target", nargs="?", default="all",
                   help="portfolios|my_ipe|my_role|restricted_reference|all (默认 all)")
    c.set_defaults(func=cmd_clear)

    sub.add_parser("show").set_defaults(func=cmd_show)

    return ap


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
