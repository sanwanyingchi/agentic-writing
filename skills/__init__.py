"""
Skill 基类 + 全局注册表
每个 Skill 继承 BaseSkill，通过 @register_skill 装饰器自动注册。
Agent 规划层通过 skill name + description 决定调用哪些 Skill。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# ── 全局 Skill 注册表 ─────────────────────────────────────
_SKILL_REGISTRY: dict[str, "BaseSkill"] = {}


def register_skill(cls):
    """装饰器：将 Skill 类实例化并注册到全局表"""
    instance = cls()
    _SKILL_REGISTRY[instance.name] = instance
    return cls


def get_skill(name: str) -> "BaseSkill":
    if name not in _SKILL_REGISTRY:
        raise KeyError(f"Skill '{name}' 未注册。可用: {list(_SKILL_REGISTRY.keys())}")
    return _SKILL_REGISTRY[name]


def get_all_skills() -> dict[str, "BaseSkill"]:
    return dict(_SKILL_REGISTRY)


def get_skill_catalog() -> str:
    """生成 Skill 目录描述，供 Agent 规划层读取"""
    lines = []
    for name, skill in _SKILL_REGISTRY.items():
        lines.append(
            f"- name: {name}\n"
            f"  description: {skill.description}\n"
            f"  applicable_scenarios: {skill.applicable_scenarios}\n"
            f"  input_fields: {skill.input_fields}\n"
            f"  output_fields: {skill.output_fields}"
        )
    return "\n".join(lines)


# ── Skill 执行结果 ────────────────────────────────────────
@dataclass
class SkillResult:
    skill_name: str
    success: bool
    output: dict = field(default_factory=dict)
    confidence: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str = ""


# ── Skill 基类 ────────────────────────────────────────────
class BaseSkill(ABC):
    """
    所有 Skill 的基类。子类必须实现：
    - name, description, applicable_scenarios
    - input_fields, output_fields（供 Agent 规划层了解接口）
    - execute(context) -> SkillResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 唯一标识符"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Skill 功能描述（Agent 规划层读这个来决定是否调用）"""
        ...

    @property
    def applicable_scenarios(self) -> list[str]:
        """适用场景列表，空 = 全场景通用"""
        return []

    @property
    def input_fields(self) -> str:
        """输入字段说明（自然语言，供 Agent 理解）"""
        return "context dict with query and previous skill outputs"

    @property
    def output_fields(self) -> str:
        """输出字段说明"""
        return "result dict"

    @abstractmethod
    def execute(self, context: dict) -> SkillResult:
        """
        执行 Skill。

        参数:
            context: 包含 query、scenario、以及上游 Skill 输出的上下文字典
                     context["query"]        — 用户原始 query
                     context["scenario"]     — 场景: essay / novel / xiaohongshu
                     context["skill_outputs"] — {skill_name: SkillResult} 上游结果
        返回:
            SkillResult
        """
        ...
