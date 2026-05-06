#!/usr/bin/env python3
"""知识条目质量评分脚本 — 五维度评估文章质量。

五个维度（加权总分 100 分）：
  1. 摘要质量   — 25 分
  2. 技术深度   — 25 分
  3. 格式规范   — 20 分
  4. 标签精度   — 15 分
  5. 空洞词检测 — 15 分

等级：A (>=80) / B (>=60) / C (<60)

用法:
    python hooks/check_quality.py <json_file> [json_file2 ...]
    python hooks/check_quality.py knowledge/articles/*.json

退出码:
    0 — 全部 B 级以上
    1 — 存在 C 级文章
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HOLLOW_WORDS_ZH: list[str] = [
    "赋能",
    "抓手",
    "闭环",
    "打通",
    "全链路",
    "底层逻辑",
    "颗粒度",
    "对齐",
    "拉通",
    "沉淀",
    "强大的",
    "革命性的",
]

HOLLOW_WORDS_EN: list[str] = [
    "groundbreaking",
    "revolutionary",
    "game-changing",
    "cutting-edge",
    "state-of-the-art",
    "leverage",
    "synergy",
    "paradigm shift",
    "disruptive",
    "next-generation",
    "world-class",
]

HOLLOW_WORDS: list[str] = HOLLOW_WORDS_ZH + HOLLOW_WORDS_EN

VALID_TAGS: frozenset[str] = frozenset(
    {
        "agent",
        "agent-framework",
        "api",
        "audio",
        "benchmark",
        "code-generation",
        "computer-vision",
        "dataset",
        "deep-learning",
        "deployment",
        "evaluation",
        "fine-tuning",
        "large-language-model",
        "llm",
        "machine-learning",
        "mcp",
        "multi-agent",
        "nlp",
        "open-source",
        "prompt-engineering",
        "python",
        "rag",
        "reasoning",
        "robotics",
        "security",
        "tool-use",
        "vision",
    }
)

TECH_KEYWORDS: list[str] = [
    "模型",
    "训练",
    "推理",
    "API",
    "框架",
    "agent",
    "LLM",
    "RAG",
    "token",
    "向量",
    "embedding",
    "transformer",
    "微调",
    "model",
    "training",
    "inference",
    "framework",
    "架构",
    "优化",
    "benchmark",
    "评估",
    "部署",
    "开源",
    "fine-tuning",
    "RLHF",
    "prompt",
]


@dataclass
class DimensionScore:
    """单维度评分。

    Attributes:
        name: 维度名称（如 "摘要质量"）。
        score: 实际得分。
        max_score: 该维度满分。
        details: 评分详情说明。
    """

    name: str
    score: float
    max_score: float
    details: str

    @property
    def percentage(self) -> float:
        """得分百分比（0-100）。"""
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0.0


@dataclass
class QualityReport:
    """单篇文章的质量评估报告。

    Attributes:
        filepath: 源文件路径。
        title: 文章标题。
        dimensions: 五个维度的评分列表。
    """

    filepath: str
    title: str
    dimensions: list[DimensionScore]

    @property
    def total_score(self) -> float:
        """加权总分。"""
        return sum(d.score for d in self.dimensions)

    @property
    def max_total(self) -> float:
        """满分（固定 100）。"""
        return sum(d.max_score for d in self.dimensions)

    @property
    def grade(self) -> str:
        """等级：A (>=80) / B (>=60) / C (<60)。"""
        score = self.total_score
        if score >= 80:
            return "A"
        if score >= 60:
            return "B"
        return "C"


def _score_summary(data: dict[str, Any]) -> DimensionScore:
    """维度 1：摘要质量（满分 25 分）。

    评分规则：
    - >= 50 字：满分 25 分
    - >= 20 字：基本分 20 分
    - < 20 字：按比例计算，最低 0 分
    - 每匹配 1 个技术关键词额外 +1 分，最多 +5 分
    - 总分上限 25 分

    Args:
        data: 文章 JSON 数据字典。

    Returns:
        摘要质量维度的评分结果。
    """
    max_score = 25.0
    summary = str(data.get("summary", "")).strip()

    if not summary:
        return DimensionScore("摘要质量", 0.0, max_score, "无摘要")

    length = len(summary)

    if length >= 50:
        base = 25.0
        detail = f"长度充足 ({length} 字)"
    elif length >= 20:
        base = 20.0
        detail = f"长度基本 ({length} 字)"
    else:
        base = max(0.0, (length / 20.0) * 20.0)
        detail = f"太短 ({length} 字)"

    keyword_count = sum(
        1 for kw in TECH_KEYWORDS if kw.lower() in summary.lower()
    )
    bonus = min(5.0, float(keyword_count))
    if bonus > 0:
        detail += f"，含 {keyword_count} 个技术关键词 (+{bonus:.0f})"

    score = min(max_score, base + bonus)
    return DimensionScore("摘要质量", score, max_score, detail)


def _score_tech_depth(data: dict[str, Any]) -> DimensionScore:
    """维度 2：技术深度（满分 25 分）。

    基于文章 score 字段（1-10 分）线性映射到 0-25 分。
    缺失 score 字段或类型异常时默认按 5 分处理。

    Args:
        data: 文章 JSON 数据字典。

    Returns:
        技术深度维度的评分结果。
    """
    max_score = 25.0
    score_val = data.get("score")

    if score_val is None:
        score_val = 5
        detail_prefix = "score 字段缺失，按 5 分处理"
    elif not isinstance(score_val, (int, float)) or isinstance(score_val, bool):
        score_val = 5
        detail_prefix = "score 字段类型异常，按 5 分处理"
    else:
        score_val = float(score_val)
        detail_prefix = f"文章评分 {score_val:.0f}/10"

    score_val = max(1.0, min(10.0, score_val))
    mapped = round((score_val / 10.0) * max_score, 1)

    detail = f"{detail_prefix} → {mapped:.1f}/{max_score:.0f}"
    return DimensionScore("技术深度", mapped, max_score, detail)


def _score_format(data: dict[str, Any]) -> DimensionScore:
    """维度 3：格式规范（满分 20 分）。

    检查 5 项，每项 4 分：
    - id 存在且非空
    - title 存在且非空
    - source_url 存在且非空
    - status 存在且非空
    - collected_at 或 updated_at 时间戳存在

    Args:
        data: 文章 JSON 数据字典。

    Returns:
        格式规范维度的评分结果。
    """
    max_score = 20.0
    field_checks: list[tuple[str, float]] = [
        ("id", 4),
        ("title", 4),
        ("source_url", 4),
        ("status", 4),
    ]

    missing: list[str] = []
    score = 0.0

    for field_name, points in field_checks:
        val = data.get(field_name, "")
        if val and str(val).strip():
            score += points
        else:
            missing.append(field_name)

    has_timestamp = bool(data.get("collected_at") or data.get("updated_at"))
    if has_timestamp:
        score += 4
    else:
        missing.append("时间戳(collected_at/updated_at)")

    if not missing:
        detail = "完整"
    else:
        detail = "缺失: " + ", ".join(missing)

    return DimensionScore("格式规范", score, max_score, detail)


def _score_tags(data: dict[str, Any]) -> DimensionScore:
    """维度 4：标签精度（满分 15 分）。

    评分规则：
    - 1-3 个标签且全部合法：15 分
    - 1-3 个标签，部分合法：按合法比例得分（10 + 5 * 合法比例）
    - 标签数量 > 3：基础按合法比例得分（满分 10），额外扣分
    - 标签数量 > 5：超出部分每个 -1 分
    - 无标签：0 分

    Args:
        data: 文章 JSON 数据字典。

    Returns:
        标签精度维度的评分结果。
    """
    max_score = 15.0
    tags: list[str] = data.get("tags", [])

    if not isinstance(tags, list):
        return DimensionScore("标签精度", 0.0, max_score, "tags 字段不是列表")

    if not tags:
        return DimensionScore("标签精度", 0.0, max_score, "无标签")

    total_count = len(tags)
    valid_count = sum(1 for t in tags if isinstance(t, str) and t in VALID_TAGS)

    if total_count <= 3:
        if valid_count == total_count:
            score = 15.0
            detail = f"{total_count} 个标签，全部合法"
        elif valid_count > 0:
            ratio = valid_count / total_count
            score = round(10.0 + 5.0 * ratio, 1)
            detail = f"{valid_count}/{total_count} 个合法标签"
        else:
            score = 3.0
            detail = f"有 {total_count} 个标签但均不在标准列表"
    else:
        ratio = valid_count / total_count
        score = round(10.0 * ratio, 1) if valid_count > 0 else 3.0
        detail = f"{valid_count}/{total_count} 个合法标签"

    if total_count > 5:
        penalty = min(5.0, (total_count - 5) * 1.0)
        score = max(0.0, score - penalty)
        detail += f"，标签过多 (-{penalty:.0f}分)"

    return DimensionScore("标签精度", score, max_score, detail)


def _score_hollow(data: dict[str, Any]) -> DimensionScore:
    """维度 5：空洞词检测（满分 15 分）。

    扫描 title 和 summary 字段，每发现 1 个空洞词扣 3 分，扣完为止。

    Args:
        data: 文章 JSON 数据字典。

    Returns:
        空洞词检测维度的评分结果。
    """
    max_score = 15.0
    text = (
        str(data.get("summary", "")) + " " + str(data.get("title", ""))
    ).lower()

    found: list[str] = []
    for word in HOLLOW_WORDS:
        if word.lower() in text:
            found.append(word)

    penalty = min(max_score, len(found) * 3.0)
    score = max_score - penalty

    if found:
        detail = f"发现 {len(found)} 个空洞词: {', '.join(found[:5])}"
        if len(found) > 5:
            detail += f" 等"
    else:
        detail = "未发现空洞词"

    return DimensionScore("空洞词检测", score, max_score, detail)


def evaluate_quality(filepath: str, data: dict[str, Any]) -> QualityReport:
    """对单篇文章进行五维度综合评估。

    Args:
        filepath: 源文件路径。
        data: 文章 JSON 数据字典。

    Returns:
        包含五个维度评分和汇总等级的质量报告。
    """
    title = str(data.get("title", Path(filepath).stem))
    dimensions = [
        _score_summary(data),
        _score_tech_depth(data),
        _score_format(data),
        _score_tags(data),
        _score_hollow(data),
    ]
    return QualityReport(filepath=filepath, title=title, dimensions=dimensions)


def _print_report(report: QualityReport) -> None:
    """格式化输出单篇文章的质量评估报告。

    包含每个维度的进度条、得分详情、总分和等级。

    Args:
        report: 质量评估报告。
    """
    bar_width = 30

    print(f"\n{'─' * 62}")
    print(f"  📄 {report.title}")
    print(f"     文件: {report.filepath}")
    print(f"{'─' * 62}")

    for dim in report.dimensions:
        filled = int(dim.percentage / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = f"{dim.percentage:5.1f}%"
        print(
            f"  {dim.name:6s} │{bar}│ {pct} "
            f"{dim.score:5.1f}/{dim.max_score:.0f}  {dim.details}"
        )

    grade_icons = {"A": "🟢", "B": "🟡", "C": "🔴"}
    icon = grade_icons.get(report.grade, "⚪")
    print(
        f"\n  {'总分':6s}   {report.total_score:.1f}/{report.max_total:.0f}"
        f"  等级: {icon} {report.grade}"
    )


def _collect_files(raw_paths: list[str]) -> list[Path]:
    """从命令行参数中收集所有待评分的 JSON 文件。

    支持三种输入形式：
    - 普通文件路径（如 knowledge/articles/foo.json）
    - 通配符模式（如 knowledge/articles/*.json），由 shell 展开
    - 目录路径（递归查找目录下所有 .json 文件）

    Args:
        raw_paths: 命令行传入的原始路径列表。

    Returns:
        去重、排序后的 Path 列表。
    """
    collected: set[Path] = set()

    for raw in raw_paths:
        path = Path(raw)
        if path.exists():
            if path.is_dir():
                for f in sorted(path.rglob("*.json")):
                    collected.add(f)
            elif path.suffix == ".json":
                collected.add(path)
            else:
                logger.warning("跳过非 JSON 文件: %s", path)
        else:
            matches = list(Path.cwd().glob(raw))
            if matches:
                for m in matches:
                    if m.is_file() and m.suffix == ".json":
                        collected.add(m)
            else:
                logger.warning("未找到匹配的文件: %s", raw)

    return sorted(collected)


def main() -> None:
    """命令行入口：收集文件 → 逐篇评分 → 输出汇总 → 返回退出码。

    退出码 0 表示全部文件为 B 级以上，退出码 1 表示存在 C 级或解析失败。
    """
    parser = argparse.ArgumentParser(
        prog="check_quality",
        description="对知识条目 JSON 文件进行五维度质量评分",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="JSON 文件路径（支持通配符和目录）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="静默模式，只输出汇总信息",
    )
    args = parser.parse_args()

    file_paths = _collect_files(args.files)
    if not file_paths:
        logger.error("未找到任何可评分的 JSON 文件")
        sys.exit(1)

    grade_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    has_c_grade = False
    parse_errors = 0

    for fp in file_paths:
        try:
            text = fp.read_text(encoding="utf-8")
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("%s: JSON 解析失败 — %s", fp, exc)
            has_c_grade = True
            parse_errors += 1
            continue
        except OSError as exc:
            logger.error("%s: 文件读取失败 — %s", fp, exc)
            has_c_grade = True
            parse_errors += 1
            continue

        if not isinstance(data, dict):
            logger.error("%s: 根元素不是 JSON 对象，跳过评分", fp)
            has_c_grade = True
            parse_errors += 1
            continue

        report = evaluate_quality(str(fp), data)
        grade_counts[report.grade] += 1

        if report.grade == "C":
            has_c_grade = True

        if not args.quiet:
            _print_report(report)

    total = len(file_paths)
    scored = total - parse_errors
    print(f"\n{'=' * 62}")
    print("质量评估汇总")
    print(f"{'=' * 62}")
    print(f"  文件总数: {total}")
    if parse_errors > 0:
        print(f"  解析失败: {parse_errors}")
    print(f"  成功评分: {scored}")
    print(f"  A 级 (>=80): {grade_counts.get('A', 0)}")
    print(f"  B 级 (>=60): {grade_counts.get('B', 0)}")
    print(f"  C 级 (<60) : {grade_counts.get('C', 0)}")
    print(f"{'=' * 62}")

    if has_c_grade:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s %(message)s",
        stream=sys.stderr,
    )
    main()
