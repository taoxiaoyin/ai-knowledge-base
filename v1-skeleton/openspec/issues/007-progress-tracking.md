# Issue #7: 进度追踪：流水线状态日志

> 标签: `needs-triage` | 类型: AFK | 依赖: #5

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

实现流水线执行过程中的进度追踪，每个阶段开始/结束时写状态日志，便于监控运行状态。

**状态文件**：`knowledge/raw/status-{date}.json`

```json
{
  "date": "2026-05-03",
  "status": "running",
  "stages": [
    { "name": "collector", "status": "done", "started_at": "...", "finished_at": "...", "item_count": 20, "error": null },
    { "name": "analyzer", "status": "running", "started_at": "...", "finished_at": null, "item_count": null, "error": null },
    { "name": "organizer", "status": "pending", "started_at": null, "finished_at": null, "item_count": null, "error": null }
  ]
}
```

**状态值**：`pending` → `running` → `done` / `failed`
- `done`：正常完成，含 `item_count`
- `failed`：异常退出，含 `error` 字段

**日志要求**：
- 每个阶段开始前写 `status: running`
- 每个阶段完成后写 `status: done` 含 `item_count`
- 异常时写 `status: failed` 含 `error`

## Acceptance criteria

- [ ] 每个阶段开始前，`status-{date}.json` 中对应阶段标记为 `running`
- [ ] 每个阶段完成后，标记为 `done`，含 `item_count`
- [ ] 阶段失败时，标记为 `failed`，含 `error`
- [ ] 文件内容可随时读取，反映流水线实时状态
- [ ] 同一天重跑时，状态文件重置

## Blocked by

- #5: 流水线编排（进度追踪在编排层实现）
