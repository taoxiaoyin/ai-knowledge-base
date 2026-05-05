# Issue #4: Organizer：读取已标注数据、生成 Markdown 日报

> 标签: `needs-triage` | 类型: AFK | 依赖: #1, #3

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现 Organizer Agent，读取 Analyzer 分析后的 raw JSON，过滤低相关度条目，按技术领域标签分组，生成结构化 Markdown 日报。

**过滤**：
- 丢弃 `relevance == "low"` 的条目
- 丢弃缺少必填字段的条目
- 丢弃 `tags` 数量 < 3 的条目
- 所有丢弃记录写入 `knowledge/raw/filtered-{date}.json`

**分组**：按技术领域标签分组（`agent-framework` → "🤖 Agent 框架"，`rag` → "🔍 RAG"，`large-language-model` → "🧠 大语言模型" 等）

**Markdown 模板**：含标题、概览统计、分组展示（每条目含链接、Star 数、语言、标签、note）、页脚

**输出**：
- 日报：`knowledge/articles/{date}-ai-daily.md`
- 索引：`knowledge/articles/index.md`（表格汇总所有日报）

## Acceptance criteria

- [ ] 成功读取 Analyzer 处理后的 raw JSON
- [ ] `relevance: low` 的条目不出现在日报中
- [ ] 过滤日志完整，每条丢弃有 `title` 和 `reason`
- [ ] 日报 Markdown 格式正确，可正常渲染
- [ ] 分组与条目标签匹配，无错误归类
- [ ] 概览统计数字与实际条目数一致
- [ ] `index.md` 表格统计数据准确
- [ ] 文件编码 UTF-8
- [ ] 使用 Read / Grep / Glob / Write / Edit 工具，不使用 WebFetch / Bash
- [ ] 不修改 `knowledge/raw/` 中的任何文件（只读）

## Blocked by

- #1: 项目基础设施
- #3: Analyzer（需要已标注的 raw 数据）
