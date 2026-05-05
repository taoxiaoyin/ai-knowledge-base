# Issue #3: Analyzer：读取 raw 数据、3 维度打标签

> 标签: `needs-triage` | 类型: AFK | 依赖: #1, #2

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现 Analyzer Agent，读取 Collector 产出的 raw JSON，为每个条目打 3 维度标签并评估相关度。

**3 维度标签**：
- 技术领域标签（必选 1 个）：`large-language-model`、`agent-framework`、`rag`、`mcp`、`fine-tuning`、`multi-agent` 等
- 技术栈标签（必选 1-2 个）：`python`、`openai`、`langchain`、`transformers` 等
- 应用场景标签（可选 1-2 个）：`developer-tool`、`chatbot`、`workflow-automation` 等

**相关度评估**：
- `high`：直接涉及 LLM/Agent/RAG/MCP 核心技术
- `medium`：AI 相关但偏应用层
- `low`：与 AI 关联度弱

**输出**：在原条目追加 `tags`（3-5 个）、`relevance`（high/medium/low）、`note`（一句中文价值说明）、`analyzed_at`

无 `readme_excerpt` 的条目，用 WebFetch 访问仓库 README 辅助判断。

## Acceptance criteria

- [ ] 成功读取 `knowledge/raw/github-trending-{date}.json` 中的所有条目
- [ ] 每个条目含 `tags` 数组（3-5 个标签）
- [ ] 所有标签来自标签体系或遵循英文小写连字符规范
- [ ] 每个条目含 `relevance` 字段（high / medium / low）
- [ ] 每个条目含 `note` 字段（一句中文，20-40 字）
- [ ] `relevance: high` 的条目至少包含 1 个核心技术领域标签
- [ ] 标签基于仓库实际 topics/description/README，不编造
- [ ] `analyzed_at` 为 ISO 8601 格式
- [ ] 仅使用 Read / Grep / Glob / WebFetch 工具，无 Write / Edit / Bash

## Blocked by

- #1: 项目基础设施（需要依赖和目录结构）
- #2: Collector（需要 raw 数据作为输入）
