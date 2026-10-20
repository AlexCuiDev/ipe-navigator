#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_sample.py — 生成结构一致、内容脱敏的合成样本数据。

Generate a synthetic sample whose schema matches the real parsed output
exactly, but whose content is entirely placeholder. Lets anyone run the
full pipeline without access to Dassault internal data.

用法 / Usage:
    python examples/make_sample.py -o examples/sample_portfolio.json
    python examples/make_sample.py -o out.json --rows 200 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# 与真实解析产物完全一致的顶层列名 / Top-level keys, identical to real output
COLUMNS = [
    "Industry",
    "Segment",
    "Industry Solution Experience",
    "Industry Process Experience",
    "Roles / Products",
    "Role Availability",
    "Brand",
    "Portfolio",
    "Theme",
    "Discipline",
    "Pre-Req List",
    "Apps",
    "Media Names",
    "License Type",
    "DS Offering",
    "Item Type",
    "Version Long Name",
    "Release Origin",
]

PLACEHOLDER_POOLS = {
    "Industry": ["SAMPLE_INDUSTRY_A", "SAMPLE_INDUSTRY_B", "SAMPLE_INDUSTRY_C"],
    "Segment": ["SAMPLE_SEGMENT_1", "SAMPLE_SEGMENT_2"],
    "Industry Solution Experience": ["SAMPLE_ISE_X", "SAMPLE_ISE_Y", "SAMPLE_ISE_Z"],
    "Industry Process Experience": ["SAMPLE_IPE_001", "SAMPLE_IPE_002", "SAMPLE_IPE_003", "SAMPLE_IPE_004"],
    "Roles / Products": None,  # 动态生成 / generated dynamically
    "Role Availability": ["PublicCloud", "PrivateCloud", "DedicatedCloud", "On Premise"],
    "Brand": ["SAMPLE_BRAND_A", "SAMPLE_BRAND_B"],
    "Portfolio": ["SAMPLE_PORTFOLIO_1", "SAMPLE_PORTFOLIO_2", "SAMPLE_PORTFOLIO_3"],
    "Theme": ["SAMPLE_THEME_A", "SAMPLE_THEME_B"],
    "Discipline": ["SAMPLE_DISCIPLINE_A", "SAMPLE_DISCIPLINE_B"],
    "Pre-Req List": ["", "SAMPLE_IPE_001"],
    "Apps": ["SAMPLE_APP_A", "SAMPLE_APP_B", "SAMPLE_APP_C"],
    "Media Names": ["SAMPLE_MEDIA_A", "SAMPLE_MEDIA_B"],
    "License Type": ["SAMPLE_LICENSE_A", "SAMPLE_LICENSE_B"],
    "DS Offering": ["SAMPLE_OFFERING_A", "SAMPLE_OFFERING_B"],
    "Item Type": ["Role", "Product", "App"],
    "Version Long Name": ["SAMPLE_VERSION_2026x", "SAMPLE_VERSION_2024x"],
    "Release Origin": ["FD01", "FD02", "FD03"],
}


def build(rows: int, rng: random.Random) -> dict:
    data: dict[str, list] = {}
    for col in COLUMNS:
        data[col] = [col]  # 第一行为表头 / first row is the header, as in real output
        pool = PLACEHOLDER_POOLS.get(col)
        for i in range(rows):
            if pool is None:
                data[col].append(f"SAMPLE_ROLE_{i:04d}")
            else:
                data[col].append(rng.choice(pool))
    return data


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate a synthetic, fully anonymised sample.")
    ap.add_argument("-o", "--out", default="examples/sample_portfolio.json", help="output path")
    ap.add_argument("--rows", type=int, default=120, help="rows per column (default 120)")
    ap.add_argument("--seed", type=int, default=42, help="random seed")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    data = build(args.rows, rng)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out}  columns={len(COLUMNS)}  rows={args.rows}")
    print("All values are placeholders. No real data is included.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
