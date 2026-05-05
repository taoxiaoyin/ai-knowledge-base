# Issue #8: 端到端集成验证

> 标签: `needs-triage` | 类型: HITL | 依赖: #1, #2, #3, #4, #5, #6, #7

## Parent

[agents-prd.md](../specs/agents-prd.md) — AI 知识库 · 三 Agent PRD v0.1

## What to build

完整跑通一次采集→分析→整理流程，验证所有组件协同工作，产出可读的 Markdown 日报。

**验证步骤**：
1. 设置 `GITHUB_TOKEN` 环境变量
2. 执行完整流水线（Collector → Analyzer → Organizer）
3. 检查产出的文件：
   - `knowledge/raw/github-trending-{date}.json` — 含 ≥ 15 条采集数据
   - 同上文件含 Analyzer 追加的 `tags`、`relevance`、`note` 字段
   - `knowledge/articles/{date}-ai-daily.md` — 格式正确、可正常渲染的日报
   - `knowledge/articles/index.md` — 索引正确
   - `knowledge/raw/status-{date}.json` — 所有阶段 `done`
   - `knowledge/raw/filtered-{date}.json` — 丢弃记录完整
4. 验证日报质量：
   - 所有条目 `relevance` 为 high 或 medium
   - 分组与标签匹配
   - 无重复条目
   - Markdown 可正常渲染
5. 重跑同一天，验证幂等性：
   - 无重复条目
   - 日志含 "跳过 N 条已有条目"

## Acceptance criteria

- [ ] 完整流水线从 Collector 到 Organizer 一气呵成运行
- [ ] `knowledge/raw/github-trending-{date}.json` 采集 ≥ 15 条
- [ ] 每个条目含完整的三维度标签和相关度评估
- [ ] 日报 Markdown 格式正确、分组合理、可读
- [ ] `index.md` 统计准确
- [ ] `status-{date}.json` 所有阶段标记为 `done`
- [ ] 过滤日志完整，每条丢弃有原因
- [ ] 重跑不会产生重复数据
- [ ] 无运行时崩溃

## Blocked by

- #1 - #7: 所有前置 Issue 必须完成
