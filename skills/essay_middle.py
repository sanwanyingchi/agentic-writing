"""
初中作文场景专属 Skill
- middle_topic_analysis: 初中审题（大题小做，识别深层含义）
- middle_outline: 初中提纲（详略得当，细节描写）
- middle_writing: 初中写作（细节+心理+自然升华）
"""
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config
import json


@register_skill
class MiddleTopicAnalysis(BaseSkill):

    @property
    def name(self): return "middle_topic_analysis"

    @property
    def description(self):
        return (
            "初中审题：分析初中作文题目，判断体裁（记叙文/半命题/话题/材料/读后感），"
            "挖掘表层和深层含义，指导'大题小做'切入角度，指出初中常见审题陷阱。"
        )

    @property
    def applicable_scenarios(self): return ["essay_middle"]

    @property
    def input_fields(self): return "query, need_analysis output"

    @property
    def output_fields(self):
        return "genre, surface_meaning, deep_meaning, angle, pitfalls, material_hints"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        need = context.get("skill_outputs", {}).get("need_analysis", {})
        need_out = need.output if hasattr(need, "output") else (need if isinstance(need, dict) else {})

        sub_type = need_out.get("sub_type", "记叙文")
        word_count = need_out.get("word_count", 600)

        messages = [
            {"role": "system", "content": (
                "你是经验丰富的初中语文骨干教师，擅长指导学生审题立意。\n\n"
                "请从以下维度分析题目：\n"
                "1. genre: 体裁判断（记叙文/半命题作文/话题作文/材料作文/读后感）\n"
                "2. surface_meaning: 题目的表层含义（字面意思）\n"
                "3. deep_meaning: 题目的深层含义（情感、成长、价值层面）\n"
                "4. angle: 建议的切入角度（如何'大题小做'，用具体小事写大主题）\n"
                "5. pitfalls: 初中常见审题陷阱（如把'成长'写成流水账、把'温暖'写成套路亲情）\n"
                "6. material_hints: [可用的素材方向，要具体可感]\n"
                "7. confidence: 0-1\n\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"作文题目：{query}\n"
                f"文体：{sub_type}\n"
                f"字数要求：{word_count}字"
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
class MiddleOutline(BaseSkill):

    @property
    def name(self): return "middle_outline"

    @property
    def description(self):
        return (
            "初中提纲：生成记叙文或半命题/话题作文的框架，"
            "包含开头点题、铺垫、核心事件（详写）、转折/高潮、结尾升华，"
            "每部分标注目标字数，要求开头结尾有文采，中间有细节描写。"
        )

    @property
    def applicable_scenarios(self): return ["essay_middle"]

    @property
    def input_fields(self): return "query, middle_topic_analysis output"

    @property
    def output_fields(self):
        return "structure, sections[], total_words, writing_requirements"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        topic = context.get("skill_outputs", {}).get("middle_topic_analysis", {})
        topic_out = topic.output if hasattr(topic, "output") else (topic if isinstance(topic, dict) else {})

        need = context.get("skill_outputs", {}).get("need_analysis", {})
        need_out = need.output if hasattr(need, "output") else (need if isinstance(need, dict) else {})
        word_count = need_out.get("word_count", 600)

        genre = topic_out.get("genre", "记叙文")

        messages = [
            {"role": "system", "content": (
                f"你是初中语文骨干教师，帮学生列作文提纲。\n\n"
                f"体裁：{genre}\n"
                f"全文目标字数：{word_count}字\n\n"
                f"请生成适合{genre}的结构框架：\n"
                f"- 记叙文：开头点题→铺垫→核心事件（详写，占40%）→转折/高潮→结尾扣题升华\n"
                f"- 半命题作文：先补题说明→再按记叙文结构\n"
                f"- 话题作文：定角度说明→再按记叙文结构\n"
                f"- 材料作文：引材料→分析→联系自身→升华\n"
                f"- 读后感：引→议→联→结\n\n"
                f"写作要求：\n"
                f"1. 开头结尾要有'文采'（可用修辞、环境描写、引用）\n"
                f"2. 中间要有细节描写（动作、神态、心理、环境）\n"
                f"3. 结尾升华要从事件自然引出感悟，不能生硬说教\n\n"
                f"输出 JSON：\n"
                f"- structure: 整体结构说明\n"
                f"- sections: 数组，每项包含 name, content_hint, target_words, requirements（该段特殊要求）\n"
                f"- total_words: 各段字数之和\n"
                f"- writing_requirements: {{开头要求, 中间要求, 结尾要求}}\n"
                f"只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"作文题目：{query}\n\n"
                f"审题结果：\n{_safe_dump(topic_out)}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(messages, temperature=0.4)
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
class MiddleWriting(BaseSkill):

    @property
    def name(self): return "middle_writing"

    @property
    def description(self):
        return (
            "初中写作：根据提纲撰写完整初中作文，有细节描写（五感）、适当心理活动，"
            "语言比小学成熟但不模仿高中腔，结尾升华自然不突兀。"
        )

    @property
    def applicable_scenarios(self): return ["essay_middle"]

    @property
    def input_fields(self):
        return "query, middle_topic_analysis output, middle_outline output"

    @property
    def output_fields(self): return "outline, sections[], full_text, word_count"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        outputs = context.get("skill_outputs", {})

        topic_out = _extract_output(outputs.get("middle_topic_analysis"))
        outline_out = _extract_output(outputs.get("middle_outline"))

        need_out = _extract_output(outputs.get("need_analysis"))
        word_count = need_out.get("word_count", 600) if need_out else 600

        messages = [
            {"role": "system", "content": (
                "你是初中语文骨干教师。请根据提纲写一篇完整的初中作文。\n\n"
                "写作要求：\n"
                "1. 语言比小学更成熟，但不要模仿高中腔，保持初中生口吻\n"
                "2. 有具体的细节描写（视觉、听觉、触觉、嗅觉、味觉）\n"
                "3. 有适当的心理活动描写，但不冗长\n"
                "4. 开头可以有文采（修辞、环境、引用），但要自然\n"
                "5. 结尾升华要从事件自然引出，不生硬不说教\n"
                "6. 重点部分要详写，有层次感\n\n"
                f"字数要求：必须在 {word_count}字 到 {word_count+80}字 之间，少于 {word_count}字 视为不合格\n\n"
                "输出 JSON：\n"
                "- outline: 简要提纲回顾\n"
                "- sections: [{title, content}] 各段落内容\n"
                "- full_text: 拼接后的完整文章（代码拼接，不要让模型拼）\n"
                "- word_count: 文章总字数\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"作文题目：{query}\n\n"
                f"审题结果：\n{_safe_dump(topic_out)}\n\n"
                f"提纲框架：\n{_safe_dump(outline_out)}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(
                messages, temperature=config.SKILL_TEMPERATURE, max_tokens=8000
            )
            
            # 代码中拼接 full_text
            sections = data.get("sections", [])
            full_text_parts = []
            for sec in sections:
                content = sec.get("content", "") if isinstance(sec, dict) else ""
                if content:
                    full_text_parts.append(content)
            full_text = "\n\n".join(full_text_parts)
            
            # 更新数据
            data["full_text"] = full_text
            data["word_count"] = len(full_text)
            
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
