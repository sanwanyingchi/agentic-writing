"""
Writing Agent — 模型自主规划 + Skill 调度 + 质量门控
核心流程：
  1. 模型读取 Skill 目录，自主生成执行计划
  2. 逐步执行计划，每步调用对应 Skill
  3. 遇到质量门控节点，不达标则回退重写
  4. CLI 实时展示规划和执行过程
"""
import json
import time
from dataclasses import dataclass, field

import llm_client
import config
from skills import get_skill, get_skill_catalog, SkillResult


# ── CLI 输出样式 ──────────────────────────────────────────

class CLI:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"

    @staticmethod
    def header(text):
        print(f"\n{'━'*60}")
        print(f"{CLI.BOLD}{CLI.CYAN}{text}{CLI.RESET}")
        print(f"{'━'*60}")

    @staticmethod
    def step(idx, total, skill_name, description):
        print(f"\n  {CLI.BOLD}[{idx}/{total}]{CLI.RESET} {CLI.MAGENTA}{skill_name}{CLI.RESET}")
        print(f"       {CLI.DIM}{description}{CLI.RESET}")

    @staticmethod
    def result(success, detail, tokens=0, latency=0):
        icon = f"{CLI.GREEN}✓{CLI.RESET}" if success else f"{CLI.RED}✗{CLI.RESET}"
        stats = f"{CLI.DIM}({tokens} tokens, {latency}ms){CLI.RESET}" if tokens else ""
        print(f"       {icon} {detail} {stats}")

    @staticmethod
    def plan(steps):
        print(f"\n  {CLI.BOLD}执行计划：{CLI.RESET}")
        for i, s in enumerate(steps, 1):
            qg = f" {CLI.YELLOW}← 质量门控{CLI.RESET}" if s.get("quality_gate") else ""
            print(f"    {CLI.DIM}{i}.{CLI.RESET} {s['skill']} — {s.get('purpose', '')}{qg}")

    @staticmethod
    def quality_gate(passed, score, detail=""):
        if passed:
            print(f"       {CLI.GREEN}▶ 质量门控通过{CLI.RESET} (score={score:.2f})")
        else:
            print(f"       {CLI.YELLOW}▶ 质量门控未通过{CLI.RESET} (score={score:.2f}) → 触发回退")
            if detail:
                print(f"         {CLI.DIM}{detail}{CLI.RESET}")

    @staticmethod
    def retry(target_skill, attempt, max_retries):
        print(f"       {CLI.YELLOW}↻ 回退重写 {target_skill}{CLI.RESET} (第{attempt}/{max_retries}次)")


# ── 规划结果 ──────────────────────────────────────────────

@dataclass
class ExecutionPlan:
    """模型生成的执行计划"""
    scenario: str
    steps: list[dict] = field(default_factory=list)
    reasoning: str = ""
    plan_tokens: int = 0
    plan_latency_ms: int = 0


# ── Agent 核心 ────────────────────────────────────────────

