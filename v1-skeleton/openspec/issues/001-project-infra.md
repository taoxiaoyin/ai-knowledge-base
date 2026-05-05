# Issue #1: 项目基础设施：依赖、日志、配置

> 标签: `needs-triage` | 类型: AFK

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

搭建 AI 知识库项目的工程基础设施，确保三个 Agent 有统一的运行环境。

- 创建 `pyproject.toml`，用 uv 管理依赖（requests、python-dotenv、langgraph 等）
- 配置 logging 模块，所有 Agent 通过 `logging.getLogger(__name__)` 写日志，禁止 `print()`
- 创建 `.env.example` 模板（含 `GITHUB_TOKEN`、日志级别等配置项）
- 通过 `dotenv` 自动加载 `.env` 环境变量
- 创建 `knowledge/raw/` 和 `knowledge/articles/` 目录结构
- 配置 ruff（lint）+ black（format）+ pyright（strict type check）

## Acceptance criteria

- [ ] `pyproject.toml` 声明所有必要依赖，`uv sync` 成功
- [ ] `logging` 配置完成，Agent 代码中使用 `logger.info/error` 无 `print()`
- [ ] `.env.example` 文件存在，列出所有环境变量
- [ ] `.env` 在 `.gitignore` 中
- [ ] `knowledge/raw/` 和 `knowledge/articles/` 目录存在
- [ ] `ruff check .` 无错误
- [ ] `black --check .` 通过
- [ ] `pyright .` 类型检查通过

## Blocked by

无 — 可立即开始
