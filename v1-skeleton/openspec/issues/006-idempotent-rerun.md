# Issue #6: 重跑策略：幂等性与增量追加

> 标签: `needs-triage` | 类型: AFK | 依赖: #5

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现流水线重跑幂等性：同一天重复执行不产生重复数据，增量追加而非覆盖。

**Collector 幂等**：
- 写入前检查 `knowledge/raw/github-trending-{date}.json` 是否存在
- 存在时读取现有条目，按 `url` 去重后合并，追加新条目
- 不删除已有条目（即使是低相关度条目，由 Analyzer/Organizer 决定去留）

**Organizer 幂等**：
- 写入前检查 `knowledge/articles/{date}-ai-daily.md` 是否存在
- 存在时读取现有内容，按 `url` 判重，只追加新条目
- 更新概览统计数字

**索引幂等**：
- 更新 `index.md` 时，如果当天记录已存在则更新统计数据，不重复添加行

## Acceptance criteria

- [ ] 同一天 Collector 重复执行，raw JSON 不产生重复条目（按 url）
- [ ] 同一天 Organizer 重复执行，日报不产生重复条目（按 url）
- [ ] 已有条目的分析字段不被覆盖（Analyzer 不重复分析已有产物）
- [ ] `index.md` 每天只有一行记录
- [ ] 重跑日志记录"跳过 N 条已有条目，新增 M 条"

## Blocked by

- #5: 流水线编排（幂等性在编排层实现）
