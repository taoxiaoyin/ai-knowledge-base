---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools: Read, Grep, Glob, WebFetch
---

# 技术深度分析技能

## 使用场景

当需要对 `knowledge/raw/` 中已采集的技术内容（GitHub 仓库、Hacker News 文章、arXiv 论文）进行逐条深度分析时，自动激活此技能。适用于 Collector 完成采集后，由 Analyzer 调用此技能对原始数据进行技术研判和评分。

## 执行步骤

### 第 1 步：读取最新采集文件

从 `knowledge/raw/` 目录读取当日最新采集的 JSON 文件：

- 按文件名中的日期排序，取最新日期的文件
- 支持多源文件：`github-trending-{date}.json`、`hackernews-top-{date}.json`、`arxiv-{date}.json`
- 如果同一日期有多个文件，全部读取后合并到同一个分析批次
- 解析 `items` 数组，提取每个条目的 `name`、`url`、`description`、`stars`、`language`、`topics` 字段

### 第 2 步：逐条深度分析

对每个条目完成以下四个维度的分析：

#### 2.1 摘要（≤ 50 字）

提炼核心价值，一句话说清楚"这个东西解决了什么问题，怎么解决的"。

**写作规范**：
- 必须 ≤ 50 个中文字符，越精炼越好
- 技术术语保留英文原文（RAG、MCP、LoRA、RLHF 等）
- 直接点明本质，禁止"该项目是一个…"、"本文介绍了…"等废话开头
- 用事实和数据说话，不用空洞形容词

**示例**：

> 将 MCP 协议移植到浏览器端，通过 Wasm 沙箱让网页应用调用本地 LLM 工具链。

#### 2.2 技术亮点（2-3 个，用事实说话）

提取该条目中 2-3 个具体的技术亮点，每个亮点包含：

- **亮点名称**（一句话概括）
- **事实依据**（引用的具体数据、方案、对比结果）

**要求**：
- 禁止泛泛而谈——必须有具体技术细节或数据支撑
- 没有足够信息判断时，标注"信息不足，无法判定"
- 每个亮点不超过 60 字

**示例**：

| 亮点 | 事实依据 |
|------|----------|
| 零配置 Wasm 沙箱 | 无需 Node.js 运行时，浏览器内即完成工具注册和调用，冷启动 < 100ms |
| 协议兼容层 | 完整实现 MCP 2024-11-05 规范，通过官方 47 项兼容性测试 |

#### 2.3 评分（1-10，附理由）

按以下标准给出 1-10 的整数评分，并附一句话理由：

| 分数 | 含义 | 判定标准 |
|------|------|----------|
| 9-10 | 改变格局 | 能引发行业范式转移或开辟全新方向。如 GPT-4 发布、Transformer 论文。 |
| 7-8 | 直接有帮助 | 可立即用于实际项目，或对当前技术决策有明确指导价值。 |
| 5-6 | 值得了解 | 有参考价值，但离实际应用有距离，或与个人方向不完全匹配。 |
| 1-4 | 可略过 | 重复造轮子、信息量低、纯营销内容、与 AI 领域关联弱。 |

**评分原则**：
- 基于可验证事实，不凭印象
- 同一批次内各条目独立评分，不互相比较压低或抬高
- 理由必须具体，引用至少一个事实依据

**理由示例**：
> 8 分 — 首次在浏览器端完整实现 MCP 协议，且有 47 项兼容性测试数据佐证，
> 对 Web Agent 生态有直接推动价值。

#### 2.4 标签建议

为每个条目生成 3-5 个标签，优先使用以下词库：

**领域标签**：`large-language-model`、`agent-framework`、`multi-agent`、`rag`、`mcp`、`fine-tuning`、`prompt-engineering`、`code-generation`、`embeddings`、`inference`、`alignment`

**技术标签**：`transformer`、`lora`、`vector-database`、`knowledge-graph`、`function-calling`、`tool-use`、`wasm`、`webgpu`

**语言/平台标签**：`python`、`typescript`、`rust`、`jupyter`、`browser`

