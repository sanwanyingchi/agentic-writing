"""
共享 Skill — 三场景通用
- need_analysis: 需求分析
- quality_review: 质量自检
- format_polish: 格式优化
"""
from skills import BaseSkill, SkillResult, register_skill
import llm_client
import config


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 需求分析 Skill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@register_skill
class NeedAnalysis(BaseSkill):

    @property
    def name(self): return "need_analysis"

    @property
    def description(self):
        return (
            "分析用户 query，提取写作场景、文体类型、字数要求、风格偏好、"
            "目标受众等结构化约束，生成 Task Context 供后续 Skill 消费。"
        )

    @property
    def applicable_scenarios(self): return ["essay", "essay_primary", "essay_middle", "novel", "xiaohongshu"]

    @property
    def input_fields(self): return "query (用户原始输入)"

    @property
    def output_fields(self):
        return "scenario, sub_type, word_count, style, audience, constraints, complexity"

    def execute(self, context: dict) -> SkillResult:
        query = context["query"]

        messages = [
            {"role": "system", "content": (
                "你是写作需求分析专家。分析用户的写作请求，提取结构化信息。\n"
                "输出 JSON，字段：\n"
                "- scenario: essay / essay_primary / essay_middle / novel / xiaohongshu\n"
                "  * essay: 高中/高考/大学作文（议论文、记叙文、材料作文等）\n"
                "  * essay_primary: 小学作文（看图写话、小学记叙文、小学想象作文等）\n"
                "  * essay_middle: 初中作文（中考作文、半命题作文、话题作文等）\n"
                "  * novel: 小说\n"
                "  * xiaohongshu: 小红书文案\n"
                "- sub_type: 具体子类型（如：议论文、小学记叙文、初中半命题作文、种草文案）\n"
                "- word_count: 目标字数（整数）。如果用户未指定，按场景给默认值：\n"
                "  * essay: 800\n"
                "  * essay_primary: 300-400（小学低年级300，高年级400）\n"
                "  * essay_middle: 600\n"
                "  * novel: 2000\n"
                "  * xiaohongshu: 300-600\n"
                "- style: 风格描述\n"
                "- audience: 目标受众\n"
                "- constraints: 其他显式约束（数组）\n"
                "- complexity: simple / moderate / complex\n"
                "只输出 JSON，不要其他内容。"
            )},
            {"role": "user", "content": f"分析这个写作请求：{query}"}
        ]

        try:
            data, resp = llm_client.chat_json(messages, model=config.SKILL_MODEL)
            return SkillResult(
                skill_name=self.name, success=True,
                output=data, confidence=0.9,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(
                skill_name=self.name, success=False, error=str(e)
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 质量自检 Skill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 场景特定的评审维度
_REVIEW_DIMENSIONS = {
    "essay": {
        "dimensions": "扣题程度、论证力度、结构完整性、语言水平、思辨深度",
        "focus": "重点检查是否跑题、论据是否支撑论点、段落间是否有逻辑衔接",
    },
    "essay_primary": {
        "dimensions": "扣题程度、叙事完整性、详略得当、语句通顺、修辞运用",
        "focus": "重点检查是否把事情写清楚了、重点部分是否展开写、好词好句是否自然",
    },
    "essay_middle": {
        "dimensions": "扣题程度、立意深度、细节描写、结构完整性、语言表达",
        "focus": "重点检查是否有具体的细节描写而非空洞叙述、结尾升华是否自然、是否'大题小做'而非写空话",
    },
    "novel": {
        "dimensions": "代入感、节奏感、悬念设置、角色鲜活度、世界观一致性",
        "focus": "重点检查开篇是否有吸引力、角色是否立得住、是否有继续读的欲望",
    },
    "xiaohongshu": {
        "dimensions": "标题吸引力、痛点命中率、真实感、转化引导、平台调性",
        "focus": "重点检查是否像真人分享而非广告、是否有具体体验细节、CTA是否自然",
    },
}


@register_skill
class QualityReview(BaseSkill):

    @property
    def name(self): return "quality_review"

    @property
    def description(self):
        return (
            "对生成的写作成品进行质量审核，按场景特定维度打分（1-5），"
            "识别具体的薄弱环节，并给出是否通过的判定和修改建议。"
        )

    @property
    def applicable_scenarios(self): return ["essay", "novel", "xiaohongshu"]

    @property
    def input_fields(self): return "query, scenario, draft_text (待审核的成品文本)"

    @property
    def output_fields(self):
        return "passed, overall_score, dimension_scores, weaknesses, revision_suggestion"

    def execute(self, context: dict) -> SkillResult:
        scenario = context.get("scenario", "essay")
        query = context["query"]
        draft = context.get("draft_text", "")
        
        # 硬性字数检查（在 LLM 评审之前）
        need = context.get("skill_outputs", {}).get("need_analysis")
        target = need.output.get("word_count", 800) if need else 800
        actual = len(draft)
        
        if actual < target * 0.85:
            return SkillResult(
                skill_name=self.name, success=True,
                output={
                    "passed": False,
                    "overall_score": 0.5,
                    "weaknesses": [f"字数不足：要求{target}字，实际{actual}字"],
                    "revision_suggestion": f"正文只有{actual}字，需要扩写到{target}字以上。重点扩充论证段的素材和分析。",
                    "dimension_scores": {}
                },
                confidence=0.5,
            )
        
        review_cfg = _REVIEW_DIMENSIONS.get(scenario, _REVIEW_DIMENSIONS["essay"])

        messages = [
            {"role": "system", "content": (
                f"你是资深写作评审专家。请对以下作品进行质量审核。\n\n"
                f"评审维度：{review_cfg['dimensions']}\n"
                f"重点关注：{review_cfg['focus']}\n\n"
                f"输出 JSON，字段：\n"
                f"- overall_score: 0.0-1.0 的总分\n"
                f"- dimension_scores: {{维度名: 1-5分}}\n"
                f"- weaknesses: [具体薄弱点描述]（数组）\n"
                f"- revision_suggestion: 如果不通过，具体说明哪部分需要重写、怎么改\n"
                f"- passed: true/false（overall_score >= 0.7 为通过）\n"
                f"只输出 JSON。"
            )},
            {"role": "user", "content": (
                f"用户需求：{query}\n\n"
                f"待审核作品：\n{draft}"
            )}
        ]

        try:
            data, resp = llm_client.chat_json(
                messages, model=config.SKILL_MODEL,
                temperature=config.EVAL_TEMPERATURE
            )
            score = data.get("overall_score", 0.5)
            data["passed"] = score >= config.QUALITY_THRESHOLD
            return SkillResult(
                skill_name=self.name, success=True,
                output=data, confidence=score,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(
                skill_name=self.name, success=False, error=str(e)
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 格式优化 Skill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_FORMAT_INSTRUCTIONS = {
    "essay": "保持学术作文格式：分段清晰，每段有主题句，首尾呼应。不加 emoji 或网络用语。",
    "novel": "小说格式：对话用引号，场景描写与对话交替，段落不宜过长。章节标题简洁有力。",
    "xiaohongshu": "小红书格式：适当使用 emoji 分隔段落，关键词加【】突出，结尾加话题标签，整体轻松活泼。",
}


@register_skill
class FormatPolish(BaseSkill):

    @property
    def name(self): return "format_polish"

    @property
    def description(self):
        return "对写作成品进行最终的格式排版优化，适配目标平台的排版规范。"

    @property
    def applicable_scenarios(self): return ["essay", "novel", "xiaohongshu"]

    @property
    def input_fields(self): return "scenario, draft_text"

    @property
    def output_fields(self): return "polished_text"

    def execute(self, context: dict) -> SkillResult:
        scenario = context.get("scenario", "essay")
        draft = context.get("draft_text", "")
        fmt_instr = _FORMAT_INSTRUCTIONS.get(scenario, _FORMAT_INSTRUCTIONS["essay"])

        messages = [
            {"role": "system", "content": (
                f"你是排版编辑。对以下文本做格式优化，不改变内容含义。\n"
                f"格式要求：{fmt_instr}\n"
                f"直接输出优化后的文本，不要加任何解释。"
            )},
            {"role": "user", "content": draft}
        ]

        try:
            resp = llm_client.chat(
                messages, model=config.SKILL_MODEL,
                temperature=0.2, max_tokens=4096
            )
            return SkillResult(
                skill_name=self.name, success=True,
                output={"polished_text": resp.content},
                confidence=0.95,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
        except Exception as e:
            return SkillResult(
                skill_name=self.name, success=False, error=str(e)
            )
