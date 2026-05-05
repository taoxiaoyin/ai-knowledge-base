"""MCP Knowledge Server — 本地知识库搜索服务

基于 MCP (Model Context Protocol) 协议，通过 JSON-RPC 2.0 over stdio 与 AI 工具通信。
提供 search_articles、get_article、knowledge_stats 三个工具，
读取 knowledge/articles/ 目录下的 JSON 文章文件进行搜索和统计。
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# ── 日志：stderr 输出，不干扰 stdout 上的 JSON-RPC 通信 ──────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────
ARTICLES_DIR = Path(__file__).resolve().parent / "knowledge" / "articles"
SERVER_NAME = "knowledge-server"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

# ── 文章加载 ────────────────────────────────────────────────────────


def _load_articles(articles_dir: Path) -> list[dict[str, Any]]:
    """加载 articles 目录下所有 JSON 文件。

    Args:
        articles_dir: articles 目录路径

    Returns:
        所有文章字典的列表

    Raises:
        FileNotFoundError: articles 目录不存在
    """
    if not articles_dir.is_dir():
        raise FileNotFoundError(f"articles 目录不存在: {articles_dir}")

    articles: list[dict[str, Any]] = []
    for json_file in sorted(articles_dir.glob("*.json")):
        if json_file.name == "index.json":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                articles.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("跳过无法解析的文件 %s: %s", json_file.name, e)
            continue

    logger.info("从 %s 加载了 %d 篇文章", articles_dir, len(articles))
    return articles


# ── 工具实现 ────────────────────────────────────────────────────────


def search_articles(
    articles: list[dict[str, Any]],
    keyword: str,
    limit: int = 5,
) -> str:
    """按关键词搜索文章标题和摘要。

    Args:
        articles: 文章列表
        keyword: 搜索关键词（大小写不敏感）
        limit: 最大返回数量

    Returns:
        JSON 格式的搜索结果字符串
    """
    keyword_lower = keyword.lower()
    results: list[dict[str, Any]] = []

    for article in articles:
        title = str(article.get("title", ""))
        summary = str(article.get("summary", ""))
        if keyword_lower in title.lower() or keyword_lower in summary.lower():
            results.append(
                {
                    "id": article.get("id"),
                    "title": title,
                    "source": article.get("source"),
                    "score": article.get("relevance_score"),
                    "tags": article.get("tags", []),
                    "summary": (
                        summary[:200] + "…" if len(summary) > 200 else summary
                    ),
                }
            )

    results.sort(key=lambda a: float(a.get("score") or 0), reverse=True)
    results = results[:limit]

    if not results:
        return json.dumps(
            {"count": 0, "message": f'未找到包含关键词 "{keyword}" 的文章'},
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {"count": len(results), "results": results},
        ensure_ascii=False,
        indent=2,
    )


def get_article(
    articles: list[dict[str, Any]],
    article_id: str,
) -> str:
    """按 ID 获取文章完整内容。

    Args:
        articles: 文章列表
        article_id: 文章唯一标识

    Returns:
        JSON 格式的文章完整内容，或未找到提示
    """
    for article in articles:
        if article.get("id") == article_id:
            return json.dumps(article, ensure_ascii=False, indent=2)

    return json.dumps(
        {"error": f'未找到文章 "{article_id}"'},
        ensure_ascii=False,
        indent=2,
    )


def knowledge_stats(articles: list[dict[str, Any]]) -> str:
    """返回知识库统计信息。

    Args:
        articles: 文章列表

    Returns:
        JSON 格式的统计信息
    """
    total = len(articles)

    sources: dict[str, int] = dict(
        Counter(a.get("source", "unknown") for a in articles)
    )

    tag_counter: Counter[str] = Counter()
    for article in articles:
        tag_counter.update(article.get("tags", []))
    top_tags = tag_counter.most_common(20)

    scores = [a.get("relevance_score", 0) for a in articles]
    avg_score = sum(scores) / len(scores) if scores else 0
    high_score_count = sum(1 for s in scores if isinstance(s, (int, float)) and s >= 0.8)

    statuses: dict[str, int] = dict(
        Counter(a.get("status", "unknown") for a in articles)
    )

    stats: dict[str, Any] = {
        "total_articles": total,
        "source_distribution": sources,
        "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        "average_relevance_score": round(avg_score, 3),
        "high_score_count": high_score_count,
        "status_distribution": statuses,
    }

    return json.dumps(stats, ensure_ascii=False, indent=2)


# ── JSON-RPC 2.0 协议处理 ───────────────────────────────────────────


def _build_response(request_id: Any, result: Any) -> dict[str, Any]:
    """构造 JSON-RPC 2.0 成功响应。

    Args:
        request_id: 请求 ID
        result: 响应结果

    Returns:
        JSON-RPC 响应字典
    """
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _build_error(
    request_id: Any,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    """构造 JSON-RPC 2.0 错误响应。

    Args:
        request_id: 请求 ID
        code: 错误码
        message: 错误信息
        data: 附加数据

    Returns:
        JSON-RPC 错误响应字典
    """
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _handle_initialize(request_id: Any) -> dict[str, Any]:
    """处理 MCP initialize 请求。

    Args:
        request_id: 请求 ID

    Returns:
        JSON-RPC 响应，包含服务端能力声明
    """
    return _build_response(
        request_id,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        },
    )


def _handle_tools_list(request_id: Any) -> dict[str, Any]:
    """处理 MCP tools/list 请求，返回可用工具列表。

    Args:
        request_id: 请求 ID

    Returns:
        JSON-RPC 响应，包含工具定义列表
    """
    tools: list[dict[str, Any]] = [
        {
            "name": "search_articles",
            "description": "按关键词搜索知识库文章（匹配标题和摘要），返回相关度最高的结果",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（大小写不敏感）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大返回数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["keyword"],
            },
        },
        {
            "name": "get_article",
            "description": "按文章 ID 获取完整内容，包含标题、摘要、标签、评分等所有字段",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "文章唯一标识，如 github-20260504-001",
                    },
                },
                "required": ["article_id"],
            },
        },
        {
            "name": "knowledge_stats",
            "description": "获取知识库统计信息：文章总数、来源分布、热门标签、平均评分等",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]
    return _build_response(request_id, {"tools": tools})


def _handle_tools_call(
    request_id: Any,
    params: dict[str, Any],
    articles: list[dict[str, Any]],
) -> dict[str, Any]:
    """处理 MCP tools/call 请求，执行指定工具并返回结果。

    Args:
        request_id: 请求 ID
        params: 包含 name 和 arguments 的参数字典
        articles: 已加载的文章列表

    Returns:
        JSON-RPC 响应，包含工具执行结果
    """
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if not isinstance(arguments, dict):
        return _build_error(
            request_id,
            -32602,
            "Invalid params: arguments must be an object",
        )

    tool_map: dict[str, Any] = {
        "search_articles": search_articles,
        "get_article": get_article,
        "knowledge_stats": knowledge_stats,
    }

    handler = tool_map.get(tool_name)
    if handler is None:
        return _build_error(
            request_id,
            -32601,
            f"Method not found: {tool_name}",
        )

    try:
        if tool_name == "search_articles":
            keyword = str(arguments.get("keyword", ""))
            limit = int(arguments.get("limit", 5))
            if not keyword:
                return _build_error(
                    request_id,
                    -32602,
                    "Invalid params: keyword is required",
                )
            result_text = handler(articles, keyword, limit)
        elif tool_name == "get_article":
            article_id = str(arguments.get("article_id", ""))
            if not article_id:
                return _build_error(
                    request_id,
                    -32602,
                    "Invalid params: article_id is required",
                )
            result_text = handler(articles, article_id)
        elif tool_name == "knowledge_stats":
            result_text = handler(articles)
        else:
            return _build_error(
                request_id,
                -32601,
                f"Unknown tool: {tool_name}",
            )

        return _build_response(
            request_id,
            {
                "content": [
                    {"type": "text", "text": result_text},
                ],
            },
        )

    except Exception as e:
        logger.error("工具 %s 执行失败: %s", tool_name, e)
        return _build_error(
            request_id,
            -32000,
            f"Tool execution error: {e}",
        )


# ── 主循环 ──────────────────────────────────────────────────────────


def run_server() -> None:
    """启动 MCP 服务端主循环。

    从 stdin 逐行读取 JSON-RPC 请求，处理后在 stdout 输出响应。
    标准 JSON-RPC 错误码：
        -32700 Parse error
        -32600 Invalid Request
        -32601 Method not found
        -32602 Invalid params
        -32603 Internal error
    """
    logger.info("MCP Knowledge Server 启动")
    logger.info("articles 目录: %s", ARTICLES_DIR)

    try:
        articles = _load_articles(ARTICLES_DIR)
    except FileNotFoundError as e:
        logger.error("启动失败: %s", e)
        sys.exit(1)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError as e:
            response = _build_error(None, -32700, f"Parse error: {e}")
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        logger.debug("收到请求: method=%s, id=%s", method, request_id)

        if request_id is None:
            logger.debug("跳过通知: %s", method)
            continue

        if method == "initialize":
            response = _handle_initialize(request_id)
        elif method == "tools/list":
            response = _handle_tools_list(request_id)
        elif method == "tools/call":
            response = _handle_tools_call(request_id, params, articles)
        else:
            response = _build_error(
                request_id,
                -32601,
                f"Method not found: {method}",
            )

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    logger.info("MCP Knowledge Server 已退出")


if __name__ == "__main__":
    run_server()
