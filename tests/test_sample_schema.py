#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Smoke test: 校验 make_sample.py 产出的合成数据结构与真实解析产物一致。
Verifies the synthetic sample has the same schema as real parsed output.

    python tests/test_sample_schema.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COLUMNS = {
    "Industry", "Segment", "Industry Solution Experience",
    "Industry Process Experience", "Roles / Products", "Role Availability",
    "Brand", "Portfolio", "Theme", "Discipline", "Pre-Req List", "Apps",
    "Media Names", "License Type", "DS Offering", "Item Type",
    "Version Long Name", "Release Origin",
}


def main() -> int:
    import json

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sample.json"
        r = subprocess.run(
            [sys.executable, str(ROOT / "examples" / "make_sample.py"), "-o", str(out), "--rows", "20"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print("FAIL: make_sample.py exited non-zero")
            print(r.stderr)
            return 1

        data = json.loads(out.read_text(encoding="utf-8"))

    if set(data.keys()) != EXPECTED_COLUMNS:
        missing = EXPECTED_COLUMNS - set(data.keys())
        extra = set(data.keys()) - EXPECTED_COLUMNS
        print(f"FAIL: column mismatch. missing={missing} extra={extra}")
        return 1

    lengths = {len(v) for v in data.values()}
    if len(lengths) != 1:
        print(f"FAIL: columns have inconsistent lengths: {lengths}")
        return 1

    for col, values in data.items():
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            print(f"FAIL: column {col!r} is not list[str]")
            return 1

    print(f"PASS: {len(data)} columns, {lengths.pop()} rows each, all list[str]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
