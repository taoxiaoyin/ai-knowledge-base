---
name: github-trending
description: 从 GitHub 采集 AI/LLM/Agent 领域的 Trending 热门开源仓库，自动过滤、去重、生成中文技术摘要，输出结构化 JSON。Use when user asks to collect/fetch/pull/search/scan/grab/get/retrieve/check/explore/look at Github trending/hot/popular/top repositories, AI/LLM/Agent repos on Github, Github star ranking, or 采集/获取/抓取/拉取/搜索/扫描/查看/浏览/检索 GitHub 热门/趋势/Trending/热点/排行 的 AI/LLM/Agent/大模型 相关 开源项目/仓库/代码库。Triggers on: "github trending", "github 趋势", "github 热门", "GitHub 热门项目", "采集 GitHub", "获取 GitHub", "github repos", "github 仓库", "github star", "github AI", "trending repos", "hot repos github", "daily github", "今日 github", "github trending today", "github 排行", "github 每日".
allowed-tools: Read, Grep, Glob, WebFetch
---

# GitHub Trending 采集技能

## 快速开始

用户发出采集请求后，按以下 6 步执行：

1. **搜索** — 调用 GitHub Search API（`GET /search/repositories`）
   - 查询条件：`q=ai OR llm OR agent OR rag OR mcp created:>{7天前}`
   - 排序：`sort=stars&order=desc`，`per_page=30`
   - 请求头：`Authorization: Bearer ${GITHUB_TOKEN}`

2. **过滤纳入** — 任一条件满足则保留：
   - `topics` 含 `ai`、`llm`、`agent`、`rag`、`mcp`、`large-language-model`
   - `description` 含 "AI"、"LLM"、"Agent"、"RAG"、"MCP"（大小写不敏感）
   - `language` 为 Python/TypeScript/Rust 且 topics 含 `machine-learning`、`deep-learning`

3. **过滤排除** — 任一条件满足则丢弃：
   - `topics` 含 `awesome-list`、`awesome`
   - `name` 匹配 `awesome-*` 或 `*-awesome`
   - `fork: true`

4. **去重** — 按 `name`（`owner/repo`）去重；若当日 JSON 已存在，读取后合并

5. **摘要** — 每条生成 50-150 中文字符：
   - 公式：`项目名` + `做什么` + `为什么值得关注`
   - 技术术语保留英文（RAG、MCP、Fine-tuning 等）
   - 避免空洞形容词，用具体信息替代

6. **输出** — 按 `stars` 降序取 Top 15，写入 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`

## 输出格式

```json
{
  "source": "github-trending",
  "skill": "github-trending",
  "collected_at": "2026-05-03T10:00:00Z",
  "items": [
    {
      "name": "owner/repo-name",
      "url": "https://github.com/owner/repo-name",
      "summary": "MCP 协议在浏览器端的轻量实现，让网页应用直接调用本地 LLM 工具链。",
      "stars": 3200,
      "language": "Python",
      "topics": ["agent-framework", "llm", "multi-agent"]
    }
  ]
}
```

## 容错策略

| 场景 | 处理 |
|------|------|
| API 限流 | 读取 `X-RateLimit-Reset` 计算等待时间，报告用户 |
| 网络超时（>30s） | 重试 ≤3 次，间隔 5s；全失败记录到 `errors-{date}.json` |
| Token 未配置 | 报错提示检查 `.env` 中的 `GITHUB_TOKEN` |
| 过滤后不足 15 条 | 全部输出，日志记录实际数量；触发补齐数据源 |
