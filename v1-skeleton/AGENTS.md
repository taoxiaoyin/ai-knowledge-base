# AGENTS.md — AI 知识库项目

> 本文件是项目的"大脑"——OpenCode 启动时自动加载，指导所有 Agent 的行为。

## 项目定义

**AI Knowledge Base（AI 知识库）** 是一个自动化技术情报收集与分析系统。
它每日定时从 GitHub Trending、Hacker News、arXiv 等多源采集 AI 领域技术资讯，
通过 LangGraph 编排的 Agent 流水线完成采集、分析、整理，输出结构化中文知识条目，
并通过 Telegram / 飞书多渠道分发触达用户。

### 核心价值
- 每日自动采集 AI/LLM/Agent 领域的 **20 条** 高质量技术文章与开源项目
- 通过 Agent 协作完成 **采集 → 分析 → 整理** 三阶段流水线
- 输出格式统一的 JSON 知识条目，支持多渠道分发与前端检索
- 自动生成周报和趋势分析，辅助技术决策

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 运行时 | Python 3.12+ | 主开发语言，建议使用最新稳定版 |
| Agent 编排 | OpenCode + 国产大模型 | DeepSeek / Qwen，Agent 调度与协作 |
| 流水线引擎 | LangGraph | 状态机驱动的多节点工作流编排 |
| 自动采集 | OpenClaw | 无头浏览器 / 自动化网页抓取 |
| 数据源 | GitHub API v3 | 仓库搜索与 Trending |
| | Hacker News API (Firebase) | Top Stories 获取 |
| | arXiv API | cs.AI / cs.CL 论文检索 |
| 输出格式 | JSON | 结构化知识条目 |
| 分发渠道 | Telegram Bot API | 每日知识摘要推送 |
| | 飞书 Webhook | 同步推送 |
| 插件系统 | TypeScript + Bun | OpenCode Plugin Hook，文件校验等扩展 |
| 版本管理 | Git | 代码与数据版本控制 |

## 项目结构

```
ai-knowledge-base/
├── AGENTS.md                          # 项目记忆文件（本文件）
├── .env                               # 环境变量（API Key、Token 等）
├── .opencode/
│   ├── agents/
│   │   ├── collector.md               # 采集 Agent 角色定义
│   │   ├── analyzer.md                # 分析 Agent 角色定义
│   │   └── organizer.md               # 整理 Agent 角色定义
│   ├── plugins/
│   │   └── *.ts                        # TypeScript 插件（文件校验等扩展）
│   └── skills/
│       ├── github-trending/SKILL.md   # GitHub Trending 采集技能
│       └── tech-summary/SKILL.md      # 技术摘要生成技能
├── knowledge/
│   ├── raw/                           # 原始采集数据（JSON）+ 分析追加字段
│   └── articles/                      # 整理后的知识条目（JSON）
├── push/                              # 分发模块（Telegram + 飞书）
└── reports/                           # 周报 & 趋势分析
```

## 编码规范

### Python

