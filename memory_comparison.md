# AI 代码生成：有 Memory vs 无 Memory 对比

"Memory" 指项目中的 `AGENTS.md`（项目记忆文件），它定义了编码规范、项目结构、红线约束等规则。
AI 在生成代码时会依据这些规则产出风格一致、质量可控的代码。

## 维度对比

| 维度 | 无 Memory（AI 默认行为） | 有 Memory（AGENTS.md 约束） |
|------|------------------------|---------------------------|
| **命名风格** | 风格混乱：变量可能用 `camelCase`、函数用 `snakeCase`、常量用小写。甚至同一个文件中混用多种风格。 | 严格一致：变量/函数 `snake_case`，类 `PascalCase`，常量 `UPPER_SNAKE`，私有成员 `_` 前缀。 |
| **docstring** | 时有时无，格式不统一——一段用 Google 风格，另一段又用 reST。常见缺失 `Returns` 和 `Raises`，函数签名缺类型注解。 | 所有公开函数/类必须使用 **Google 风格** docstring，含 `Args`、`Returns`、`Raises` 三要素。所有函数签名带完整类型注解（Python 3.12 语法）。 |
| **日志方式** | 大量裸 `print()` 输出调试信息，无日志级别区分，无法在生产环境控制输出。 | 统一使用 `logging` 模块，`logger = logging.getLogger(__name__)`，禁止裸 `print()`。支持按级别过滤和运行时开关。 |
| **错误处理** | 使用裸 `except:` 或 `except Exception:` 捕获所有异常，静默吞掉错误，无重试机制。 | 必须指定具体异常类型（如 `except requests.RequestException`）。API 调用的限流重试最多 3 次。错误写入 `knowledge/raw/errors-{date}.json`，不中断整体流程。 |
| **文件位置** | 文件名随机，路径随意。可能把原始数据、分析结果、配置文件全部散落在根目录。 | 按模块和日期组织：`knowledge/raw/{source}-{date}.json`、`knowledge/articles/{date}-{slug}.json`、`push/`、`reports/`，结构清晰可追溯。 |

## 结论

**Memory（AGENTS.md）对 AI 代码生成质量的影响是决定性的。** 在没有 Memory 的情况下，AI 依赖其训练数据中的统计模式生成代码，但训练数据来自成千上万个风格各异的项目，导致产出天然偏向"平均风格"——命名随意、日志缺失、错误处理粗糙。这在小规模一次性脚本中尚可接受，但在需要长期维护的项目中会成为技术债务的温床。

有 Memory 之后，AGENTS.md 实际上充当了一个**持续作用的约束层**：AI 在每次生成代码前，都会"看到"项目的命名规则、文档规范、日志约定和错误处理策略。这使得每一段新代码自动融入项目的既有风格，消除了"AI 味代码"的典型问题（如裸 `print()`、裸 `except:`、`type: ignore` 等），同时保障了代码可维护性、可追溯性和协作一致性。

简而言之：**Memory 将 AI 从"通用代码生成器"校准为"理解项目上下文的项目成员"。** 投入编写一份高质量的 AGENTS.md，远比事后反复修风格和修 bug 要划算。
