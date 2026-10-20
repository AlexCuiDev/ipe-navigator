# IPE Navigator Toolkit

> 达索 IPE 订阅覆盖度分析工具集 · 把人工 1 人天的申报管理压缩到 1 分钟以内
> A Python toolchain that turns a 1-person-day manual IPE reporting workflow into under a minute.

---

## 背景与痛点

达索的 IPE（Industry Process Experience）资源目录**每季度更新一次**。要回答"某个客户买的 portfolio 到底激活了哪些 IPE 和角色"，原流程需要人工翻阅 Portfolio Navigator 导出的离线 HTML，逐条比对订阅项与激活关系——**单次约 1 人天**。

原有替代方案是一个 Java 工具（`IPE Statistics_2024 W28.4`），但 HTML 模板每次升级它就失效，维护成本比手工还高。

Dassault's IPE resource catalogue **refreshes every quarter**. Answering "which IPEs and roles does this customer's portfolio actually activate?" meant manually reading the offline Portfolio Navigator HTML and cross-checking subscriptions against activation rules — **roughly one person-day per run**. The existing Java tool broke on every template refresh.

---

## 解决方案

13 个 Python 模块组成的分层工具集：

```
解析层  extract_from_html.py   HTML → 稳定 JSON Schema（业务层与模板解耦）
业务层  company.py / ipecalc.py  订阅管理、覆盖率计算、版本 diff
输出层  build_ui.py / export_sourcefile.py / serve.py
入口    ipe.py（统一 CLI）
```

关键设计是**稳定 JSON Schema 契约**：解析层输出的 Schema 不随达索 HTML 模板变化，因此模板升级不会波及业务逻辑——这正是旧 Java 工具做不到的地方。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 覆盖率计算 | BFS 沿 `compat_with` 关系求 closure 跳数，算出 portfolio 实际激活的 IPE / 角色集合 |
| 版本对比 | R2024x ↔ R2026x 差异自动 diff，输出可读的版本变更报告 |
| 可交互报告 | 生成带搜索、高亮、勾选的 HTML 报告 |
| CSV 导出 | 镜像达索内部 IPESummary 格式，可直接导入 |
| 桌面交付 | PyInstaller 打包为 `.exe`，供非技术同事使用 |

---

## 快速开始

```bash
pip install -r requirements.txt

# 1. 生成一份合成样本（无需任何真实数据即可体验完整流程）
python examples/make_sample.py -o examples/sample_portfolio.json

# 2. 查看全部命令
python src/ipe.py help

# 3. 用真实数据：从 Portfolio Navigator 导出 HTML 后解析
python src/ipe.py extract --source <你的 HTML> --out data/
python src/ipe.py report
python src/ipe.py interactive && python src/ipe.py serve 8000
```

---

## 效果

| 指标 | 之前 | 之后 |
|------|------|------|
| 单次分析耗时 | ~1 人天 | < 1 分钟（约 480×） |
| 模板升级后可用性 | Java 工具失效 | 解析层解耦，无需改码 |
| 使用者 | 需工程背景 | 打包 .exe，非技术同事可自助 |

---

## 数据说明（重要）

**本仓库不包含任何达索系统内部数据。**

工具的输入是达索 Portfolio Navigator 导出的 HTML，属内部资料，需自备。为了让任何人都能跑通完整流程，仓库提供了 `examples/make_sample.py`——它生成一份**字段结构与真实数据完全一致、但内容全部为占位符**的合成样本。

This repository contains **no Dassault Systèmes internal data**. The input (Portfolio Navigator HTML export) is proprietary and must be supplied by the user. `examples/make_sample.py` generates a synthetic sample with an identical schema but fully placeholder content, so the toolchain can be exercised end to end without exposing anything real.

---

## 依赖

仅标准库 + 三个第三方包：`beautifulsoup4`、`lxml`、`jinja2`。不依赖 pandas / openpyxl，因此打包体积小。

---

## License

MIT