class WritingAgent:
    """
    模型自主规划的写作 Agent。

    使用方式：
        agent = WritingAgent()
        result = agent.run("写一篇关于坚持的高考议论文")
    """

    def __init__(self):
        # 触发所有 Skill 注册（import 时 @register_skill 自动执行）
        import skills.shared
        import skills.essay
        import skills.essay_primary
        import skills.essay_middle
        import skills.novel
        import skills.xiaohongshu

    def run(self, query: str) -> dict:
        """
        完整执行流程：规划 → 逐步执行 → 质量门控 → 输出
        """
        CLI.header(f"Writing Agent 启动\n  Query: {query}")

        # ── Step 1: 模型自主规划 ──
        plan = self._plan(query)
        CLI.plan(plan.steps)

        # ── Step 2: 逐步执行 ──
        context = {
            "query": query,
            "scenario": plan.scenario,
            "skill_outputs": {},
        }
        total_steps = len(plan.steps)
        stats = {"total_tokens": plan.plan_tokens, "total_latency_ms": plan.plan_latency_ms}

        for i, step_def in enumerate(plan.steps, 1):
            skill_name = step_def["skill"]
            purpose = step_def.get("purpose", "")

            CLI.step(i, total_steps, skill_name, purpose)

            # 执行 Skill（含重试）
            result = self._execute_skill(skill_name, context, step_def)

            if result.success:
                context["skill_outputs"][skill_name] = result
                # 更新 draft_text（供质量审核和格式优化使用）
                self._update_draft(context, skill_name, result)
                CLI.result(True, self._summarize_output(skill_name, result),
                          result.input_tokens + result.output_tokens, result.latency_ms)
                stats["total_tokens"] += result.input_tokens + result.output_tokens
                stats["total_latency_ms"] += result.latency_ms
            else:
                CLI.result(False, f"执行失败: {result.error}")

            # ── 质量门控 ──
            if step_def.get("quality_gate") and result.success:
                review_result = self._quality_gate(context, step_def, stats)
                if review_result and not review_result.output.get("passed", True):
                    # 回退重写
                    retry_target = step_def["quality_gate"].get("retry_target", skill_name)
                    self._handle_retry(retry_target, context, step_def, stats)

        # ── Step 3: 提取最终文本 ──
        final_text = context.get("draft_text", "（未生成文本）")

        CLI.header("执行完成")
        print(f"  规划模型: {config.PLANNER_MODEL} (thinking={'on' if config.PLANNER_ENABLE_THINKING else 'off'})")
        print(f"  写作模型: {config.SKILL_MODEL}")
        print(f"  评估模型: {config.EVAL_MODEL}")
        print(f"  总 token: {stats['total_tokens']}")
        print(f"  总耗时:  {stats['total_latency_ms']}ms")
        print(f"  文本长度: {len(final_text)}字")

        return {
            "query": query,
            "scenario": plan.scenario,
            "plan": plan,
            "final_text": final_text,
            "skill_outputs": {k: v.output for k, v in context["skill_outputs"].items()
                             if isinstance(v, SkillResult)},
            "stats": stats,
        }

    # ── 规划层 ────────────────────────────────────────────

    def _plan(self, query: str) -> ExecutionPlan:
        """让模型自主决定执行哪些 Skill、按什么顺序"""
        catalog = get_skill_catalog()

        messages = [
            {"role": "system", "content": (
                "你是写作任务规划专家。根据用户的写作需求，从可用的 Skill 池中"
                "选择合适的 Skill 并规划执行顺序。\n\n"
                "## 可用 Skill 池\n"
                f"{catalog}\n\n"
                "## 规划规则\n"
                "1. 第一步必须是 need_analysis（需求分析）\n"
                "2. 根据场景选择合适的专属 Skill\n"
                "3. 写作 Skill 之后必须跟 quality_review（质量审核）\n"
                "4. 最后一步是 format_polish（格式优化）\n"
                "5. 质量审核节点需要设置 quality_gate，指定不通过时回退重写的目标 Skill\n\n"
                "## 输出格式（JSON）\n"
                "{\n"
                '  "scenario": "essay / novel / xiaohongshu",\n'
                '  "reasoning": "规划理由（简要说明为什么选这些 Skill、这个顺序）",\n'
                '  "steps": [\n'
                '    {\n'
                '      "skill": "skill_name",\n'
                '      "purpose": "这一步要做什么（一句话）",\n'
                '      "quality_gate": null 或 {"retry_target": "要回退重写的 skill_name"}\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "只输出 JSON。"
            )},
            {"role": "user", "content": f"请为以下写作需求制定执行计划：\n{query}"}
        ]

        data, resp = llm_client.chat_json(
            messages, model=config.PLANNER_MODEL,
            temperature=config.PLANNER_TEMPERATURE,
            enable_thinking=config.PLANNER_ENABLE_THINKING,
        )

        plan = ExecutionPlan(
            scenario=data.get("scenario", "essay"),
            steps=data.get("steps", []),
            reasoning=data.get("reasoning", ""),
            plan_tokens=resp.input_tokens + resp.output_tokens,
            plan_latency_ms=resp.latency_ms,
        )

        # 展示 qwen3.5-plus 的 thinking 推理过程
        if resp.reasoning:
            print(f"\n  {CLI.CYAN}💭 模型思考过程:{CLI.RESET}")
            # 截取前 300 字展示，避免刷屏
            thinking_preview = resp.reasoning[:300]
            if len(resp.reasoning) > 300:
                thinking_preview += "..."
            for line in thinking_preview.split("\n"):
                print(f"  {CLI.DIM}  {line}{CLI.RESET}")
            print(f"  {CLI.DIM}  (思考 {len(resp.reasoning)} 字){CLI.RESET}")

        print(f"\n  {CLI.DIM}规划理由: {plan.reasoning}{CLI.RESET}")
        print(f"  {CLI.DIM}识别场景: {plan.scenario} | "
              f"步骤数: {len(plan.steps)} | "
              f"规划模型: {resp.model} | "
              f"规划耗时: {plan.plan_latency_ms}ms{CLI.RESET}")

        return plan

    # ── Skill 执行 ────────────────────────────────────────

    def _execute_skill(self, skill_name: str, context: dict,
                       step_def: dict) -> SkillResult:
        """执行单个 Skill，含异常处理"""
        try:
            skill = get_skill(skill_name)
            return skill.execute(context)
        except KeyError as e:
            return SkillResult(skill_name=skill_name, success=False,
                             error=f"Skill 未找到: {e}")
        except Exception as e:
            return SkillResult(skill_name=skill_name, success=False,
                             error=str(e))

    # ── 质量门控 ──────────────────────────────────────────

    def _quality_gate(self, context: dict, step_def: dict,
                      stats: dict) -> SkillResult:
        """调用 quality_review Skill 进行质量审核"""
        review_skill = get_skill("quality_review")
        review_result = review_skill.execute(context)

        stats["total_tokens"] += review_result.input_tokens + review_result.output_tokens
        stats["total_latency_ms"] += review_result.latency_ms

        passed = review_result.output.get("passed", True)
        score = review_result.output.get("overall_score", 0)
        weakness = "; ".join(review_result.output.get("weaknesses", [])[:2])

        CLI.quality_gate(passed, score, weakness)
        context["skill_outputs"]["quality_review"] = review_result
        return review_result

    def _handle_retry(self, target_skill: str, context: dict,
                      step_def: dict, stats: dict):
        """质量不达标时回退重写指定 Skill"""
        for attempt in range(1, config.MAX_SKILL_RETRIES + 1):
            CLI.retry(target_skill, attempt, config.MAX_SKILL_RETRIES)

            # 将审核反馈注入 context，让重写 Skill 能看到
            review_out = context["skill_outputs"].get("quality_review")
            if isinstance(review_out, SkillResult):
                context["revision_feedback"] = review_out.output.get(
                    "revision_suggestion", ""
                )

            result = self._execute_skill(target_skill, context, step_def)
            if result.success:
                context["skill_outputs"][target_skill] = result
                self._update_draft(context, target_skill, result)
                stats["total_tokens"] += result.input_tokens + result.output_tokens
                stats["total_latency_ms"] += result.latency_ms
                CLI.result(True, f"重写完成", result.input_tokens + result.output_tokens,
                          result.latency_ms)

                # 再次审核
                re_review = get_skill("quality_review").execute(context)
                stats["total_tokens"] += re_review.input_tokens + re_review.output_tokens
                stats["total_latency_ms"] += re_review.latency_ms
                score = re_review.output.get("overall_score", 0)

                if re_review.output.get("passed", False):
                    CLI.quality_gate(True, score)
                    return
                else:
                    CLI.quality_gate(False, score)

        CLI.result(False, f"重试 {config.MAX_SKILL_RETRIES} 次后仍未通过，继续执行")

    # ── 上下文管理 ────────────────────────────────────────

    def _update_draft(self, context: dict, skill_name: str, result: SkillResult):
        """从 Skill 输出中提取文本，更新 context 中的 draft_text"""
        output = result.output
        if not isinstance(output, dict):
            return

        # 按优先级尝试提取文本
        for key in ["full_text", "polished_text"]:
            if key in output and output[key]:
                context["draft_text"] = output[key]
                return

    def _summarize_output(self, skill_name: str, result: SkillResult) -> str:
        """生成 Skill 输出的一行摘要，用于 CLI 展示"""
        out = result.output
        if not isinstance(out, dict):
            return "完成"

        if skill_name == "need_analysis":
            return f"场景={out.get('scenario','?')} 类型={out.get('sub_type','?')} 字数={out.get('word_count','?')}"
        elif skill_name == "essay_topic_analysis":
            dims = out.get("dimensions", [])
            angles = [d.get("angle", "") for d in dims[:3]]
            return f"核心词={out.get('topic_keyword','?')} 维度=[{', '.join(angles)}]"
        elif skill_name == "essay_thesis":
            cands = out.get("candidates", [])
            sel = out.get("selected_index", 0)
            thesis = cands[sel].get("thesis", "?") if sel < len(cands) else "?"
            return f"生成{len(cands)}个立意 → 选定: {thesis[:40]}..."
        elif skill_name in ("essay_writing", "novel_writing"):
            text = out.get("full_text", "")
            return f"生成 {len(text)} 字"
        elif skill_name == "novel_worldbuilding":
            protag = out.get("protagonist", {})
            return f"主角={protag.get('name','?')} 冲突={out.get('initial_conflict','?')[:30]}..."
        elif skill_name == "xhs_viral_copy":
            title = out.get("selected_title", "?")
            text = out.get("full_text", "")
            return f"标题=《{title[:25]}》 {len(text)}字"
        elif skill_name == "quality_review":
            return f"score={out.get('overall_score',0):.2f} passed={out.get('passed',False)}"
        elif skill_name == "format_polish":
            text = out.get("polished_text", "")
            return f"排版优化完成 ({len(text)}字)"
        else:
            return "完成"
