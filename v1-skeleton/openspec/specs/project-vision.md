# AI 知识库 · 项目愿景 v1.0

## 要做什么

### 采集（Collector）
- 每日 UTC 00:00 定时触发
- 抓取 **20 条/天** AI 相关仓库/文章
- 判定标准：`topics` 含 `ai` / `llm` / `agent`
- 数据源（GitHub Trending 不够部分由以下补齐）：
  - GitHub Trending（主源）
  - Hacker News Top
  - arXiv cs.AI / cs.CL
- 原始数据写入 `knowledge/raw/{source}-{YYYY-MM-DD}.json`

### 分析（Analyzer）
- 对每条原始数据做 **三维分析**：
  - **摘要**：中文简介，约 200 字
  - **技术判断**：技术栈、解决的问题、创新点、适用场景
  - **评分**：`relevance_score`（0-1）、`confidence`（0-1）
- `confidence < 0.6` 的条目标记为 `status: "review"`，进入待复核队列，不进入下游
- 串行处理，在源 JSON 上原地追加分析字段，写入 `knowledge/raw/`

### 分析追加字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `summary_zh` | string | 中文摘要，约 200 字 |
| `tech_stack` | string[] | 技术栈 |
| `innovation_point` | string | 创新点 |
| `relevance_score` | number | 相关度评分 0-1 |
| `confidence` | number | 置信度 0-1 |
| `status` | enum | `published` / `review` |

### 整理（Organizer）
- 将 `status: "published"` 的条目整理为最终知识条目
- 输出格式：JSON
- 文件路径：`knowledge/articles/{YYYY-MM-DD}-{slug}.json`
- 每条含 8 个必含字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `title` | string | 条目标题 |
| `source` | string | 来源（github-trending / hackernews / arxiv）|
| `url` | string | 原文链接 |
| `collected_at` | string | 采集时间 ISO 8601 |
| `summary` | string | 中文摘要 |
| `tags` | string[] | 英文小写连字符标签 |
| `relevance_score` | number | 相关度评分 |

### 前端
- 交互式 Web UI
- 查看当日/历史条目
- 支持搜索、tags 筛选

### 推送
- 微信推送每日知识摘要

### 周报 & 趋势
- 周报：基于最近 7 天数据生成趋势汇总
- 跨日聚合分析

### 输出语言
- 可采集英文源，**分析/摘要/注释全部输出中文**

## 不做什么

- 不输出中文以外的语言

## 边界 & 验收

- **用户模型**：单人使用
- **数据保留**：30 天（超期自动清理）
- **部署模型**：服务器部署
- **V1 完成标准**：功能清单全部跑通

## 怎么验证（验收 checklist）

- [ ] 连续 3 天，每日 UTC 00:00 定时触发采集成功
- [ ] 单日采集数据源 ≥ 2 个，入库条目 ≥ 15 条
- [ ] 每条采集数据经 Analyzer 产出 `summary_zh`、`tech_stack`、`relevance_score`、`confidence` 字段完整
- [ ] `confidence < 0.6` 的条目标记 `status: "review"`，不进入 `knowledge/articles/`
- [ ] Organizer 产出的 articles JSON 全部包含 8 个必含字段，无缺失
- [ ] Web 前端可访问，支持查看历史条目、搜索、tags 筛选
- [ ] 微信推送成功发送每日知识摘要
- [ ] 周报生成功能基于 7 天数据正常产出
- [ ] 超过 30 天的数据自动清理
- [ ] 无运行时崩溃导致流水线中断超过 24 小时
