#!/usr/bin/env python3
"""校验知识条目 JSON 文件的格式合规性。

支持单文件和多文件（通配符）两种输入模式，逐文件检查 JSON 结构、
必填字段、字段类型、ID 格式、状态枚举、URL 格式等。

用法:
    python hooks/validate_json.py <json_file> [json_file2 ...]
    python hooks/validate_json.py knowledge/articles/*.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
}

VALID_STATUSES: frozenset[str] = frozenset(
    {"draft", "review", "published", "archived"}
)
VALID_AUDIENCES: frozenset[str] = frozenset(
    {"beginner", "intermediate", "advanced"}
)

_ID_RE = re.compile(r"^[a-z][a-z0-9]*[a-z0-9-]*-\d{8}-\d{3}$")
_URL_RE = re.compile(r"^https?://")

MIN_SUMMARY_LEN = 20
MIN_TAGS_COUNT = 1
SCORE_MIN = 1
SCORE_MAX = 10


def _validate_single(file_path: Path) -> list[str]:
    """校验单个 JSON 文件。

    按以下顺序检查：JSON 可解析性 → 根类型 → 必填字段存在性与类型 →
    ID 格式 → status 枚举 → URL 格式 → summary 长度 → tags 数量 →
    可选字段合法性。

    Args:
        file_path: 待校验 JSON 文件的路径。

    Returns:
        错误信息列表；空列表表示校验全部通过。
    """
    errors: list[str] = []

    try:
        text = file_path.read_text(encoding="utf-8")
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"{file_path}: JSON 解析失败 — {exc}"]
    except OSError as exc:
        return [f"{file_path}: 文件读取失败 — {exc}"]

    if not isinstance(data, dict):
        return [
            f"{file_path}: 根元素类型错误 "
            f"（期望 dict，实际 {type(data).__name__}）"
        ]

    missing_types: list[str] = []
    missing_fields: list[str] = []
    for field, exp_type in REQUIRED_FIELDS.items():
        if field not in data:
            missing_fields.append(field)
            continue
        if not isinstance(data[field], exp_type):
            missing_types.append(
                f"'{field}'（期望 {exp_type.__name__}，"
                f"实际 {type(data[field]).__name__}）"
            )

    if missing_fields:
        errors.append(
            f"{file_path}: 缺少必填字段: {', '.join(missing_fields)}"
        )
    if missing_types:
        errors.append(
            f"{file_path}: 字段类型错误: {'; '.join(missing_types)}"
        )

    if missing_fields:
        return errors

    item_id = str(data["id"])
    if not _ID_RE.match(item_id):
        errors.append(
            f"{file_path}: ID 格式错误 '{item_id}'，"
            f"期望格式: {{source}}-{{YYYYMMDD}}-{{NNN}}"
        )

    status_val = data["status"]
    if status_val not in VALID_STATUSES:
        errors.append(
            f"{file_path}: status '{status_val}' 不合法，"
            f"允许值: {', '.join(sorted(VALID_STATUSES))}"
        )

    url_val = str(data["source_url"])
    if not _URL_RE.match(url_val):
        errors.append(
            f"{file_path}: source_url 格式错误 '{url_val}'，"
            "必须以 http:// 或 https:// 开头"
        )

    summary_val = str(data["summary"])
    if len(summary_val) < MIN_SUMMARY_LEN:
        errors.append(
            f"{file_path}: summary 长度不足 "
            f"（至少 {MIN_SUMMARY_LEN} 字，当前 {len(summary_val)} 字）"
        )

    tags_val = data["tags"]
    if len(tags_val) < MIN_TAGS_COUNT:
        errors.append(
            f"{file_path}: tags 至少需要 {MIN_TAGS_COUNT} 个标签，"
            f"当前 {len(tags_val)} 个"
        )

    if "score" in data:
        score = data["score"]
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or score < SCORE_MIN
            or score > SCORE_MAX
        ):
            errors.append(
                f"{file_path}: score '{score}' 不在 "
                f"{SCORE_MIN}-{SCORE_MAX} 范围，或类型不是数字"
            )

    if "audience" in data:
        audience = data["audience"]
        if audience not in VALID_AUDIENCES:
            errors.append(
                f"{file_path}: audience '{audience}' 不合法，"
                f"允许值: {', '.join(sorted(VALID_AUDIENCES))}"
            )

    return errors


def _collect_files(raw_paths: list[str]) -> list[Path]:
    """从命令行参数中收集所有待校验的 JSON 文件。

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
                logger.warning("未找到匹配的文件或目录: %s", raw)

    return sorted(collected)


def main() -> None:
    """命令行入口：收集文件 → 逐条校验 → 输出汇总 → 返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="validate_json",
        description="校验知识条目 JSON 文件的格式合规性",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="JSON 文件路径（支持通配符和目录）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="同时显示校验通过的文件",
    )
    args = parser.parse_args()

    file_paths = _collect_files(args.files)
    if not file_paths:
        logger.error("未找到任何可校验的 JSON 文件")
        sys.exit(1)

    per_file_errors: dict[str, list[str]] = {}
    passed = 0
    failed = 0

    for fp in file_paths:
        errs = _validate_single(fp)
        if errs:
            failed += 1
            per_file_errors[str(fp)] = errs
            for e in errs:
                logger.error(e)
        else:
            passed += 1
            if args.verbose:
                logger.info("✅ 通过: %s", fp)

    total = passed + failed
    print("=" * 48)
    print("校验汇总")
    print("=" * 48)
    print(f"文件总数  : {total}")
    print(f"通过     : {passed}")
    print(f"失败     : {failed}")
    print("-" * 48)

    if per_file_errors:
        print("\n失败详情:")
        for file_name, errs in per_file_errors.items():
            print(f"\n  📄 {file_name}")
            for err in errs:
                print(f"    ❌ {err.split(': ', 1)[-1] if ': ' in err else err}")
        print()
        sys.exit(1)

    print("\n全部文件校验通过 ✅")
    sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-7s %(message)s",
        stream=sys.stderr,
    )
    main()
