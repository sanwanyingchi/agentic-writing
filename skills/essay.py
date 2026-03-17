"""
作文场景专属 Skill
- essay_topic_analysis: 审题
- essay_thesis: 立意
- essay_writing: 提纲 + 分段写作（合并为一个 Skill 降低调用次数）
"""
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config


@register_skill
class EssayTopicAnalysis(BaseSkill):

    @property
    def name(self): return "essay_topic_analysis"

    @property
    def description(self):
        return (
            "审题：深度解析作文题目的核心概念、多维含义（表层/中层/深层）、"
            "写作要求（显性+隐性）和常见审题陷阱，输出结构化审题结果。"
        )

    @property
    def applicable_scenarios(self): return ["essay"]

    @property
    def input_fields(self): return "query, need_analysis output"

    @property
    def output_fields(self):
        return "topic_keyword, dimensions[], pitfalls[], recommended_approach"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        need = context.get("skill_outputs", {}).get("need_analysis", {})
        need_out = need.output if hasattr(need, "output") else (need if isinstance(need, dict) else {})

        sub_type = need_out.get("sub_type", "议论文")
        word_count = need_out.get("word_count", 800)

        messages = [
            {"role": "system", "content": (
                "你是经验丰富的高中语文教师，专精作文审题。\n\n"
                "请从以下维度分析题目：\n"
                "1. topic_keyword: 核心关键词\n"
                "2. dimensions: 至少3个解读角度，每个包含 angle, explanation, depth_level(surface/moderate/deep), example_directions[]\n"
                "3. writing_requirements: {explicit: [], implicit: []}\n"
                "4. pitfalls: [{trap, why_wrong}] 常见陷阱\n"
                "5. recommended_approach: 综合推荐的审题切入方向\n"
                "6. confidence: 0-1\n\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"题目：{query}\n文体：{sub_type}\n字数要求：{word_count}字"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(messages, temperature=0.3)
            return SkillResult(
                skill_name=self.name, success=True,
                output=data,
                confidence=data.get("confidence", 0.8),
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(skill_name=self.name, success=False, error=str(e))


@register_skill
class EssayThesis(BaseSkill):

    @property
    def name(self): return "essay_thesis"

    @property
    def description(self):
        return (
            "立意：基于审题结果生成3个候选立意方向，每个包含核心论点、"
            "论证思路和适配的素材方向，并推荐最优立意。"
        )

    @property
    def applicable_scenarios(self): return ["essay"]

    @property
    def input_fields(self): return "query, essay_topic_analysis output"

    @property
    def output_fields(self):
        return "candidates[{thesis, reasoning_path, material_hints}], selected_index, selection_reason"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        topic = context.get("skill_outputs", {}).get("essay_topic_analysis", {})
        topic_out = topic.output if hasattr(topic, "output") else (topic if isinstance(topic, dict) else {})

        messages = [
            {"role": "system", "content": (
                "你是高考作文命题研究专家。基于审题分析结果，生成3个候选立意。\n\n"
                "输出 JSON：\n"
                "- candidates: 数组，每个元素：\n"
                "  - thesis: 核心论点（一句话）\n"
                "  - reasoning_path: 论证思路概述\n"
                "  - material_hints: [可用的素材方向]\n"
                "  - depth: surface / moderate / deep\n"
                "- selected_index: 推荐的候选编号 (0-based)\n"
                "- selection_reason: 推荐理由\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"用户题目：{query}\n\n"
                f"审题分析结果：\n{_safe_dump(topic_out)}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(messages, temperature=0.5)
            return SkillResult(
                skill_name=self.name, success=True,
                output=data, confidence=0.85,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(skill_name=self.name, success=False, error=str(e))


@register_skill
class EssayWriting(BaseSkill):

    @property
    def name(self): return "essay_writing"

    @property
    def description(self):
        return (
            "分段写作：基于选定的立意和审题结果，先生成三段论提纲，"
            "再逐段（开头→论证1→论证2→结尾）撰写全文，确保各段衔接连贯。"
        )

    @property
    def applicable_scenarios(self): return ["essay"]

    @property
    def input_fields(self):
        return "query, essay_topic_analysis output, essay_thesis output"

    @property
    def output_fields(self): return "outline, sections[], full_text"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        outputs = context.get("skill_outputs", {})

        topic_out = _extract_output(outputs.get("essay_topic_analysis"))
        thesis_out = _extract_output(outputs.get("essay_thesis"))

        # 取推荐的立意
        selected = {}
        if thesis_out:
            candidates = thesis_out.get("candidates", [])
            idx = thesis_out.get("selected_index", 0)
            if candidates and idx < len(candidates):
                selected = candidates[idx]

        need_out = _extract_output(outputs.get("need_analysis"))
        word_count = need_out.get("word_count", 800) if need_out else 800

        messages = [
            {"role": "system", "content": (
                "你是高考满分作文写作指导老师。请按以下步骤写作：\n\n"
                "第一步：根据立意生成提纲（outline），包含开头、论证段×2、结尾的主旨\n"
                "第二步：逐段写作，确保：\n"
                "  - 开头：引出话题，明确论点，不超过总篇幅15%\n"
                "  - 论证1：正面论证，有具体素材支撑\n"
                "  - 论证2：辩证思考或反面论证，体现思维深度\n"
                "  - 结尾：升华主题，回扣标题，有力收束\n"
                "  - 段落间有过渡衔接\n\n"
                "输出 JSON：\n"
                "- outline: {intro, body1, body2, conclusion} 每项一句话概述\n"
                "- sections: [{title, content}] 四个段落\n"
                "- full_text: 拼接后的完整文章\n"
                f"- 总字数必须在 {word_count}字 到 {word_count+100}字 之间，少于 {word_count}字 视为不合格\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"题目：{query}\n\n"
                f"审题要点：{topic_out.get('recommended_approach', '无')}\n"
                f"选定立意：{selected.get('thesis', '无')}\n"
                f"论证思路：{selected.get('reasoning_path', '无')}\n"
                f"素材方向：{selected.get('material_hints', [])}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(
                messages, temperature=config.SKILL_TEMPERATURE, max_tokens=10000
            )
            return SkillResult(
                skill_name=self.name, success=True,
                output=data, confidence=0.85,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(skill_name=self.name, success=False, error=str(e))


# ── 工具函数 ──────────────────────────────────────────────
import json

def _extract_output(result) -> dict:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "output"):
        return result.output if isinstance(result.output, dict) else {}
    return {}

def _safe_dump(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)
