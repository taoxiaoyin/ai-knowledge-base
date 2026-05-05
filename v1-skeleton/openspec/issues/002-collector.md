# Issue #2: Collector：抓取 GitHub Trending Top 50 并过滤

> 标签: `needs-triage` | 类型: AFK | 依赖: #1

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现 Collector Agent，从 GitHub Search API 抓取 AI/LLM/Agent 相关热门仓库，过滤后存入 `knowledge/raw/github-trending-{date}.json`。

- 调用 `GET /search/repositories` 搜索关键词 `AI OR LLM OR agent OR RAG OR MCP`，时间窗口 7 天
- 过滤条件：`stargazers_count >= 20`、`fork == false`、有 `description`、非 awesome-list
- 提取字段：`title`、`url`、`source`、`popularity`、`language`、`topics`、`summary`（中文翻译 description）
- Top 10 仓库额外获取 README 前 500 字存入 `readme_excerpt`
- 输出 JSON 按 `popularity` 降序排列
- 使用 `GITHUB_TOKEN` 环境变量认证，未认证时报错
- API 限流（403/429）时读取 `X-RateLimit-Reset` 等待后重试，最多 3 次

## Acceptance criteria

- [ ] 成功调用 GitHub Search API 并获取 ≥ 15 条仓库
- [ ] 返回的每条条目含 `title`、`url`、`source`、`popularity`、`summary` 五字段，全部非空
- [ ] 输出保存到 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`，格式正确
- [ ] 条目按 `popularity` 降序排列
- [ ] 无重复条目（同 `url` 不出现两次）
- [ ] 限流时自动重试，不崩溃
- [ ] 日志记录采集数量、过滤数量、失败原因
- [ ] 仅使用 Read / Grep / Glob / WebFetch 工具，无 Write / Edit / Bash

## Blocked by

- #1: 项目基础设施（需要依赖安装和目录结构就绪）
