"""
utils/github_api_new.py — GitHub API 仓库信息查询工具

通过 GitHub REST API v3 获取指定仓库的基本信息，
包括 Star 数、Fork 数、描述等。

Usage:
    import asyncio
    from utils.github_api_new import get_repo_info

    info = asyncio.run(get_repo_info("langchain-ai/langchain"))
    print(info["stars"], info["forks"], info["description"])
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
MAX_RETRIES = 3
RATE_LIMIT_WAIT = 10


# ============================================================
# 数据定义
# ============================================================

@dataclass
class RepoInfo:
    """GitHub 仓库基本信息。"""

    full_name: str
    description: str
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str = ""
    owner: str = ""
    html_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "description": self.description,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "language": self.language,
            "owner": self.owner,
            "html_url": self.html_url,
            "fetched_at": self.fetched_at,
        }


# ============================================================
# 核心函数
# ============================================================

async def get_repo_info(repo_full_name: str) -> dict[str, Any]:
    """从 GitHub API 获取指定仓库的基本信息。

    调用 GET /repos/{owner}/{repo} 接口，获取 Star 数、Fork 数、描述等字段。

    Args:
        repo_full_name: 仓库全名，格式为 "owner/repo"，如 "langchain-ai/langchain"

    Returns:
        包含仓库基本信息的字典，字段包括：
        - full_name: 仓库全名
        - description: 仓库描述
        - stars: Star 数量
        - forks: Fork 数量
        - open_issues: 开放 Issue 数量
        - language: 主要编程语言
        - owner: 仓库拥有者
        - html_url: 仓库主页链接
        - fetched_at: 数据获取时间（ISO 8601）

    Raises:
        ValueError: repo_full_name 格式不正确
        aiohttp.ClientError: 网络请求失败（重试耗尽后）

    Example:
        >>> info = await get_repo_info("langchain-ai/langchain")
        >>> print(f"Stars: {info['stars']}, Forks: {info['forks']}")
        Stars: 95000, Forks: 15000
    """
    parts = repo_full_name.strip("/").split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"仓库名格式错误，应为 'owner/repo'，当前输入: '{repo_full_name}'"
        )
    owner, repo = parts

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ai-knowledge-base",
    }
    github_token = os.getenv("GITHUB_TOKEN", "")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    url = f"{API_BASE}/repos/{owner}/{repo}"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

                    if resp.status == 403 and "rate limit" in (data.get("message") or "").lower():
                        logger.warning(
                            f"[GitHub] 接口限流，等待 {RATE_LIMIT_WAIT}s 后重试（{attempt}/{MAX_RETRIES}）"
                        )
                        await asyncio.sleep(RATE_LIMIT_WAIT)
                        continue

                    if resp.status == 404:
                        logger.error(f"[GitHub] 仓库不存在: {repo_full_name}")
                        return RepoInfo(
                            full_name=repo_full_name,
                            description=f"仓库不存在: {repo_full_name}",
                        ).to_dict()

                    if not resp.ok:
                        logger.error(
                            f"[GitHub] 请求失败 status={resp.status}: {data.get('message', '')}"
                        )
                        last_error = aiohttp.ClientError(
                            f"GitHub API returned {resp.status}: {data.get('message', '')}"
                        )
                        continue

                    repo_info = RepoInfo(
                        full_name=repo_full_name,
                        description=data.get("description") or "",
                        stars=data.get("stargazers_count", 0),
                        forks=data.get("forks_count", 0),
                        open_issues=data.get("open_issues_count", 0),
                        language=data.get("language") or "",
                        owner=data.get("owner", {}).get("login", owner),
                        html_url=data.get("html_url", f"https://github.com/{repo_full_name}"),
                    )
                    logger.info(
                        f"[GitHub] {repo_full_name} — ⭐ {repo_info.stars} "
                        f"🍴 {repo_info.forks} | {repo_info.language}"
                    )
                    return repo_info.to_dict()

        except asyncio.TimeoutError:
            logger.warning(
                f"[GitHub] 请求超时，重试 {attempt}/{MAX_RETRIES}: {repo_full_name}"
            )
            last_error = asyncio.TimeoutError(f"请求超时: {repo_full_name}")
        except aiohttp.ClientError as e:
            logger.warning(
                f"[GitHub] 网络错误，重试 {attempt}/{MAX_RETRIES}: {e}"
            )
            last_error = e

    logger.error(f"[GitHub] 获取仓库信息失败（已重试 {MAX_RETRIES} 次）: {repo_full_name}")
    raise last_error  # type: ignore[misc]


# ============================================================
# 同步封装
# ============================================================

def get_repo_info_sync(repo_full_name: str) -> dict[str, Any]:
    """同步版本的仓库信息获取（内部调用 async 函数）。

    适用于非异步环境或简单脚本。

    Args:
        repo_full_name: 仓库全名，格式为 "owner/repo"

    Returns:
        仓库基本信息字典
    """
    return asyncio.run(get_repo_info(repo_full_name))


# ============================================================
# CLI 入口
# ============================================================

async def _main():
    """命令行入口：根据参数查询仓库信息。"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m utils.github_api_new owner/repo [owner/repo ...]")
        sys.exit(1)

    tasks = [get_repo_info(repo) for repo in sys.argv[1:]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        repo = sys.argv[i + 1]
        print(f"\n{'=' * 60}")
        if isinstance(result, Exception):
            print(f"❌ {repo}: {result}")
        else:
            info = result
            print(f"📦 {info['full_name']}")
            print(f"   ⭐ Stars:       {info['stars']:,}")
            print(f"   🍴 Forks:       {info['forks']:,}")
            print(f"   📝 Issues:      {info['open_issues']:,}")
            print(f"   🔤 Language:    {info['language']}")
            print(f"   👤 Owner:       {info['owner']}")
            print(f"   📄 Description: {info['description']}")
            print(f"   🔗 URL:         {info['html_url']}")
            print(f"   🕐 Fetched:     {info['fetched_at']}")


if __name__ == "__main__":
    asyncio.run(_main())
