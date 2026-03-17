"""
小学作文场景专属 Skill
- primary_topic_analysis: 小学审题（亲切耐心，适合小学生理解）
- primary_outline: 小学提纲（叙事框架，标注重点段）
- primary_writing: 小学写作（语句通顺，适当修辞，禁止超纲）
"""
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config
import json


@register_skill
class PrimaryTopicAnalysis(BaseSkill):

    @property
    def name(self): return "primary_topic_analysis"

    @property
    def description(self):
        return (
            "小学审题：分析小学作文题目，判断体裁（记叙文/看图写话/想象作文/日记/书信），"
            "明确写什么内容、要不要写感受，指出容易跑题的地方。"
        )

    @property
    def applicable_scenarios(self): return ["essay_primary"]

    @property
    def input_fields(self): return "query, need_analysis output"

    @property
    def output_fields(self):
        return "genre, topic, content_type, need_feeling, pitfalls, tips"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        need = context.get("skill_outputs", {}).get("need_analysis", {})
        need_out = need.output if hasattr(need, "output") else (need if isinstance(need, dict) else {})

        sub_type = need_out.get("sub_type", "记叙文")
        word_count = need_out.get("word_count", 400)

        messages = [
            {"role": "system", "content": (
                "你是亲切有耐心的小学语文老师，擅长帮小学生分析作文题目。\n\n"
                "请从以下维度分析题目（用小学生能听懂的语言）：\n"
                "1. genre: 体裁判断（记叙文/看图写话/想象作文/日记/书信）\n"
                "2. topic: 核心话题是什么\n"
                "3. content_type: 写什么事/什么人/什么景\n"
                "4. need_feeling: 要不要写感受和道理（true/false）\n"
                "5. pitfalls: 容易跑题的地方（用简单的话提醒）\n"
                "6. tips: 给小朋友的写作小建议\n"
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
class PrimaryOutline(BaseSkill):

    @property
    def name(self): return "primary_outline"

    @property
    def description(self):
        return (
            "小学提纲：根据审题结果生成叙事框架，包括起因→经过（标注重点段）→结果→感受，"
            "或写景/想象作文的结构框架，每部分标注目标字数，提醒使用好词好句。"
        )

    @property
    def applicable_scenarios(self): return ["essay_primary"]

    @property
    def input_fields(self): return "query, primary_topic_analysis output"

    @property
    def output_fields(self):
        return "structure, sections[], total_words, rhetorical_tips"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        topic = context.get("skill_outputs", {}).get("primary_topic_analysis", {})
        topic_out = topic.output if hasattr(topic, "output") else (topic if isinstance(topic, dict) else {})

        need = context.get("skill_outputs", {}).get("need_analysis", {})
        need_out = need.output if hasattr(need, "output") else (need if isinstance(need, dict) else {})
        word_count = need_out.get("word_count", 400)

        genre = topic_out.get("genre", "记叙文")

        messages = [
            {"role": "system", "content": (
                f"你是小学语文老师，帮学生列作文提纲。\n\n"
                f"体裁：{genre}\n"
                f"全文目标字数：{word_count}字\n\n"
                f"请生成适合{genre}的结构框架：\n"
                f"- 记叙文：起因→经过（标注重点段）→结果→感受\n"
                f"- 写景文：总印象→分景描写→总感受\n"
                f"- 想象作文：设定→经历→结局\n"
                f"- 看图写话：图1→图2→图3（按图顺序）→道理\n"
                f"- 日记：时间/天气→事件经过→心情\n"
                f"- 书信：称呼→正文（事由+经过）→祝福语\n\n"
                f"输出 JSON：\n"
                f"- structure: 整体结构说明\n"
                f"- sections: 数组，每项包含 name, content_hint, target_words\n"
                f"- total_words: 各段字数之和\n"
                f"- rhetorical_tips: [修辞手法建议，如\"用比喻写云朵\"、\"用拟人写小草\"]\n"
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
class PrimaryWriting(BaseSkill):

    @property
    def name(self): return "primary_writing"

    @property
    def description(self):
        return (
            "小学写作：根据提纲撰写完整小学作文，语句通顺，适当使用比喻拟人排比，"
            "符合小学生认知水平，禁止超纲词汇和复杂长句。"
        )

    @property
    def applicable_scenarios(self): return ["essay_primary"]

    @property
    def input_fields(self):
        return "query, primary_topic_analysis output, primary_outline output"

    @property
    def output_fields(self): return "outline, sections[], full_text, word_count"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        outputs = context.get("skill_outputs", {})

        topic_out = _extract_output(outputs.get("primary_topic_analysis"))
        outline_out = _extract_output(outputs.get("primary_outline"))

        need_out = _extract_output(outputs.get("need_analysis"))
        word_count = need_out.get("word_count", 400) if need_out else 400

        messages = [
            {"role": "system", "content": (
                "你是小学作文辅导老师。请根据提纲写一篇完整的小学作文。\n\n"
                "写作要求：\n"
                "1. 语句通顺，段落分明\n"
                "2. 适当使用修辞手法（比喻、拟人、排比），但要自然不堆砌\n"
                "3. 符合小学生认知水平，禁止使用超纲词汇和复杂长句\n"
                "4. 写真人真事，有真情实感\n"
                "5. 重点部分要展开写详细\n\n"
                f"字数要求：必须在 {word_count}字 到 {word_count+50}字 之间，少于 {word_count}字 视为不合格\n\n"
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
