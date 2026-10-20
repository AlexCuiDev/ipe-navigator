#!/usr/bin/env python
"""
serve.py — 一键本地 HTTP server，让 Chrome/Edge 能跑 interactive.html 的 JS

用法：
    python serve.py                # 用默认 8000 端口，serve samples/ 目录
    python serve.py 8080           # 自定义端口

然后浏览器打开：
    http://localhost:8000/interactive.html
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DIR = HERE / "samples"


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 8000
    serve_dir = DEFAULT_DIR if len(argv) < 2 else Path(argv[1])
    if not serve_dir.exists():
        print(f"[ERR] serve dir 不存在: {serve_dir}", file=sys.stderr)
        return 1

    # 切到目标目录，handler 用 SimpleHTTPRequestHandler
    os.chdir(str(serve_dir))

    class Handler(http.server.SimpleHTTPRequestHandler):
        # 关掉缓存，方便反复修改 HTML 调试
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()
        # 不要在控制台乱码 — 默认就行

    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}/interactive.html"
        print(f"[OK] serving {serve_dir} on port {port}")
        print(f"     open: {url}")
        print(f"     浏览器弹窗会自动开；如果没有，手动粘贴上面这行地址")
        print(f"     按 Ctrl+C 停止")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[bye]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
