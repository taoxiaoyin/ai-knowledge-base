"""pipeline/model_client.py — 统一 LLM 调用客户端

支持 DeepSeek、Qwen、OpenAI 三种模型提供商，通过环境变量 LLM_PROVIDER 切换。
使用 httpx 直接调用 OpenAI 兼容 API，不依赖 openai SDK。

Usage:
    from pipeline.model_client import quick_chat, create_provider, chat_with_retry

    # 快捷调用
    reply = quick_chat("什么是 AI Agent？")

    # 完整调用流程
    provider = create_provider()
    response = chat_with_retry(
        provider,
        [{"role": "user", "content": "你好"}],
    )
    print(response.content)
    print(f"Token: {response.usage.total_tokens}, 成本: ${estimate_cost(provider.model, response.usage):.6f}")
    provider.close()
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    """Token 用量统计。

    Attributes:
        prompt_tokens: 输入消耗的 token 数
        completion_tokens: 输出消耗的 token 数
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """输入 + 输出 token 总数。"""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        """转换为字典，便于序列化。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """统一的 LLM 响应格式。

    Attributes:
        content: 模型返回的文本内容
        usage: Token 用量统计
    """

    content: str
    usage: Usage = field(default_factory=Usage)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，便于序列化。"""
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
        }


PRICING: dict[str, dict[str, float]] = {
    # DeepSeek
    "deepseek-chat": {"input": 0.0014, "output": 0.0028},
    "deepseek-reasoner": {"input": 0.004, "output": 0.016},
    # Qwen (通义千问)
    "qwen-plus": {"input": 0.002, "output": 0.006},
    "qwen-turbo": {"input": 0.0005, "output": 0.001},
    "qwen-max": {"input": 0.02, "output": 0.06},
    # OpenAI
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.001, "output": 0.004},
    "gpt-4.1-mini": {"input": 0.00005, "output": 0.0002},
    "gpt-4.1-nano": {"input": 0.00001, "output": 0.00004},
}

DEFAULT_PRICING: dict[str, float] = {"input": 0.002, "output": 0.006}

# 国产模型价格表（单位：元/百万 tokens），按提供商名称索引
COST_PRICING: dict[str, dict[str, float]] = {
    "deepseek": {"input": 1, "output": 2},
    "qwen": {"input": 4, "output": 12},
    "openai": {"input": 150, "output": 600},
}

DEFAULT_COST_PRICING: dict[str, float] = {"input": 4, "output": 12}