**格式化**：[black](https://github.com/psf/black)，默认配置（line-length=88）。

**Lint**：[ruff](https://github.com/astral-sh/ruff)，启用以下规则：

| 规则组 | 检查内容 |
|--------|----------|
| `I` | import 排序（stdlib → 第三方 → 本地模块，各组内按字母序） |
| `D` | 公开函数/类必须有 Google 风格 docstring |
| `N` | 命名规范（snake_case / PascalCase / UPPER_SNAKE，私有成员单下划线前缀） |
| `T201` | 禁止裸 `print()` |
| `E722` | 禁止裸 `except:` |
| `PGH003` | 禁止 `# type: ignore` |

**类型检查**：[pyright](https://github.com/microsoft/pyright)，`typeCheckingMode: "strict"`。

- 所有函数参数、返回值必须有完整类型注解
- `strict` 模式强制类型注解，缺失即报错
- 禁止 `as any`、`@ts-ignore` 等类型抑制

**命名规则**：

- 变量/函数：`snake_case`（如 `collect_github_trending`）
- 类：`PascalCase`（如 `KnowledgePipeline`）
- 常量：`UPPER_SNAKE`（如 `MAX_RETRY_COUNT`）
- 私有成员：单下划线前缀（如 `_build_query`）

**Docstring**：所有公开函数/类必须使用 **Google 风格** docstring：

```python
def collect_github_trending(token: str, limit: int = 20) -> list[dict]:
    """从 GitHub Trending 采集 AI 相关仓库

    使用 GitHub Search API 搜索最近一周内创建的 AI/LLM/Agent 相关仓库，
    按 Star 数降序排列，返回指定数量的结果。

    Args:
        token: GitHub Personal Access Token，用于提升 API 限额
        limit: 最大采集数量，默认 20

    Returns:
        包含仓库信息的字典列表，每个字典含 id、title、url、stars 等字段

    Raises:
        RuntimeError: GitHub API 请求失败或返回非 200 状态码时抛出
    """
```

**日志**：禁止裸 `print()`，必须使用 `logging` 模块：

```python
import logging

logger = logging.getLogger(__name__)

# 正确
logger.info("采集完成，共 %d 条", len(items))

# 错误 — 禁止
print("采集完成，共", len(items), "条")
```

**Imports 排序**：stdlib → 第三方库 → 本地模块，各组内按字母序（由 ruff `I` 规则自动执行）：

```python
import json
import logging
from datetime import datetime, timezone

import requests
from langgraph.graph import StateGraph

from workflows.state import KBState
```

**依赖管理**：[uv](https://github.com/astral-sh/uv)。`pyproject.toml` 声明依赖，`uv.lock` 锁版本进仓库。

---

### TypeScript

**运行时**：Bun（统一用于插件代码和开发工具链）。

**格式化**：[Prettier](https://prettier.io/)，默认配置（无分号、行宽 80、双引号）。

**Import 排序**：[@ianvs/prettier-plugin-sort-imports](https://github.com/ianvs/prettier-plugin-sort-imports)，
排序顺序：类型导入 → 外部包 → 相对路径导入，各组内按字母序。

**类型检查**：`tsc --noEmit`，`strict: true`。

**Lint**：[ESLint](https://eslint.org/)，启用以下插件/配置：

| 配置 | 检查内容 |
|------|----------|
| `strictTypeChecked` | 类型感知的严格规则（禁止 `var`、优先 `const`、禁止空 catch） |
| `stylisticTypeChecked` | 命名规范（camelCase / PascalCase / UPPER_SNAKE） |
| `eslint-plugin-jsdoc` | 导出函数/类型必须有 JSDoc |
| `eslint-config-prettier` | 关掉与 Prettier 冲突的格式规则 |

**命名规则**：

- 变量/函数：`camelCase`（如 `collectArticles`、`parseSourceUrl`）
- 类/接口/类型别名：`PascalCase`（如 `KnowledgePipeline`、`ArticleEntry`）
- 常量：`UPPER_SNAKE`（如 `MAX_RETRY_COUNT`、`DEFAULT_LIMIT`）
- 私有类成员：`#` 前缀（如 `#buildQuery`）
- 导出常量（如 Plugin 对象）：`PascalCase`（如 `ValidateHook`）

**类型注解**：所有函数参数、返回值、公开接口必须带类型注解。

- 禁止使用 `any`，优先用 `unknown` 配合类型守卫收窄
- 禁止 `// @ts-ignore`、`// @ts-nocheck`、`as any`
- `as` 类型断言仅用于向下收窄（如 `as string`、`as const`），禁止跨类型强制转换
- 可能为 `undefined` / `null` 的值使用可选链 `?.` 和空值合并 `??`

```typescript
// 正确 — 类型守卫 + 窄化
function parseInput(raw: unknown): ArticleEntry {
  if (typeof raw !== 'object' || raw === null) {
    throw new TypeError('输入必须是对象');
  }
  const record = raw as Record<string, unknown>;
  return {
    id: String(record.id ?? ''),
    title: String(record.title ?? ''),
  };
}

// 错误 — 禁止 any、禁止 @ts-ignore
function parseInput(raw: any): any {
  // @ts-ignore — 禁止
  return raw;
}
```

**JSDoc**：导出函数/类型必须带 JSDoc 注释：

```typescript
/**
 * 校验知识条目 JSON 的格式合规性
 *
 * 在 Plugin Hook 中自动调用，检查必填字段、ID 格式、状态值合法性。
 *
 * @param filePath - 待校验的 JSON 文件路径
 * @returns 校验结果对象，含 `valid` 标志和错误列表
 */
export function validateArticle(filePath: string): ValidationResult {
  // ...
}
```

**错误处理**：捕获异常必须指定具体类型，禁止空 `catch` 块：

```typescript
try {
  await collectTrending();
} catch (err: unknown) {
  if (err instanceof Error) {
    logger.error('采集失败: %s', err.message);
  } else {
    logger.error('采集失败: 未知错误 %o', err);
  }
}

// 错误 — 禁止空 catch
try { /* ... */ } catch (e) {}  // 禁止
```

**日志**：Plugin Hook 场景允许 `console.log`；独立模块统一使用 Logger：

```typescript
// Plugin Hook 中允许
console.log(`[validate-hook] ✅ 格式校验通过`);

// 独立模块中使用 logger
import { logger } from './logger';
logger.info('校验完成，共 %d 条', items.length);
```

**文件命名**：`.ts` 文件使用 `snake_case` 或 `kebab-case`：
- 例：`validate.ts`、`format-output.ts`、`check-quality.ts`

**依赖管理**：[Bun](https://bun.sh/)。
`package.json` 声明依赖（含 `devDependencies`），`bun.lockb` 锁版本进仓库。

---

### JSON

**格式化**：Prettier（2 空格缩进，UTF-8）。

- **日期格式**：ISO 8601（`YYYY-MM-DDTHH:mm:ssZ`）
- **键名**：英文
- **值**：摘要/分析字段使用中文

### 文件命名

- 原始数据：`knowledge/raw/{source}-{YYYY-MM-DD}.json`
  - 例：`knowledge/raw/github-trending-2026-03-17.json`
  - 例：`knowledge/raw/hackernews-top-2026-03-17.json`
  - 例：`knowledge/raw/arxiv-2026-03-17.json`
- 知识条目：`knowledge/articles/{YYYY-MM-DD}-{slug}.json`
  - 例：`knowledge/articles/2026-03-17-openai-agents-sdk.json`
- 索引文件：`knowledge/articles/index.json`
- 错误日志：`knowledge/raw/errors-{YYYY-MM-DD}.json`

### 语言约定

- 代码、JSON 键名、文件名：**英文**
- 摘要、分析、注释：**中文**
- 标签（tags）：英文小写，连字符分隔（如 `large-language-model`、`multi-agent`）
- **只输出中文**，不输出其他语言的分析/摘要/注释

### 通用规则

**禁止魔法字符串**：业务逻辑中的枚举值/状态值/标签必须通过常量引用，禁止裸字符串字面量。
配置 key、字典 key 不在此限。

**禁止未完成代码**：`TODO`、`FIXME`、`HACK` 注释不得出现在 `main` 分支。
检查范围仅限 diff 新增行（存量不管）。

**敏感信息保护**：
- API Token / Key 等必须通过环境变量（`os.getenv()`）读取，禁止硬编码
- `.env` 文件不进版本控制（写入 `.gitignore`）
- 项目必须维护 `.env.example` 作为配置模板

### 工具链 & CI

**本地 pre-commit**：

| 检查项 | 工具 |
|--------|------|
| Python 格式化 | `black --check .` |
| Python lint | `ruff check .` |
| TypeScript 格式化 + import 排序 | `prettier --check .` |
| 密钥泄露扫描 | `detect-secrets` |
| 未完成代码 | `grep` 检查 diff 新增行中的 `TODO\|FIXME\|HACK` |

**CI pipeline**：

| 检查项 | 工具 |
|--------|------|
| lint（第二道防线） | black + ruff + prettier（与 pre-commit 相同） |
| TypeScript 类型 | `tsc --noEmit` |
| Python 类型 | `pyright` |
| 单测 + 增量覆盖率 | `pytest --cov=src` + `diff-cover --fail-under=80` |

**命令速查**：

```bash
# 本地一次跑完所有检查
pre-commit run --all-files

# 单独检查
black --check . && ruff check . && prettier --check .
pyright . && tsc --noEmit
pytest --cov=src --cov-report=xml
diff-cover coverage.xml --fail-under=80
```

## 知识条目 JSON 格式

### 原始数据字段（Collector 产出）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `title` | string | 仓库/文章标题 |
| `source` | string | 来源：`github-trending` / `hackernews` / `arxiv` |
| `source_url` | string | 原文链接 |
| `collected_at` | string | 采集时间 ISO 8601 |
| `topics` | string[] | 仓库 topics / 文章分类 |

### 分析追加字段（Analyzer 在 raw JSON 上原地追加）

| 字段 | 类型 | 说明 |
|------|------|------|
| `summary_zh` | string | 中文摘要，约 200 字 |
| `tech_stack` | string[] | 技术栈 |
| `innovation_point` | string | 创新点 |
| `relevance_score` | number | 相关度评分 0-1 |
| `confidence` | number | 置信度 0-1 |
| `status` | enum | `published` / `review` |

### 最终条目字段（Organizer 产出）

| 字段 | 类型 | 必含 |
|------|------|------|
| `id` | string | ✅ |
| `title` | string | ✅ |
| `source` | string | ✅ |
| `source_url` | string | ✅ |
| `collected_at` | string | ✅ |
| `summary` | string | ✅ |
| `tags` | string[] | ✅ |
| `relevance_score` | number | ✅ |
| `status` | string | ✅ |

**完整示例**：

```json
{
  "id": "kb-20260317-001",
  "title": "OpenAI Agents SDK",
  "source": "github-trending",
  "source_url": "https://github.com/openai/agents-sdk",
  "collected_at": "2026-03-17T10:00:00Z",
  "summary": "OpenAI 官方 Agent 开发 SDK，提供 Handoff（任务交接）、Guardrails（安全护栏）等核心原语。开发者可以用 Python 快速构建多 Agent 协作应用，内置追踪和评估工具。对于正在探索 Agent 架构的团队，这是一个值得参考的官方实现范例。",
  "tags": ["agent-framework", "multi-agent", "python", "openai", "handoff"],
  "relevance_score": 0.87,
  "status": "published"
}
```

## Agent 角色概览

| 角色 | Agent 文件 | 职责 | 输入 | 输出 | 允许工具 | 禁止工具 |
|------|-----------|------|------|------|---------|---------|
| **采集员** | `collector.md` | 从外部数据源采集 AI 领域技术资讯 | GitHub/HN/arXiv API | `knowledge/raw/{source}-{date}.json` | Read, Grep, Glob, WebFetch | Write, Edit |
| **分析员** | `analyzer.md` | 逐条深度分析，生成中文摘要并评分 | `knowledge/raw/` 中的原始 JSON | 在 raw JSON 上原地追加分析字段 | Read, Grep, Glob, WebFetch | Write, Edit |
| **整理员** | `organizer.md` | 去重、过滤、格式化，输出最终知识条目 | 已分析的 raw JSON | `knowledge/articles/{date}-{slug}.json` + `index.json` | Read, Grep, Glob, Write, Edit | WebFetch |

## 工作流规则

### 三阶段流水线

```
[Collector] ──采集──→ knowledge/raw/
                          │
[Analyzer]  ──分析──→ knowledge/raw/ (原地追加字段)
                          │
[Organizer] ──整理──→ knowledge/articles/
```

### 采集规则（Collector）

1. **触发时机**：每日 UTC 00:00 自动触发
2. **采集数量**：20 条/天
3. **筛选标准**：仓库 `topics` 含 `ai` / `llm` / `agent`
4. **数据源优先级**：
   - 主源：GitHub Trending
   - 补齐（当主源不足 20 条时）：Hacker News Top、arXiv cs.AI / cs.CL
5. **幂等性**：重复运行同一天的采集不产生重复条目
6. **错误处理**：
   - 网络请求失败：记录错误并跳过该源，不中断整体流程
   - API 限流：等待后重试，最多 3 次
   - 数据格式异常：写入 `knowledge/raw/errors-{date}.json` 供人工排查

### 分析规则（Analyzer）

1. **输入**：`knowledge/raw/{source}-{YYYY-MM-DD}.json`
2. **处理顺序**：串行处理（逐条分析）
3. **分析维度**：
   - **摘要**：中文简介，约 200 字 → 字段 `summary_zh`
   - **技术判断**：技术栈、解决的问题、创新点、适用场景 → 字段 `tech_stack`、`innovation_point`
   - **评分**：相关度 0-1、置信度 0-1 → 字段 `relevance_score`、`confidence`
4. **质量门控**：`confidence < 0.6` 的条目标记为 `status: "review"`，进入待复核队列
5. **输出**：在原 raw JSON 上原地追加分析字段

### 整理规则（Organizer）

1. **输入**：已分析的 raw JSON 文件
2. **过滤**：仅处理 `status: "published"` 的条目，`status: "review"` 的跳过
3. **输出格式**：JSON，每个条目一个文件
4. **必含字段**：`id`、`title`、`source`、`source_url`、`collected_at`、`summary`、`tags`、`relevance_score`、`status`
5. **可追溯**：每个条目保留 `source` 和 `collected_at` 用于溯源
6. **索引**：维护 `knowledge/articles/index.json`

### Agent 协作规则

1. **单向数据流**：Collector → Analyzer → Organizer，不可反向
2. **职责隔离**：每个 Agent 只操作自己权限范围内的文件
3. **串行依赖**：Analyzer 必须等待 Collector 完成，Organizer 必须等待 Analyzer 完成
4. **幂等性**：重复运行同一天的采集不产生重复条目
5. **质量门控**：`confidence < 0.6` 的条目标记为 `status: "review"`，不进入 `knowledge/articles/`
6. **可追溯**：每个条目保留 `source_url` 和 `collected_at` 用于溯源

### Agent 调用方式

在 OpenCode 中使用 `@` 语法调用特定 Agent：

```
@collector 采集今天的 GitHub Trending 数据
@analyzer 分析 knowledge/raw/github-trending-2026-03-17.json
@organizer 整理今天所有已分析的原始数据
```

也可以在对话中要求主 Agent 依次委派子 Agent，实现流水线作业。

### 多渠道分发

- **Telegram**：每日在 Organizer 完成后，通过 Telegram Bot API 推送当日知识摘要（标题列表 + Top 5 重点关注条目）
- **飞书**：通过飞书 Webhook 同步推送，消息格式与 Telegram 保持一致
- **推送模块路径**：`push/`

### 周报 & 趋势分析

- 基于最近 7 天 `knowledge/articles/` 数据
- 产出趋势汇总：热门 topics 变化、高分条目占比、技术方向走势
- 周报输出路径：`reports/weekly-{YYYY-MM-DD}.json`

## 红线 — 绝对禁止

以下行为在任何情况下均**严格禁止**，违反即视为阻塞性问题：

| # | 红线 | 说明 |
|---|------|------|
| 1 | **禁止裸 `print()`** | 生产代码中禁止使用 `print()` 输出日志/调试信息，必须使用 `logging` 模块 |
| 2 | **禁止跨角色写文件** | Collector / Analyzer 不得使用 Write / Edit 工具，只能读不能写 |
| 3 | **禁止反向数据流** | Organizer 不得修改 `knowledge/raw/` 数据，Analyzer 不得重新采集 |
| 4 | **禁止输出非中文摘要** | 所有 summary / summary_zh / analysis 字段内容必须为中文 |
| 5 | **禁止跳过质量门控** | `confidence < 0.6` 的条目不得进入 `knowledge/articles/` |
| 6 | **禁止覆盖已有数据** | 写入前必须检查文件是否存在，存在则读取后合并去重，不可直接覆盖 |
| 7 | **禁止静默丢弃** | 丢弃任何条目必须在过滤日志中记录 `id` 和丢弃原因 |
| 8 | **禁止裸 `except`** | 捕获异常必须指定具体类型（如 `except requests.RequestException`），禁止 `except:` 或 `except Exception:` 裸捕获 |
| 9 | **禁止硬编码密钥** | API Token / Key 等敏感信息必须通过环境变量（`os.getenv()`）读取，禁止写死在代码中 |
| 10 | **禁止 type: ignore** | 不允许用 `# type: ignore`、`as any`、`@ts-ignore`、`// @ts-nocheck` 等抑制类型检查，必须从类型层面解决 |

## 边界与约束

### 用户模型
- **单人使用**，不涉及多用户/权限管理

### 数据保留
- **30 天自动清理**：超过 30 天的 `raw/` 和 `articles/` 数据自动删除
- 清理时机：每日采集前执行

### 部署模型
- **服务器部署**，非本地运行

### 输出语言
- **只输出中文**，不输出中文以外的分析/摘要语言

## 验收标准

V1 功能清单全部跑通视为完成。验收 checklist：

- [ ] 连续 3 天，每日 UTC 00:00 定时触发采集成功
- [ ] 单日采集数据源 ≥ 2 个，入库条目 ≥ 15 条
- [ ] 每条采集数据经 Analyzer 产出 `summary_zh`、`tech_stack`、`relevance_score`、`confidence` 字段完整
- [ ] `confidence < 0.6` 的条目标记 `status: "review"`，不进入 `knowledge/articles/`
- [ ] Organizer 产出的 articles JSON 全部包含 9 个必含字段（含 `status`），无缺失
- [ ] Telegram 推送成功发送每日知识摘要
- [ ] 飞书推送成功发送每日知识摘要
- [ ] 周报生成功能基于 7 天数据正常产出
- [ ] 超过 30 天的数据自动清理
- [ ] 无运行时崩溃导致流水线中断超过 24 小时
