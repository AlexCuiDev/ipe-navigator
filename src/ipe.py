#!/usr/bin/env python
"""
ipe.py — ipe-stats 统一入口（跨 shell 友好版）

用法：
    python ipe.py help
    python ipe.py extract [html_path]
    python ipe.py list
    python ipe.py search "名字"
    python ipe.py add "名字"      # 或  python ipe.py add x12345
    python ipe.py remove "名字"
    python ipe.py clear
    python ipe.py calc [--hop N]
    python ipe.py diff old.json new.json
    python ipe.py init "公司名"

不需要记子命令的具体位置，所有默认路径都自动解析。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT_SOURCE = HERE / "samples" / "r2026x_w18.3.json"
DEFAULT_COMPANY = HERE / "company.json"
# 达索 Portfolio Navigator 导出的 HTML 属内部资料，不随仓库分发。
# 请通过 --source 传入自己的文件，或用 examples/make_sample.py 生成合成样本。
# The Portfolio Navigator HTML export is internal material and is not shipped
# with this repo. Pass your own via --source, or generate a synthetic sample.
DEFAULT_HTML = Path(os.environ.get("IPE_HTML", HERE.parent / "data" / "portfolio.html"))
DEFAULT_OUT = HERE / "samples" / "report.html"
DEFAULT_DIFF = HERE / "samples" / "diff.html"
DEFAULT_EXPORT = HERE / "samples" / "exported"
DEFAULT_INTERACTIVE = HERE / "samples" / "interactive.html"


def _py_run(args: list[str]) -> int:
    return subprocess.call([sys.executable, *args], cwd=str(HERE))


def cmd_help(_args: list[str]) -> int:
    print("""
ipe-stats — Portfolio Navigator 离线覆盖度分析工具

用法：
    python ipe.py help                                 看这个
    python ipe.py extract [html_path]                  解析 HTML -> JSON
    python ipe.py init ["公司名"]                      初始化公司配置
    python ipe.py list                                 看当前订阅的 portfolio
    python ipe.py search "名字"                        在 source 里搜 portfolio
    python ipe.py add "名字"                           按名字加 portfolio
    python ipe.py add x12345                           按 xN id 加 portfolio
    python ipe.py remove "名字"   或    python ipe.py remove x12345     删
    python ipe.py clear                                清空订阅
    python ipe.py calc [--hop N]                       算覆盖度 + 输出 HTML 报告
    python ipe.py interactive [out.html]              生成 interactive.html
                                                     （必须经 HTTP serve，不要双击 file://）
    python ipe.py serve [port]                         起本地 HTTP server
                                                     （Chrome/Edge 默认 file:// 禁 JS）
    python ipe.py export [out_dir] [--skip-portfolio]  导出 sourcefile CSV
                                                     （跟 DS 内部 IPESummary 期望格式一致）
    python ipe.py diff old.json new.json               版本对比

默认路径：
  HTML        = {HTML}
  source      = {src}
  company     = {cmp}
  报告        = {out}
  interactive = {inter}
  sourcefile  = {exp}
