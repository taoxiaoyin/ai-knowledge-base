---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools: Read, Grep, Glob, WebFetch
---

# GitHub Trending 采集技能

## 使用场景

当用户要求从 GitHub 采集 AI/LLM/Agent 相关的热门仓库时，自动激活此技能。适用于每日自动化采集流水线，或手动触发采集特定日期/领域的 GitHub 热门项目。

## 执行步骤

### 第 1 步：搜索热门仓库

使用 GitHub Search API 搜索最近一周内创建的 AI/LLM/Agent 相关仓库：

```
GET https://api.github.com/search/repositories
```

**查询参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| `q` | `ai OR llm OR agent OR rag OR mcp created:>{7天前}` | 搜索关键词 + 时间过滤，`{7天前}` 替换为 ISO 8601 日期 |
| `sort` | `stars` | 按 Star 数降序排列 |
| `order` | `desc` | 降序 |
| `per_page` | `30` | 每页 30 条，为后续过滤留余量 |

**请求头**：

```
Accept: application/vnd.github.v3+json
Authorization: Bearer ${GITHUB_TOKEN}
```

> `GITHUB_TOKEN` 从环境变量读取，用于提升 API 限额（未认证：60 次/小时，已认证：5000 次/小时）。

### 第 2 步：提取信息

对 API 返回的每个仓库，提取以下字段：

| 字段 | 来源 | 说明 |
|------|------|------|
| `name` | `full_name` | 仓库全名，格式 `owner/repo` |
| `url` | `html_url` | 仓库链接 |
| `description` | `description` | 仓库描述（英文原版） |
| `stars` | `stargazers_count` | Star 数量 |
| `language` | `language` | 主要编程语言 |
| `topics` | `topics` | 仓库 topics 数组 |
| `created_at` | `created_at` | 创建时间 |
| `pushed_at` | `pushed_at` | 最近推送时间 |

### 第 3 步：过滤

对搜索结果逐一检查，符合以下任一条件则**纳入**：

- `topics` 包含 `ai`、`llm`、`agent`、`large-language-model`、`rag`、`mcp` 中至少一个
- `description` 中出现 "AI"、"LLM"、"Agent"、"RAG"、"MCP" 关键词（大小写不敏感）
- `language` 为 `Python`、`TypeScript`、`Rust`、`Jupyter Notebook` 且 `topics` 包含 `machine-learning`、`deep-learning`、`nlp` 之一

符合以下任一条件则**排除**：

- `topics` 包含 `awesome-list`、`awesome`（纯链接集合）
- `description` 以 `A curated list of`、`Curated list of`、`:rainbow:` 开头（Awesome 特征）
- `name` 匹配 `awesome-*` 或 `*-awesome` 模式
- `fork: true`（fork 仓库）

### 第 4 步：去重

- 按 `name`（`owner/repo`）去重，同名仓库只保留一条
- 如果当日 `knowledge/raw/github-trending-{YYYY-MM-DD}.json` 已存在，读取后合并，相同 `name` 的条目以新数据覆盖

### 第 5 步：撰写中文摘要

对每个通过过滤的条目，按以下公式生成中文摘要：

**公式**：`项目名` + `做什么` + `为什么值得关注`

- **项目名**：仓库名称（英文原文）
- **做什么**：基于 `description`，用 1-2 句说明核心功能/解决的问题
- **为什么值得关注**：结合 `stars`、`topics`、创建时间，给出对 AI 工程师的实际价值判断

**写作要求**：

- 摘要长度 50-150 个中文字符
- 技术术语保留英文原文（如 RAG、MCP、Fine-tuning）
- 避免空洞形容词（"强大的"、"创新的"），用具体信息替代
- 第一句直接点明核心，不用"本项目是…"等模板开头

**示例**：

> MCP 协议在浏览器端的轻量实现，让网页应用直接调用本地 LLM 工具链。
> 采用 Wasm 沙箱隔离，2 周 3.2K Star，对构建浏览器 Agent 的团队有直接参考价值。

### 第 6 步：排序取 Top 15

- 按 `stars` 降序排列
- 取前 15 条作为最终输出
- 如果过滤后不足 15 条，全部输出并在日志中记录实际数量

### 第 7 步：输出 JSON

将整理后的结果写入 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`：

- 文件路径：`knowledge/raw/github-trending-{YYYY-MM-DD}.json`（日期替换为当天）
- 2 空格缩进，UTF-8 编码
- 写入前检查文件是否已存在：
  - 不存在 → 直接写入
  - 已存在 → 读取 → 按 `name` 合并去重 → 覆盖写入

## 注意事项

1. **API 限流**：未认证的 IP 每小时 60 次请求。必须在请求头中携带 `GITHUB_TOKEN`。如果收到 `403` 且 `X-RateLimit-Remaining: 0`，读取 `X-RateLimit-Reset` 计算等待时间并报告用户。
2. **网络容错**：单次请求超时 30 秒。超时自动重试，最多 3 次，重试间隔 5 秒。3 次失败后记录错误到 `knowledge/raw/errors-{YYYY-MM-DD}.json`，不阻塞后续流程。
3. **幂等性**：同一天重复运行不产生重复条目。通过读取已有文件按 `name` 去重实现。
4. **Token 安全**：`GITHUB_TOKEN` 必须从环境变量读取，禁止硬编码。
5. **语言约定**：JSON 键名使用英文，摘要字段使用中文。

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
      "summary": "中文摘要，50-150中文字符...",
      "stars": 3200,
      "language": "Python",
      "topics": ["agent-framework", "llm", "multi-agent"]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 固定值 `"github-trending"` |
| `skill` | string | 固定值 `"github-trending"` |
| `collected_at` | string | 采集时间，ISO 8601 格式（`YYYY-MM-DDTHH:mm:ssZ`） |
| `items` | array | 仓库列表，按 `stars` 降序，最多 15 条 |
| `items[].name` | string | 仓库全名，格式 `owner/repo` |
| `items[].url` | string | GitHub 仓库链接 |
| `items[].summary` | string | 中文技术摘要，50-150 中文字符 |
| `items[].stars` | number | Star 数量 |
| `items[].language` | string | 主要编程语言 |
| `items[].topics` | string[] | GitHub topics 数组 |
