"""
AI 知识库四步流水线：采集 → 分析 → 整理 → 保存

运行方式：
    python pipeline/pipeline.py --sources github,rss --limit 20
    python pipeline/pipeline.py --sources github --limit 5
    python pipeline/pipeline.py --sources rss --limit 10
    python pipeline/pipeline.py --sources github --limit 5 --dry-run
    python pipeline/pipeline.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

from model_client import chat_with_retry, create_provider, estimate_cost, tracker

load_dotenv()

logger = logging.getLogger(__name__)

# ── 项目路径 ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"
RSS_CONFIG = Path(__file__).resolve().parent / "rss_sources.yaml"


# ── Step 1: 采集（Collect）─────────────────────────────────────────────


def collect_github(limit: int = 20) -> list[dict[str, Any]]:
    """从 GitHub Search API 采集 AI 相关热门仓库。

    使用 GitHub Search API 搜索最近一周更新的 AI/LLM/Agent 相关仓库，
    按 Star 数降序排列，返回指定数量的结果。

    Args:
        limit: 最大采集数量，默认 20。

    Returns:
        原始数据列表，每条包含 id、title、source、source_url 等字段。
    """
    token = os.getenv("GITHUB_TOKEN", "")
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"ai agent llm stars:>100 pushed:>{one_week_ago}"

    url = "https://api.github.com/search/repositories"
    params: dict[str, str | int] = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }

    results: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

            for i, repo in enumerate(data.get("items", [])[:limit]):
                now = datetime.now(timezone.utc).isoformat()
                results.append({
                    "id": f"github-{datetime.now().strftime('%Y%m%d')}-{i + 1:03d}",
                    "title": repo.get("full_name", ""),
                    "source": "github-trending",
                    "source_url": repo.get("html_url", ""),
                    "author": repo.get("owner", {}).get("login", "unknown"),
                    "published_at": repo.get("pushed_at", ""),
                    "raw_description": repo.get("description") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "collected_at": now,
                })

        logger.info("GitHub 采集完成: %d 条", len(results))
    except httpx.HTTPError as e:
        logger.error("GitHub API 请求失败: %s", e)

    return results


def collect_rss(limit: int = 20) -> list[dict[str, Any]]:
    """从配置的 RSS 源采集 AI 相关内容。

    读取 pipeline/rss_sources.yaml 中标记为 enabled 的源，
    用简易正则解析 XML，提取每条 <item> 的 <title> 和 <link>。

    Args:
        limit: 最大采集数量（所有源合计），默认 20。

    Returns:
        原始数据列表。
    """
    if not RSS_CONFIG.exists():
        logger.warning("RSS 配置文件不存在: %s", RSS_CONFIG)
        return []

    with open(RSS_CONFIG, "r", encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    sources = [
        s for s in config.get("sources", [])
        if isinstance(s, dict) and s.get("enabled", True)
    ]
    results: list[dict[str, Any]] = []
    count = 0

    with httpx.Client(timeout=20.0) as client:
        for source in sources:
            if count >= limit:
                break

            src_name = source.get("name", "unknown")
            src_url = source.get("url", "")
            if not src_url:
                logger.warning("RSS 源 [%s] 缺少 URL，跳过", src_name)
                continue

            try:
                resp = client.get(src_url)
                resp.raise_for_status()
                feed_text = resp.text

                # 简易 RSS 解析：提取 <item> 中的 <title> 和 <link>
                # 支持 CDATA、属性值带引号、link 在 title 之前或之后
                items = re.findall(
                    r"<item[^>]*>"
                    r"(?:.*?<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>|)"
                    r"(?:.*?<link[^>]*>(.*?)</link>|)"
                    r".*?</item>",
                    feed_text,
                    re.DOTALL,
                )

                # re.findall 返回的 group 顺序固定，但 title/link 可能互换了位置
                # 改用两次独立匹配确保正确
                title_matches = re.findall(
                    r"<item[^>]*>.*?<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>.*?</item>",
                    feed_text,
                    re.DOTALL,
                )
                link_matches = re.findall(
                    r"<item[^>]*>.*?<link[^>]*>(.*?)</link>.*?</item>",
                    feed_text,
                    re.DOTALL,
                )
                items = list(zip(title_matches, link_matches))

                for title, link in items:
                    if count >= limit:
                        break
                    title = title.strip()
                    link = link.strip()
                    if not title or not link:
                        continue

                    now = datetime.now(timezone.utc).isoformat()
                    count += 1
                    results.append({
                        "id": f"rss-{datetime.now().strftime('%Y%m%d')}-{count:03d}",
                        "title": title,
                        "source": f"rss:{src_name}",
                        "source_url": link,
                        "author": src_name,
                        "published_at": now,
                        "raw_description": "",
                        "category": source.get("category", "general"),
                        "collected_at": now,
                    })

                logger.info("RSS [%s] 采集: %d 条", src_name, len(items))

            except httpx.HTTPError as e:
                logger.warning("RSS 源 [%s] 请求失败: %s", src_name, e)

    logger.info("RSS 采集完成: 共 %d 条", len(results))
    return results


def step_collect(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """Step 1: 按数据源采集原始数据，保存到 knowledge/raw/。

    Args:
        sources: 数据源列表，如 ["github", "rss"]。
        limit: 每个源最大采集数量。

    Returns:
        合并后的原始数据列表。
    """
    print(f"\n{'=' * 60}")
    print(f"📥 Step 1: 采集（sources={sources}, limit={limit}）")
    print(f"{'=' * 60}")

    all_items: list[dict[str, Any]] = []

    if "github" in sources:
        all_items.extend(collect_github(limit))
    if "rss" in sources:
        all_items.extend(collect_rss(limit))

    # 保存原始数据到 knowledge/raw/
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = RAW_DIR / f"raw_{timestamp}.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print(f"  采集到 {len(all_items)} 条原始数据 → {raw_file}")

    return all_items


# ── Step 2: 分析（Analyze）─────────────────────────────────────────────


ANALYZE_PROMPT_TEMPLATE = """请分析以下 AI 技术内容，返回严格 JSON 格式的分析结果（不要包含 markdown 代码块标记）。