class CostTracker:
    """LLM 调用成本追踪器。

    记录每次 API 调用的 token 消耗，按提供商累积统计，
    支持估算总成本和打印成本报告。

    Attributes:
        _records: 各提供商的累积用量和调用次数
    """

    def __init__(self) -> None:
        self._records: dict[str, dict[str, int | float]] = {}

    def record(self, usage: Usage, provider: str) -> None:
        """记录一次 API 调用的 token 用量。

        Args:
            usage: 本次调用的 token 用量统计
            provider: 提供商名称（deepseek / qwen / openai）
        """
        if provider not in self._records:
            self._records[provider] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "call_count": 0,
                "total_cost": 0.0,
            }
        record = self._records[provider]
        record["prompt_tokens"] += usage.prompt_tokens
        record["completion_tokens"] += usage.completion_tokens
        record["call_count"] += 1

        cost = self._calc_cost(usage, provider)
        record["total_cost"] += cost

        logger.debug(
            "CostTracker: provider=%s, prompt=%d, completion=%d, cost=¥%.4f",
            provider,
            usage.prompt_tokens,
            usage.completion_tokens,
            cost,
        )

    @staticmethod
    def _calc_cost(usage: Usage, provider: str) -> float:
        """计算单次调用的估算成本（元）。

        Args:
            usage: Token 用量统计
            provider: 提供商名称

        Returns:
            估算成本，单位元（CNY）
        """
        prices = COST_PRICING.get(provider, DEFAULT_COST_PRICING)
        prompt_cost = usage.prompt_tokens / 1_000_000 * prices["input"]
        completion_cost = usage.completion_tokens / 1_000_000 * prices["output"]
        return prompt_cost + completion_cost

    def estimated_cost(self, provider: str) -> float:
        """返回指定提供商的累计估算成本（元）。

        Args:
            provider: 提供商名称

        Returns:
            累计成本，单位元（CNY）。若该提供商无记录则返回 0。
        """
        record = self._records.get(provider)
        if record is None:
            return 0.0
        return float(record["total_cost"])

    def report(self, provider: str | None = None) -> str:
        """生成成本报告文本。

        Args:
            provider: 指定提供商则只报告该提供商；
                      为 None 则报告所有有记录的提供商。

        Returns:
            格式化的成本报告字符串，包含每次调用明细和汇总。
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("LLM 调用成本报告")
        lines.append("=" * 60)

        providers = [provider] if provider else sorted(self._records.keys())
        grand_prompt = 0
        grand_completion = 0
        grand_cost = 0.0

        for p in providers:
            record = self._records.get(p)
            if record is None:
                lines.append(f"  提供商 {p}: 无记录")
                continue

            prompt = int(record["prompt_tokens"])
            completion = int(record["completion_tokens"])
            cost = float(record["total_cost"])
            count = int(record["call_count"])

            grand_prompt += prompt
            grand_completion += completion
            grand_cost += cost

            lines.append(f"\n  提供商: {p} (调用 {count} 次)")
            lines.append(f"    输入 token:  {prompt:>10,}")
            lines.append(f"    输出 token:  {completion:>10,}")
            lines.append(f"    总计 token:  {prompt + completion:>10,}")
            lines.append(f"    估算成本:    ¥{cost:>9.4f} 元")

        if not provider and len(self._records) > 1:
            lines.append(f"\n  {'—' * 40}")
            lines.append(f"  汇总（{len(self._records)} 个提供商）")
            lines.append(f"    输入 token:  {grand_prompt:>10,}")
            lines.append(f"    输出 token:  {grand_completion:>10,}")
            lines.append(f"    总计 token:  {grand_prompt + grand_completion:>10,}")
            lines.append(f"    估算成本:    ¥{grand_cost:>9.4f} 元")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def print_report(self, provider: str | None = None) -> None:
        """打印成本报告到终端。

        Args:
            provider: 指定提供商则只报告该提供商；
                      为 None 则报告所有有记录的提供商。
        """
        print(self.report(provider))


# 全局成本追踪器实例
tracker = CostTracker()


def estimate_tokens(text: str) -> int:
    """粗略估算文本对应的 token 数量。

    使用启发式规则：中文约 1.5 字符/token，英文约 4 字符/token。
    仅用于调用前预估，精确值以 API 返回的 usage 为准。

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数量
    """
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def estimate_cost(model: str, usage: Usage) -> float:
    """估算单次 LLM 调用的成本（USD）。

    Args:
        model: 模型名称，用于查找定价
        usage: Token 用量统计

    Returns:
        估算成本，单位 USD
    """
    prices = PRICING.get(model, DEFAULT_PRICING)
    return (
        usage.prompt_tokens / 1000 * prices["input"]
        + usage.completion_tokens / 1000 * prices["output"]
    )




class LLMProvider(ABC):
    """LLM 提供商抽象基类。

    定义统一的 chat 接口，所有提供商实现必须继承此类。
    支持上下文管理器协议（with 语句自动关闭连接）。

    Attributes:
        api_key: API 密钥
        base_url: API 基础地址
        model: 模型名称
        client: httpx 同步客户端，超时 60 秒
    """

    def __init__(
        self, api_key: str, base_url: str, model: str, provider_name: str = ""
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider_name = provider_name
        self.client = httpx.Client(timeout=60.0)

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """发送聊天请求，返回统一格式响应。

        Args:
            messages: 消息列表，每条包含 role 和 content
            temperature: 采样温度，0-2 之间，越高越随机
            max_tokens: 最大生成 token 数

        Returns:
            LLMResponse 统一响应对象
        """
        ...

    def close(self) -> None:
        """关闭底层 HTTP 连接。"""
        self.client.close()

    def __enter__(self) -> LLMProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI Chat Completions API 兼容的提供商实现。

    DeepSeek、Qwen、OpenAI 均使用相同的 /chat/completions 接口格式，
    此实现通过配置不同的 base_url 来适配各提供商。
    """

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = self.client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        choice = data["choices"][0]
        content = str(choice.get("message", {}).get("content", ""))
        usage_data: dict[str, int] = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )

        if self.provider_name:
            tracker.record(usage, self.provider_name)

        return LLMResponse(content=content, usage=usage)




PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model_env": "DEEPSEEK_MODEL",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "api_key_env": "QWEN_API_KEY",
        "base_url_env": "QWEN_BASE_URL",
        "model_env": "QWEN_MODEL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "model_env": "OPENAI_MODEL",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
}