""".strip().format(
        HTML=DEFAULT_HTML, src=DEFAULT_SOURCE, cmp=DEFAULT_COMPANY,
        out=DEFAULT_OUT, inter=DEFAULT_INTERACTIVE, exp=DEFAULT_EXPORT,
    ))
    return 0


def cmd_extract(args: list[str]) -> int:
    html_path = Path(args[0]) if args else DEFAULT_HTML
    out_path  = Path(args[1]) if len(args) > 1 else DEFAULT_SOURCE
    return _py_run([str(HERE / "extract_from_html.py"), str(html_path), "-o", str(out_path)])


def cmd_init(args: list[str]) -> int:
    name = args[0] if args else "My Company"
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "init", "--name", name])


def cmd_list(_args: list[str]) -> int:
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "--source", str(DEFAULT_SOURCE), "list"])


def cmd_search(args: list[str]) -> int:
    if not args:
        print('[ERR] 用法: python ipe.py search "名字"', file=sys.stderr)
        return 1
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "--source", str(DEFAULT_SOURCE),
                    "search", *args, "--limit", "30"])


def cmd_add(args: list[str]) -> int:
    if not args:
        print('[ERR] 用法: python ipe.py add "名字"  或  python ipe.py add x12345', file=sys.stderr)
        return 1
    target = " ".join(args)
    # 区分 id (xN) 和名字
    if target.startswith("x") and target[1:].isdigit():
        return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "--source", str(DEFAULT_SOURCE),
                        "add", target])
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "--source", str(DEFAULT_SOURCE),
                    "add-name", target])


def cmd_remove(args: list[str]) -> int:
    if not args:
        print('[ERR] 用法: python ipe.py remove "名字" 或 python ipe.py remove x12345', file=sys.stderr)
        return 1
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "--source", str(DEFAULT_SOURCE),
                    "remove", *args])


def cmd_clear(_args: list[str]) -> int:
    return _py_run([str(HERE / "company.py"), "--config", str(DEFAULT_COMPANY), "clear"])


def cmd_calc(args: list[str]) -> int:
    rc = _py_run([str(HERE / "ipecalc.py"), "--source", str(DEFAULT_SOURCE),
                  "--company", str(DEFAULT_COMPANY), "--out", str(DEFAULT_OUT), *args])
    if rc == 0:
        print()
        print(f"[OK] 报告已生成: {DEFAULT_OUT}")
        print("     双击该 HTML 在浏览器打开，或拖到 Chrome / Edge / Firefox。")
    return rc


def cmd_diff(args: list[str]) -> int:
    if len(args) < 2:
        print('[ERR] 用法: python ipe.py diff old.json new.json', file=sys.stderr)
        return 1
    return _py_run([str(HERE / "diff_versions.py"), args[0], args[1], "--out", str(DEFAULT_DIFF)])


def cmd_export(args: list[str]) -> int:
    out_dir = Path(args[0]) if args else DEFAULT_EXPORT
    extras = []
    # 把 --skip-xxx 透传给 export_sourcefile.py
    for a in args[1:]:
        if a.startswith("--skip-"):
            extras.append(a)
    return _py_run([str(HERE / "export_sourcefile.py"),
                    "--source", str(DEFAULT_SOURCE),
                    "--out", str(out_dir),
                    *extras])


def cmd_interactive(args: list[str]) -> int:
    out_html = Path(args[0]) if args else DEFAULT_INTERACTIVE
    return _py_run([str(HERE / "build_ui.py"),
                    "--source", str(DEFAULT_SOURCE),
                    "--company", str(DEFAULT_COMPANY),
                    "--out", str(out_html)])


def cmd_serve(args: list[str]) -> int:
    """在一行启动本地 HTTP server，让浏览器能跑 JS 加载 interactive.html"""
    port = int(args[0]) if args else 8000
    return _py_run([str(HERE / "serve.py"), str(port), str(DEFAULT_INTERACTIVE.parent)])


CMDS = {
    "help":         cmd_help,
    "-h":           cmd_help,
    "--help":       cmd_help,
    "extract":      cmd_extract,
    "init":         cmd_init,
    "list":         cmd_list,
    "ls":           cmd_list,
    "search":       cmd_search,
    "find":         cmd_search,
    "add":          cmd_add,
    "remove":       cmd_remove,
    "rm":           cmd_remove,
    "del":          cmd_remove,
    "clear":        cmd_clear,
    "calc":         cmd_calc,
    "report":       cmd_calc,
    "export":       cmd_export,
    "interactive":  cmd_interactive,
    "ui":           cmd_interactive,
    "serve":        cmd_serve,
    "diff":         cmd_diff,
}


def main(argv: list[str]) -> int:
    if not argv:
        return cmd_help([])
    cmd = argv[0]
    if cmd not in CMDS:
        print(f"[ERR] unknown command: {cmd}", file=sys.stderr)
        return cmd_help([])
    return CMDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