内容信息：
- 标题：{title}
- 来源：{source}
- 描述：{description}{extra_info}

请返回以下 JSON 格式：
{{
  "summary": "2-3 句话的中文技术摘要，约 150-200 字，说明核心内容、创新点和适用场景",
  "relevance_score": 0.85,
  "confidence": 0.90,
  "tags": ["tag1", "tag2", "tag3"],
  "tech_stack": ["python", "langchain"],
  "innovation_point": "一句话描述创新点"
}}

评分标准：
- relevance_score（0-1）：内容与 AI/LLM/Agent 领域的相关度
  - 0.9-1.0：核心 AI 技术，直接相关
  - 0.7-0.89：AI 应用或工具，较相关
  - 0.5-0.69：包含 AI 元素但不深入
  - 0.0-0.49：弱相关或无关
- confidence（0-1）：你对分析结果的确信度
  - 0.9-1.0：信息充分，分析有把握
  - 0.7-0.89：基本可以确定
  - 0.5-0.69：有一定不确定性
  - 0.0-0.49：信息不足，分析不确定

可用标签（选择最贴切的 2-5 个）：
agent, rag, mcp, llm, fine-tuning, prompt-engineering, multi-agent,
tool-use, evaluation, deployment, security, reasoning, code-generation,
vision, audio, embedding, vector-database, open-source, api,
framework, benchmark, dataset, research-paper, tutorial"""


def _parse_llm_json(raw_content: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON，去除可能的 markdown 代码块标记。

    Args:
        raw_content: LLM 返回的原始文本。

    Returns:
        解析后的字典。

    Raises:
        json.JSONDecodeError: JSON 解析失败。
    """
    content = raw_content.strip()
    # 移除可能的 markdown 代码块标记
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?\s*```$", "", content)
    return json.loads(content)


def step_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Step 2: 调用 LLM 对每条内容进行摘要、评分、标签分析。

    逐条调用 LLM，解析返回的 JSON 分析结果，将分析字段追加到原始数据上。
    单条分析失败时使用合理默认值继续，不中断整体流程。

    Args:
        items: Step 1 产出的原始数据列表。

    Returns:
        带分析字段的数据列表（包含 summary、relevance_score、confidence、
        tags、tech_stack、innovation_point、status 等字段）。
    """
    print(f"\n{'=' * 60}")
    print(f"🔍 Step 2: 分析（{len(items)} 条内容）")
    print(f"{'=' * 60}")

    if not items:
        print("  无数据可分析")
        return []

    provider = create_provider()
    analyzed: list[dict[str, Any]] = []
    total_cost = 0.0

    try:
        for i, item in enumerate(items):
            title = item.get("title", "")[:80]
            source = item.get("source", "unknown")
            desc = item.get("raw_description", "无描述")[:500]

            # 构建额外上下文信息
            extra_parts: list[str] = []
            if item.get("stars"):
                extra_parts.append(f"- Stars: {item['stars']}")
            if item.get("language"):
                extra_parts.append(f"- 编程语言: {item['language']}")
            if item.get("topics"):
                extra_parts.append(f"- Topics: {', '.join(item['topics'][:5])}")
            extra_info = "\n" + "\n".join(extra_parts) if extra_parts else ""

            prompt = ANALYZE_PROMPT_TEMPLATE.format(
                title=title,
                source=source,
                description=desc,
                extra_info=extra_info,
            )

            print(f"  [{i + 1}/{len(items)}] 分析: {title[:50]}...")

            try:
                response = chat_with_retry(
                    provider,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "你是一个 AI 技术分析专家。"
                                "请严格按 JSON 格式返回分析结果，不要包含任何其他内容。"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )

                cost = estimate_cost(provider.model, response.usage)
                total_cost += cost

                analysis = _parse_llm_json(response.content)

                # 校验并规范化字段值
                summary = str(analysis.get("summary", desc[:200]))
                relevance_score = max(
                    0.0, min(1.0, float(analysis.get("relevance_score", 0.5)))
                )
                confidence = max(
                    0.0, min(1.0, float(analysis.get("confidence", 0.5)))
                )
                tags = analysis.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                tech_stack = analysis.get("tech_stack", [])
                if not isinstance(tech_stack, list):
                    tech_stack = []
                innovation_point = str(analysis.get("innovation_point", ""))

                # 质量门控：confidence < 0.6 标记为 review
                status = "published" if confidence >= 0.6 else "review"

                enriched: dict[str, Any] = {
                    **item,
                    "summary": summary,
                    "relevance_score": relevance_score,
                    "confidence": confidence,
                    "tags": tags,
                    "tech_stack": tech_stack,
                    "innovation_point": innovation_point,
                    "status": status,
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                analyzed.append(enriched)

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    "分析结果解析失败 [%s]: %s — 使用默认值",
                    title,
                    e,
                )
                enriched = {
                    **item,
                    "summary": item.get("raw_description", "")[:200],
                    "relevance_score": 0.5,
                    "confidence": 0.3,
                    "tags": ["llm"],
                    "tech_stack": [],
                    "innovation_point": "",
                    "status": "review",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                analyzed.append(enriched)

            except (httpx.HTTPError, OSError) as e:
                logger.error(
                    "LLM 调用失败 [%s]: %s — 使用默认值",
                    title,
                    e,
                )
                enriched = {
                    **item,
                    "summary": item.get("raw_description", "")[:200],
                    "relevance_score": 0.5,
                    "confidence": 0.0,
                    "tags": ["llm"],
                    "tech_stack": [],
                    "innovation_point": "",
                    "status": "review",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                analyzed.append(enriched)

    finally:
        provider.close()

    published_count = sum(1 for a in analyzed if a.get("status") == "published")
    print(f"  分析完成: {len(analyzed)} 条（published: {published_count}, "
          f"review: {len(analyzed) - published_count}）")
    print(f"  估算总成本: ${total_cost:.6f}")

    return analyzed


# ── Step 3: 整理（Organize）───────────────────────────────────────────


def _generate_slug(title: str) -> str:
    """从标题生成 URL 友好的文件名 slug。

    提取英文单词和数字，用连字符连接，中文部分忽略。
    结果不超过 60 字符，为空时返回 "untitled"。

    Args:
        title: 文章标题。

    Returns:
        生成的 slug（小写英文 + 数字 + 连字符）。
    """
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", title)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-").lower()
    return slug[:60] if slug else "untitled"


def step_organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Step 3: 去重、格式标准化、质量校验。

    处理流程：
    1. 加载 knowledge/articles/ 已有文章的 source_url，构建去重集合
    2. 按 source_url 去重（新采集数据内 + 与历史数据比对）
    3. 过滤 status 为 "review" 的条目（confidence < 0.6），记录丢弃原因
    4. 标准化字段格式，输出统一结构的文章条目

    Args:
        items: Step 2 产出的带分析字段的数据列表。

    Returns:
        整理后的标准化文章列表（仅含 status 为 "published" 的条目）。
    """
    print(f"\n{'=' * 60}")
    print(f"📋 Step 3: 整理（{len(items)} 条内容）")
    print(f"{'=' * 60}")

    # 加载已有文章 URL
    seen_urls: set[str] = set()
    if ARTICLES_DIR.exists():
        for fpath in ARTICLES_DIR.glob("*.json"):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    existing: dict[str, Any] = json.load(fh)
                    if "source_url" in existing:
                        seen_urls.add(existing["source_url"])
            except (json.JSONDecodeError, OSError):
                pass

    dedup_count = 0
    review_count = 0
    organized: list[dict[str, Any]] = []

    for item in items:
        url = item.get("source_url", "")

        # 去重检查
        if url and url in seen_urls:
            dedup_count += 1
            logger.debug("跳过重复条目: %s", url)
            continue
        seen_urls.add(url)

        # 质量门控：过滤 review 条目
        if item.get("status") == "review":
            review_count += 1
            logger.debug(
                "过滤 review 条目 [%s]: confidence=%.2f",
                item.get("id", "unknown"),
                item.get("confidence", 0.0),
            )
            continue

        # 格式标准化
        collected_at = item.get("collected_at", "")
        date_str = (
            collected_at[:10]
            if collected_at
            else datetime.now().strftime("%Y-%m-%d")
        )
        title = item.get("title", "untitled")

        article: dict[str, Any] = {
            "id": item.get(
                "id", f"kb-{date_str.replace('-', '')}-{len(organized) + 1:03d}"
            ),
            "title": title,
            "source": item.get("source", "unknown"),
            "source_url": url,
            "collected_at": collected_at,
            "published_at": item.get("published_at", ""),
            "summary": item.get("summary", ""),
            "tags": item.get("tags", []),
            "relevance_score": item.get("relevance_score", 0.5),
            "confidence": item.get("confidence", 0.5),
            "status": item.get("status", "published"),
            "tech_stack": item.get("tech_stack", []),
            "innovation_point": item.get("innovation_point", ""),
            "author": item.get("author", "unknown"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        organized.append(article)

    print(f"  去重: 移除 {dedup_count} 条")
    print(f"  过滤 review: {review_count} 条")
    print(f"  整理后: {len(organized)} 条")

    return organized


# ── Step 4: 保存（Save）───────────────────────────────────────────────


def step_save(
    items: list[dict[str, Any]], dry_run: bool = False
) -> list[Path]:
    """Step 4: 将文章保存为独立 JSON 文件到 knowledge/articles/。

    文件命名格式：{YYYY-MM-DD}-{slug}.json。
    如遇文件名冲突自动追加序号（-1, -2, ...）。

    Args:
        items: Step 3 产出的标准化文章列表。
        dry_run: 仅模拟运行，不实际写入文件。

    Returns:
        已保存（或模拟保存）的文件路径列表。
    """
    print(f"\n{'=' * 60}")
    print(f"💾 Step 4: 保存（{len(items)} 条内容，dry_run={dry_run}）")
    print(f"{'=' * 60}")

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    saved_files: list[Path] = []

    for item in items:
        title = item.get("title", "untitled")
        slug = _generate_slug(title)
        collected_at = item.get("collected_at", "")
        date_str = (
            collected_at[:10]
            if collected_at
            else datetime.now().strftime("%Y-%m-%d")
        )
        filename = f"{date_str}-{slug}.json"
        filepath = ARTICLES_DIR / filename

        # 避免文件名冲突
        counter = 1
        while filepath.exists():
            filename = f"{date_str}-{slug}-{counter}.json"
            filepath = ARTICLES_DIR / filename
            counter += 1

        if dry_run:
            print(f"  [DRY RUN] 将保存: {filepath}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            print(f"  已保存: {filepath}")

        saved_files.append(filepath)

    print(f"\n  共{'模拟' if dry_run else ''}保存 {len(saved_files)} 个文件")
    return saved_files


# ── 主流程 ────────────────────────────────────────────────────────────


def _load_latest_raw() -> list[dict[str, Any]]:
    """读取 knowledge/raw/ 目录中最新的原始数据文件。

    用于分步执行场景（如仅运行 --steps 2,3,4），从磁盘加载
    上一步（Step 1 采集）已保存的原始数据继续处理。

    Returns:
        原始数据列表。

    Raises:
        FileNotFoundError: 目录不存在或无原始数据文件。
    """
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"原始数据目录不存在: {RAW_DIR}，请先运行 --steps 1 采集数据"
        )
    raw_files = sorted(
        RAW_DIR.glob("raw_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not raw_files:
        raise FileNotFoundError(
            f"{RAW_DIR} 中没有原始数据文件，请先运行 --steps 1 采集数据"
        )
    latest_file = raw_files[0]
    logger.info("加载最新原始数据: %s", latest_file)
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    steps: set[int] | None = None,
) -> dict[str, Any]:
    """运行四步流水线：采集 → 分析 → 整理 → 保存，可按步选择执行。

    支持分步执行场景：
        - --steps 1         只采集并保存原始数据（免费，无 LLM 调用）
        - --steps 2,3,4     从磁盘读取已采集数据，执行分析/整理/保存
        - --steps 1,2,3,4   完整流水线（默认）

    Args:
        sources: 数据源列表，如 ["github", "rss"]。
        limit: 每个源最大采集数量，默认 20。
        dry_run: 仅模拟运行（Step 4 不实际写入文件）。
        steps: 要执行的步骤编号集合，默认 {1,2,3,4}。

    Returns:
        运行统计信息字典，包含 collected、analyzed、organized、saved
        计数和 elapsed_seconds、dry_run 标志。
    """
    if steps is None:
        steps = {1, 2, 3, 4}

    start_time = datetime.now()
    step_labels = ["采集", "分析", "整理", "保存"]
    included_steps = sorted(steps)
    step_desc = ", ".join(step_labels[i - 1] for i in included_steps)
    print(f"\n{'#' * 60}")
    print(f"# AI 知识库流水线")
    print(f"# 启动时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 数据源: {', '.join(sources)}")
    print(f"# 采集限制: {limit} 条/源")
    print(f"# 执行步骤: {step_desc}")
    print(f"# 模式: {'模拟运行' if dry_run else '正式运行'}")
    print(f"{'#' * 60}")

    raw_items: list[dict[str, Any]] = []
    analyzed_items: list[dict[str, Any]] = []
    organized_items: list[dict[str, Any]] = []
    saved_files: list[Path] = []

    # Step 1: 采集（或从磁盘读取）
    if 1 in steps:
        raw_items = step_collect(sources, limit)
        if not raw_items:
            print("\n⚠️  没有采集到任何数据，流水线结束。")
            return {
                "collected": 0, "analyzed": 0, "organized": 0, "saved": 0,
                "elapsed_seconds": 0.0, "dry_run": dry_run,
            }
    else:
        raw_items = _load_latest_raw()
        print(f"\n📂 从磁盘加载了 {len(raw_items)} 条已采集数据")

    # Step 2: 分析
    if 2 in steps:
        analyzed_items = step_analyze(raw_items)
    else:
        analyzed_items = raw_items

    # Step 3: 整理
    if 3 in steps:
        organized_items = step_organize(analyzed_items)
    else:
        organized_items = analyzed_items

    # Step 4: 保存
    if 4 in steps:
        saved_files = step_save(organized_items, dry_run=dry_run)
    else:
        saved_files = []

    # 统计
    elapsed = (datetime.now() - start_time).total_seconds()
    stats = {
        "collected": len(raw_items),
        "analyzed": len(analyzed_items),
        "organized": len(organized_items),
        "saved": len(saved_files),
        "elapsed_seconds": round(elapsed, 1),
        "dry_run": dry_run,
    }

    print(f"\n{'#' * 60}")
    print(f"# ✅ 流水线完成！")
    print(f"# 耗时: {elapsed:.1f} 秒")
    print(
        f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} → "
        f"整理: {stats['organized']} → 保存: {stats['saved']}"
    )
    print(f"{'#' * 60}\n")

    # 打印 LLM Token 用量统计（仅当有调用记录时）
    if tracker._records:
        tracker.print_report()
        print()

    return stats


# ── CLI 入口 ──────────────────────────────────────────────────────────


def _build_argparser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        配置好的 ArgumentParser 实例。
    """
    parser = argparse.ArgumentParser(
        description="AI 知识库采集流水线 — 从 GitHub/RSS 采集、分析、整理、保存",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python pipeline/pipeline.py --sources github,rss --limit 20      # 完整流水线
    python pipeline/pipeline.py --steps 1                            # 仅采集原始数据
    python pipeline/pipeline.py --steps 2,3,4                        # 仅分析入库
    python pipeline/pipeline.py --sources github --limit 5           # 只采集 GitHub
    python pipeline/pipeline.py --sources rss --limit 10             # 只采集 RSS
    python pipeline/pipeline.py --sources github --limit 5 --dry-run # 模拟运行
    python pipeline/pipeline.py --verbose                            # 详细日志
        """,
    )
    parser.add_argument(
        "--steps",
        type=str,
        default="1,2,3,4",
        help=(
            "要执行的步骤，逗号分隔。"
            "1=采集, 2=分析(LLM), 3=整理, 4=保存（默认: 1,2,3,4）"
        ),
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="数据源，逗号分隔。可选: github, rss（默认: github,rss）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每个源的最大采集数量（默认: 20）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行模式：执行采集/分析/整理，但不实际保存文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示 DEBUG 级别详细日志",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM 提供商，覆盖环境变量 LLM_PROVIDER。可选: deepseek, qwen, openai",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI 入口函数。

    解析命令行参数，配置日志，启动流水线。

    Args:
        argv: 命令行参数列表，None 时使用 sys.argv[1:]。
    """
    parser = _build_argparser()
    args = parser.parse_args(argv)

    # 覆盖 LLM 提供商
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 解析数据源
    sources = [s.strip().lower() for s in args.sources.split(",")]

    # 解析步骤
    steps = {int(s.strip()) for s in args.steps.split(",")}
    valid_steps = {1, 2, 3, 4}
    if not steps.issubset(valid_steps):
        invalid = steps - valid_steps
        print(f"错误: 无效步骤 {invalid}，有效值为 1,2,3,4")
        sys.exit(2)

    # 运行流水线
    stats = run_pipeline(
        sources=sources,
        limit=args.limit,
        dry_run=args.dry_run,
        steps=steps,
    )

    # 如果采集产量为 0，返回非零退出码
    if stats["collected"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