def create_provider(provider_name: str | None = None) -> LLMProvider:
    """工厂函数：根据提供商名称创建对应的 LLM 客户端。

    通过环境变量 LLM_PROVIDER 切换提供商（默认 deepseek）。
    各提供商对应的 API Key 也从环境变量读取。

    Args:
        provider_name: 提供商名称（deepseek / qwen / openai），
                       默认读取环境变量 LLM_PROVIDER

    Returns:
        LLMProvider 实例，可直接调用 chat()

    Raises:
        ValueError: 未知的提供商名称
        RuntimeError: 缺少对应的 API Key
    """
    name = (provider_name or os.getenv("LLM_PROVIDER", "deepseek")).lower()

    if name not in PROVIDER_CONFIG:
        raise ValueError(
            f"未知的模型提供商: {name}，支持: {', '.join(PROVIDER_CONFIG.keys())}"
        )

    config = PROVIDER_CONFIG[name]
    api_key = os.getenv(config["api_key_env"], "")
    if not api_key:
        raise RuntimeError(
            f"缺少 API Key，请设置环境变量: {config['api_key_env']}"
        )

    base_url = os.getenv(config["base_url_env"], config["default_base_url"])
    model = os.getenv(config["model_env"], config["default_model"])

    logger.info("创建 LLM 客户端: provider=%s, model=%s", name, model)
    return OpenAICompatibleProvider(
        api_key=api_key, base_url=base_url, model=model, provider_name=name
    )




def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_retries: int = 3,
    backoff_base: float = 2.0,
) -> LLMResponse:
    """带指数退避重试的聊天调用。

    当遇到网络错误或 HTTP 错误时自动重试，最多 3 次，
    退避时间为 base^attempt 秒（指数退避）。

    Args:
        provider: LLM 提供商实例
        messages: 消息列表
        temperature: 采样温度
        max_tokens: 最大生成 token 数
        max_retries: 最大重试次数，默认 3
        backoff_base: 退避基数（秒），默认 2.0

    Returns:
        LLMResponse 统一响应

    Raises:
        httpx.HTTPStatusError: HTTP 状态错误且重试耗尽
        httpx.ConnectError: 连接错误且重试耗尽
        httpx.TimeoutException: 超时且重试耗尽
    """
    last_error: httpx.HTTPStatusError | httpx.ConnectError | httpx.TimeoutException | None = None

    for attempt in range(max_retries):
        try:
            response = provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if attempt > 0:
                logger.info("第 %d 次重试成功", attempt)
            return response

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    "LLM 调用失败（第 %d/%d 次），%0.1f 秒后重试: %s",
                    attempt + 1,
                    max_retries,
                    wait_time,
                    str(e),
                )
                time.sleep(wait_time)
            else:
                logger.error("LLM 调用失败，已达最大重试次数: %s", str(e))

    if last_error is not None:
        raise last_error
    raise RuntimeError("LLM 调用失败，但未捕获到具体异常")




def quick_chat(
    prompt: str,
    system: str = "你是一个 AI 技术分析助手。",
    provider_name: str | None = None,
) -> str:
    """快捷调用：一句话调用 LLM，返回纯文本。

    自动创建并销毁 provider，适合一次性调用场景。
    如需多次调用，请使用 create_provider() + chat_with_retry() 以减少连接开销。

    Args:
        prompt: 用户提示词
        system: 系统提示词
        provider_name: 提供商名称，默认读环境变量 LLM_PROVIDER

    Returns:
        LLM 返回的文本内容
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    provider = create_provider(provider_name)
    try:
        response = chat_with_retry(provider, messages)
        cost = estimate_cost(provider.model, response.usage)
        logger.info(
            "Token 用量: %d (prompt) + %d (completion) = %d, 估算成本: $%.6f",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cost,
        )
        return response.content
    finally:
        provider.close()




if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    provider_name = os.getenv("LLM_PROVIDER", "deepseek")
    print(f"=== LLM 客户端测试 ===")
    print(f"提供商: {provider_name}")
    print(f"模型: {os.getenv(f'{provider_name.upper()}_MODEL', 'default')}")

    try:
        # 1. 测试 token 估算
        sample_text = "什么是 AI Agent？AI Agent 是一种能够自主感知环境并采取行动以实现目标的智能系统。"
        estimated = estimate_tokens(sample_text)
        print(f"\n[1] Token 估算测试")
        print(f"    文本: {sample_text}")
        print(f"    估算 token: {estimated}")

        # 2. 测试快捷调用
        print(f"\n[2] quick_chat 测试")
        result = quick_chat("用一句话介绍什么是 AI Agent。")
        print(f"    回复: {result}")

        # 3. 测试完整调用流程
        print(f"\n[3] 完整调用流程测试")
        with create_provider() as p:
            messages = [
                {"role": "system", "content": "你是一个简洁的 AI 助手。"},
                {"role": "user", "content": "什么是 Transformer 架构？"},
            ]
            response = chat_with_retry(p, messages)
            cost = estimate_cost(p.model, response.usage)
            print(f"    回复: {response.content}")
            print(f"    Token 用量: prompt={response.usage.prompt_tokens}, "
                  f"completion={response.usage.completion_tokens}, "
                  f"total={response.usage.total_tokens}")
            print(f"    估算成本: ${cost:.6f} USD")

        print(f"\n[4] 累积成本报告")
        tracker.print_report()

    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        print("请检查 .env 文件中的 API Key 配置。", file=sys.stderr)
        sys.exit(1)