**规则**：
- 全部小写，连字符分隔
- 优先使用词库标签保持一致性
- 出现词库未覆盖的新概念可以新增，但需标注为 `new:xxx`

### 第 3 步：趋势发现

基于全部分析结果，人工归纳当批条目的宏观趋势：

#### 3.1 共同主题

找出这批条目中反复出现的技术主题或模式（≥ 3 个条目涉及视为主题）：

```
示例：
- MCP 协议落地：4 个项目都在做 MCP 的客户端/服务端实现，协议标准化趋势明显
- 浏览器端 LLM：3 个项目在探索 WebGPU + 本地推理，去服务端化迹象
```

#### 3.2 新概念

记录本批中出现的新概念、新术语或之前少见的方案：

```
示例：
- "Wasm-native inference"：首次出现以 Wasm 为核心推理引擎的方案，非传统 Python/CUDA 路径
```

> 趋势发现不是必选项——如果没有明显趋势，注明"本批次未发现显著共同趋势"即可。

### 第 4 步：输出分析结果 JSON

将分析结果写入源文件同目录，字段原地追加：

- **不创建新文件**：在原 `knowledge/raw/{source}-{date}.json` 中，对 `items[]` 的每个条目原地追加分析字段
- 写入前检查文件是否已被分析过（检查 `items[0]` 是否已有 `score` 字段）：
  - 已分析 → 跳过，记录日志 "文件已分析，不再重复处理"
  - 未分析 → 追加字段后写回

**追加字段结构**：

```json
{
  "summary_short": "≤50字中文摘要...",
  "tech_highlights": [
    {
      "highlight": "亮点名称",
      "evidence": "事实依据"
    }
  ],
  "score": 8,
  "score_reason": "评分理由，引用具体事实...",
  "tags": ["agent-framework", "python", "mcp"],
  "analyzed_at": "2026-05-03T12:00:00Z",
  "trends": {
    "common_themes": ["MCP 协议落地：4 个项目在做 MCP 实现，协议标准化趋势明显"],
    "new_concepts": ["Wasm-native inference：首次出现以 Wasm 为核心推理引擎的方案"]
  }
}
```

> `trends` 写在文件顶层（共享），不在每个 `item` 中重复。

## 约束

- **评分分布**：每批 15 个项目中，9-10 分不超过 2 个。宁可严格，不可通胀
- **摘要长度**：每条摘要严格 ≤ 50 个中文字符，超过即不合格
- **技术亮点**：每条必须有事实依据，没有依据则跳过不写
- **禁止模板化**：不复制 description 原文翻译，必须用自己的话重新提炼

## 输出格式（完整文件结构）

```json
{
  "source": "github-trending",
  "skill": "github-trending",
  "collected_at": "2026-05-03T10:00:00Z",
  "trends": {
    "common_themes": [],
    "new_concepts": []
  },
  "items": [
    {
      "name": "owner/repo-name",
      "url": "https://github.com/owner/repo-name",
      "summary": "≤50字中文摘要...",
      "stars": 3200,
      "language": "Python",
      "topics": ["agent-framework", "llm"],
      "summary_short": "≤50字中文精炼摘要...",
      "tech_highlights": [
        {
          "highlight": "亮点名称",
          "evidence": "事实依据"
        }
      ],
      "score": 8,
      "score_reason": "评分理由...",
      "tags": ["agent-framework", "python"],
      "analyzed_at": "2026-05-03T12:00:00Z"
    }
  ]
}
```

**新增字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `summary_short` | string | ≤ 50 字中文精炼摘要 |
| `tech_highlights` | object[] | 技术亮点数组，每项含 `highlight` 和 `evidence` |
| `score` | number | 整数评分 1-10 |
| `score_reason` | string | 评分理由，引用具体事实 |
| `tags` | string[] | 标签建议，3-5 个 |
| `analyzed_at` | string | 分析时间，ISO 8601 格式 |
| `trends` | object | 文件级趋势发现，含 `common_themes` 和 `new_concepts` |
