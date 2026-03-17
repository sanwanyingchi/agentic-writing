"""
小红书场景专属 Skill
- xhs_viral_copy: 爆款结构生成 + 正文写作（合并为一个 Skill）
"""
import json
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config


@register_skill
class XhsViralCopy(BaseSkill):

    @property
    def name(self): return "xhs_viral_copy"

    @property
    def description(self):
        return (
            "小红书爆款文案创作：生成吸睛标题（含数字/情绪词/痛点公式）、"
            "正文结构（钩子→痛点→方案→体验→CTA），以真人分享口吻写作。"
        )

    @property
    def applicable_scenarios(self): return ["xiaohongshu"]

    @property
    def input_fields(self): return "query, need_analysis output"

    @property
    def output_fields(self):
        return "title_candidates[], selected_title, hook, body_sections[], cta, hashtags[], full_text"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]
        need = _extract(context, "need_analysis")
        word_count = need.get("word_count", 500)

        messages = [
            {"role": "system", "content": (
                "你是小红书 10w+ 爆款博主，精通种草文案的写作技巧。\n\n"
                "创作要求：\n"
                "1. 先生成3个标题候选（使用数字/反问/情绪词/痛点公式），选最佳\n"
                "2. 正文按结构创作：\n"
                "   - hook: 开头钩子（第一句话就让人想继续看）\n"
                "   - pain_point: 引起共鸣的痛点描述\n"
                "   - solution: 产品/方法介绍（自然植入，不像广告）\n"
                "   - experience: 真实使用体验/效果对比\n"
                "   - cta: 行动号召（自然引导互动）\n"
                "3. 整体风格：像跟闺蜜聊天，真实不做作，有具体细节\n\n"
                "输出 JSON：\n"
                "- title_candidates: [3个标题]\n"
                "- selected_title: 选中的标题\n"
                "- hook: 开头钩子\n"
                "- body_sections: [{type, content}] 各段正文\n"
                "- cta: 行动号召文案\n"
                "- hashtags: [话题标签，5-8个]\n"
                "- full_text: 包含 emoji 和排版的完整文案\n"
                f"- 正文字数 {word_count} 字左右\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": f"创作需求：{query}"}
        ]

        try:
            data, resp = llm_client.chat_json(
                messages, temperature=0.8, max_tokens=4000
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


def _extract(context: dict, skill_name: str) -> dict:
    result = context.get("skill_outputs", {}).get(skill_name)
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    return result.output if hasattr(result, "output") and isinstance(result.output, dict) else {}
