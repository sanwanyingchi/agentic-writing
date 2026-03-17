"""
LLM 调用封装 — 基于 DashScope OpenAI 兼容接口

适配模型：
  - qwen3.5-plus: 规划层，支持 thinking 模式（reasoning_content）
  - qwen3-max:    Skill 执行层
  - qwen-plus:    GSB 评估层
"""
import json
import re
import time
from dataclasses import dataclass, field
from openai import OpenAI
import config


# ── 需要开启 thinking 模式的模型前缀 ─────────────────────
_THINKING_MODELS = {"qwen3.5-plus", "qwen3.5-flash"}


@dataclass
class LLMResponse:
    content: str                    # 模型最终回复
    reasoning: str = ""             # thinking 模式下的推理过程
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    model: str = ""


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        timeout=60,  # 添加60秒超时，防止无限阻塞
    )


def _is_thinking_model(model: str) -> bool:
    """判断是否是需要开启 thinking 模式的模型"""
    return any(model.startswith(prefix) for prefix in _THINKING_MODELS)


def chat(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = False,
    enable_thinking: bool = None,
) -> LLMResponse:
    """
    统一的 LLM 调用入口。

    对 qwen3.5-plus 等 thinking 模型：
      - 自动通过 extra_body 开启 thinking 模式
      - 使用流式调用(stream=True)获取 reasoning_content 和 content
      - 从流式响应的 delta 字段累积内容
    """
    model = model or config.SKILL_MODEL
    client = _get_client()

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # ── thinking 模式处理 ─────────────────────────────────
    # 如果调用者未显式指定，则根据模型名自动判断
    should_think = enable_thinking if enable_thinking is not None else _is_thinking_model(model)

    if should_think:
        kwargs["extra_body"] = {
            "enable_thinking": True,
            "thinking_budget": config.PLANNER_THINKING_BUDGET,
        }

    # ── 调用模型 ──────────────────────────────────────────
    t0 = time.time()
    
    if should_think:
        # thinking 模式：使用流式调用
        kwargs["stream"] = True
        try:
            stream_resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"LLM API 流式调用失败: {e}") from e
        
        # 累积流式响应
        content_parts = []
        reasoning_parts = []
        input_tokens = 0
        output_tokens = 0
        
        for chunk in stream_resp:
            # 提取 usage 信息（通常在最后一个 chunk）
            if hasattr(chunk, 'usage') and chunk.usage:
                usage = chunk.usage
                if hasattr(usage, 'prompt_tokens') and usage.prompt_tokens:
                    input_tokens = usage.prompt_tokens
                if hasattr(usage, 'completion_tokens') and usage.completion_tokens:
                    output_tokens = usage.completion_tokens
            
            # 提取 delta 内容
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue
            
            # 累积 reasoning_content（thinking 过程）
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
            
            # 累积 content（正文）
            if hasattr(delta, 'content') and delta.content:
                content_parts.append(delta.content)
        
        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts)
        latency = int((time.time() - t0) * 1000)
        
        # 流式响应可能没有 usage，需要估算
        if input_tokens == 0:
            # 粗略估算：中文按1.5字节/token，英文按4字符/token
            input_text = "\n".join([m.get("content", "") for m in messages])
            input_tokens = len(input_text) // 2
        if output_tokens == 0:
            output_tokens = len(content) // 2 + len(reasoning) // 2
        
        return LLMResponse(
            content=content,
            reasoning=reasoning,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            model=model,
        )
    
    else:
        # 非 thinking 模式：使用普通调用
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"LLM API 调用失败: {e}") from e
        latency = int((time.time() - t0) * 1000)

        choice = resp.choices[0]
        usage = resp.usage
        message = choice.message

        # ── 提取回复和推理内容 ────────────────────────────────
        content = message.content or ""

        # qwen3.5-plus thinking 模式下，推理过程在 reasoning_content 字段
        reasoning = ""
        # 方式1：直接属性（部分 SDK 版本支持）
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            reasoning = message.reasoning_content
        # 方式2：model_extra（openai >= 1.x 的扩展字段存储位置）
        elif hasattr(message, "model_extra") and message.model_extra:
            reasoning = message.model_extra.get("reasoning_content", "")
        # 方式3：当作 dict 访问（兜底）
        elif isinstance(message, dict):
            reasoning = message.get("reasoning_content", "")

        return LLMResponse(
            content=content,
            reasoning=reasoning,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency,
            model=model,
        )


def chat_json(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    enable_thinking: bool = None,
) -> tuple[dict, LLMResponse]:
    """
    调用模型并解析 JSON 输出。

    对 thinking 模型：最终 JSON 在 content 字段中，
    reasoning_content 是推理过程（不含 JSON）。
    """
    resp = chat(
        messages, model=model, temperature=temperature,
        max_tokens=max_tokens, json_mode=True,
        enable_thinking=enable_thinking,
    )

    text = resp.content.strip()
    data = _extract_json(text)
    return data, resp


def _extract_json(text: str) -> dict:
    """
    鲁棒的 JSON 提取：
    1. 先尝试直接解析
    2. 清理 markdown 代码块后再试
    3. 用正则提取第一个 {...} 块
    """
    # 尝试 1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 清理 markdown 包裹
    cleaned = text
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        else:
            cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 尝试 3: 正则提取第一个完整的 JSON 对象
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 所有尝试失败
    raise json.JSONDecodeError(
        f"无法从模型输出中提取 JSON。原文前200字: {text[:200]}...",
        text, 0
    )
