# Issue #5: 流水线编排：串行调度 + 上游失败处理 + 数据传递

> 标签: `needs-triage` | 类型: AFK | 依赖: #2, #3, #4

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现流水线编排模块，将 Collector → Analyzer → Organizer 串行串联，并处理上游失败和数据传递。

**串行调度**：
- 按 Collector → Analyzer → Organizer 顺序执行
- 每个阶段完成后检查产出文件是否存在、格式是否合法
- 前一阶段失败时，后续阶段记录原因并跳过（不崩溃）

**上游失败策略**：
- Collector 失败 → Analyzer 和 Organizer 跳过，写错误日志
- Analyzer 失败 → Organizer 跳过，写错误日志
- 每个阶段的失败原因写入 `knowledge/raw/errors-{date}.json`

**数据传递**：
- 通过文件系统传递：Collector 写 raw JSON → Analyzer 读同一文件 → Organizer 读同一文件
- 约定文件名格式：`knowledge/raw/github-trending-{YYYY-MM-DD}.json`

**日终汇总日志**：流水线结束后输出一条汇总日志：采集 N 条、分析 N 条、丢弃 N 条、产出日报 N 条

## Acceptance criteria

- [ ] Collector → Analyzer → Organizer 按序自动执行
- [ ] Collector 失败时，Analyzer 和 Organizer 不执行，错误写入 `errors-{date}.json`
- [ ] Analyzer 失败时，Organizer 不执行，错误写入 `errors-{date}.json`
- [ ] 所有阶段成功时，产出完整日报
- [ ] 日终汇总日志包含采集/分析/丢弃/产出数量
- [ ] 各阶段通过文件系统传递数据，无全局状态依赖

## Blocked by

- #2: Collector 实现（需要完成才能串联）
- #3: Analyzer 实现（需要完成才能串联）
- #4: Organizer 实现（需要完成才能串联）
