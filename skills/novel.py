"""
小说场景专属 Skill
- novel_worldbuilding: 世界观 + 角色设定
- novel_writing: 情节大纲 + 场景写作
"""
import json
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config


@register_skill
class NovelWorldbuilding(BaseSkill):

    @property
    def name(self): return "novel_worldbuilding"

    @property
    def description(self):
        return (
            "小说世界观与角色设定：根据子类型（玄幻/都市/穿越等）"
            "生成修炼体系/社会架构、主角人设、金手指设定、初始冲突。"
        )

    @property
    def applicable_scenarios(self): return ["novel"]

    @property
    def input_fields(self): return "query, need_analysis output (sub_type, style)"

    @property
    def output_fields(self):
        return "world_setting, power_system, protagonist, initial_conflict, tone"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        need = _extract(context, "need_analysis")
        sub_type = need.get("sub_type", "玄幻")

        messages = [
            {"role": "system", "content": (
                "你是网文创作顾问，精通各类型小说的世界观构建。\n\n"
                "根据用户需求生成世界观和角色设定，输出 JSON：\n"
                "- world_setting: 世界背景描述（2-3句话）\n"
                "- power_system: 力量体系/社会规则（如修炼等级、科技水平等）\n"
                "- protagonist: {name, personality, background, golden_finger}\n"
                "  golden_finger = 主角的特殊能力/优势\n"
                "- supporting_cast: [{name, role, relation_to_protagonist}] 2-3个关键配角\n"
                "- initial_conflict: 开篇核心矛盾\n"
                "- tone: 整体基调（热血/轻松/暗黑等）\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"用户需求：{query}\n小说类型：{sub_type}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(messages, temperature=0.7)
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
class NovelWriting(BaseSkill):

    @property
    def name(self): return "novel_writing"

    @property
    def description(self):
        return (
            "小说写作：先清晰呈现背景设定（世界观、主角、金手指、冲突），"
            "然后只写第一章（开篇要有钩子，结尾留悬念），不写后续章节。"
        )

    @property
    def applicable_scenarios(self): return ["novel"]

    @property
    def input_fields(self):
        return "query, novel_worldbuilding output"

    @property
    def output_fields(self): return "background, chapter1_title, chapter1_content, full_text"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        world = _extract(context, "novel_worldbuilding")
        need = _extract(context, "need_analysis")
        word_count = need.get("word_count", 2000)

        messages = [
            {"role": "system", "content": (
                "你是网文写手，擅长写出让读者欲罢不能的开篇。\n\n"
                "请按以下结构创作：\n\n"
                "【第一部分：背景设定】（占总输出约20%）\n"
                "清晰介绍：\n"
                "- 世界背景：时间、地点、基本社会状况\n"
                "- 主角身份：姓名、现状、核心目标\n"
                "- 金手指/优势：主角有什么特殊能力或先知优势\n"
                "- 核心冲突：主角面临的最大危机或挑战\n\n"
                "【第二部分：第一章正文】（占总输出约80%）\n"
                "要求：\n"
                "- 标题格式：第X章：标题\n"
                "- 开头第一段就要有钩子（悬念/冲突/反常/震惊）\n"
                "- 中间情节推进，对话和描写交替\n"
                "- 结尾必须留悬念或爆点，让读者想继续读\n"
                "- 只写第一章，不要写第二章预告\n\n"
                "输出 JSON：\n"
                "- background: 背景设定（清晰的一段介绍）\n"
                "- chapter1_title: 第一章标题\n"
                "- chapter1_content: 第一章正文\n"
                "- full_text: 拼接后的完整文本（背景设定 + 换行 + 第一章）\n"
                f"- 第一章字数控制在 {word_count} 字左右\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"用户需求：{query}\n\n"
                f"世界观设定：\n{json.dumps(world, ensure_ascii=False, indent=2)}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(
                messages, temperature=config.SKILL_TEMPERATURE, max_tokens=8000
            )
            
            # 代码中拼接 full_text
            background = data.get("background", "")
            chapter1_title = data.get("chapter1_title", "")
            chapter1_content = data.get("chapter1_content", "")
            
            full_text_parts = []
            if background:
                full_text_parts.append(f"【背景设定】\n{background}")
            if chapter1_title and chapter1_content:
                full_text_parts.append(f"\n【{chapter1_title}】\n{chapter1_content}")
            
            data["full_text"] = "\n\n".join(full_text_parts)
            
            return SkillResult(
                skill_name=self.name, success=True,
                output=data, confidence=0.85,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(skill_name=self.name, success=False, error=str(e))


def _extract(context: dict, skill_name: str) -> dict:
    result = context.get("skill_outputs", {}).get(skill_name)
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    return result.output if hasattr(result, "output") and isinstance(result.output, dict) else {}
