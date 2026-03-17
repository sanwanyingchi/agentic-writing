"""
GSB 评估模块
输入: 同一 query 的两份作品 (baseline vs agentic)
输出: Good / Same / Bad + 各维度打分 + 评语
"""
import json
import llm_client
import config
from dataclasses import dataclass


@dataclass
class EvalResult:
    query: str
    scenario: str
    verdict: str            # G / S / B
    agentic_score: float    # 0-10
    baseline_score: float   # 0-10
    dimensions: dict        # {维度: {agentic: x, baseline: y}}
    reasoning: str          # 评语
    input_tokens: int = 0
    output_tokens: int = 0


_SCENARIO_CRITERIA = {
    "essay": (
        "作文评分维度：\n"
        "1. 扣题程度 (1-10): 是否紧扣题意，立意是否清晰\n"
        "2. 论证质量 (1-10): 论据是否充分、论证是否严密\n"
        "3. 结构布局 (1-10): 文章结构是否完整、段落衔接是否流畅\n"
        "4. 语言表达 (1-10): 用词是否准确、句式是否丰富\n"
        "5. 思辨深度 (1-10): 是否有辩证思考、立意是否有深度"
    ),
    "novel": (
        "小说评分维度：\n"
        "1. 代入感 (1-10): 开篇是否吸引人、能否让读者产生沉浸感\n"
        "2. 角色塑造 (1-10): 主角是否立体、行为是否合理\n"
        "3. 情节节奏 (1-10): 叙事节奏是否得当、是否拖沓\n"
        "4. 世界观 (1-10): 设定是否自洽、有无逻辑漏洞\n"
        "5. 悬念设置 (1-10): 结尾是否有悬念、是否让人想继续读"
    ),
    "xiaohongshu": (
        "小红书文案评分维度：\n"
        "1. 标题吸引力 (1-10): 标题是否让人想点进来\n"
        "2. 真实感 (1-10): 是否像真人分享而非广告\n"
        "3. 痛点命中 (1-10): 是否抓住了目标用户的核心需求\n"
        "4. 转化力 (1-10): 是否能让读者产生行动意愿\n"
        "5. 平台适配 (1-10): 格式和调性是否符合小红书风格"
    ),
}


def evaluate(
    query: str,
    scenario: str,
    baseline_text: str,
    agentic_text: str,
) -> EvalResult:
    """
    GSB 评估：用 LLM 作为裁判对比两份作品。
    为避免位置偏差，随机分配 A/B 标签。
    """
    import random
    # 随机分配 A/B 避免位置偏差
    if random.random() > 0.5:
        text_a, text_b = baseline_text, agentic_text
        label_a, label_b = "baseline", "agentic"
    else:
        text_a, text_b = agentic_text, baseline_text
        label_a, label_b = "agentic", "baseline"

    criteria = _SCENARIO_CRITERIA.get(scenario, _SCENARIO_CRITERIA["essay"])

    messages = [
        {"role": "system", "content": (
            "你是严格的写作评审专家。你将看到同一题目下的两篇作品（作品A 和 作品B），"
            "请从多个维度进行对比评分。\n\n"
            f"{criteria}\n\n"
            "## 输出格式（JSON）\n"
            "{\n"
            '  "dimensions": {\n'
            '    "维度名": {"a_score": x, "b_score": y}\n'
            "  },\n"
            '  "a_total": 加权总分(0-10),\n'
            '  "b_total": 加权总分(0-10),\n'
            '  "verdict": "A" 或 "B" 或 "TIE" (谁更好),\n'
            '  "reasoning": "评审理由（200字以内，指出关键差异）"\n'
            "}\n"
            "评分要基于实际内容质量，不要因为篇幅长就给高分。\n"
            "只输出 JSON。"
        )},
        {"role": "user", "content": (
            f"题目：{query}\n\n"
            f"═══ 作品A ═══\n{text_a}\n\n"
            f"═══ 作品B ═══\n{text_b}"
        )}
    ]

    data, resp = llm_client.chat_json(
        messages, model=config.EVAL_MODEL,
        temperature=config.EVAL_TEMPERATURE, max_tokens=2000
    )

    # 还原 A/B 标签到 baseline/agentic
    a_total = data.get("a_total", 5)
    b_total = data.get("b_total", 5)
    verdict_raw = data.get("verdict", "TIE")

    if label_a == "agentic":
        agentic_score, baseline_score = a_total, b_total
        verdict_map = {"A": "G", "B": "B", "TIE": "S"}
    else:
        agentic_score, baseline_score = b_total, a_total
        verdict_map = {"A": "B", "B": "G", "TIE": "S"}

    verdict = verdict_map.get(verdict_raw, "S")

    # 还原维度分数
    dimensions = {}
    for dim_name, scores in data.get("dimensions", {}).items():
        a_s = scores.get("a_score", 5)
        b_s = scores.get("b_score", 5)
        if label_a == "agentic":
            dimensions[dim_name] = {"agentic": a_s, "baseline": b_s}
        else:
            dimensions[dim_name] = {"agentic": b_s, "baseline": a_s}

    return EvalResult(
        query=query,
        scenario=scenario,
        verdict=verdict,
        agentic_score=agentic_score,
        baseline_score=baseline_score,
        dimensions=dimensions,
        reasoning=data.get("reasoning", ""),
        input_tokens=resp.input_tokens + resp.output_tokens,
    )


def print_eval_result(result: EvalResult):
    """CLI 友好的评估结果展示"""
    G = "\033[32m"
    R = "\033[31m"
    Y = "\033[33m"
    B = "\033[1m"
    D = "\033[2m"
    RESET = "\033[0m"

    verdict_display = {
        "G": f"{G}✓ Agentic 胜出{RESET}",
        "S": f"{Y}= 持平{RESET}",
        "B": f"{R}✗ Baseline 胜出{RESET}",
    }

    print(f"\n{'─'*55}")
    print(f"  {B}GSB 评估结果{RESET}")
    print(f"  Query: {D}{result.query[:50]}...{RESET}" if len(result.query) > 50
          else f"  Query: {D}{result.query}{RESET}")
    print(f"  判定:  {verdict_display.get(result.verdict, result.verdict)}")
    print(f"  总分:  Agentic {B}{result.agentic_score:.1f}{RESET}"
          f"  vs  Baseline {B}{result.baseline_score:.1f}{RESET}")
    print()

    # 维度对比
    for dim, scores in result.dimensions.items():
        a = scores["agentic"]
        b = scores["baseline"]
        diff = a - b
        bar = ""
        if diff > 0:
            bar = f"{G}+{diff:.0f}{RESET}"
        elif diff < 0:
            bar = f"{R}{diff:.0f}{RESET}"
        else:
            bar = f"{D}={RESET}"
        print(f"    {dim:<12} A={a:<4.0f} B={b:<4.0f} {bar}")

    print(f"\n  {D}评语: {result.reasoning[:200]}{RESET}")
    print(f"{'─'*55}")


def generate_report(results: list[EvalResult]) -> str:
    """生成汇总报告"""
    lines = ["\n" + "═" * 60, "  GSB 评估汇总报告", "═" * 60, ""]

    # 按场景分组
    by_scenario = {}
    for r in results:
        by_scenario.setdefault(r.scenario, []).append(r)

    total_g, total_s, total_b = 0, 0, 0

    for scenario, group in by_scenario.items():
        g = sum(1 for r in group if r.verdict == "G")
        s = sum(1 for r in group if r.verdict == "S")
        b = sum(1 for r in group if r.verdict == "B")
        total_g += g
        total_s += s
        total_b += b

        avg_a = sum(r.agentic_score for r in group) / len(group)
        avg_b = sum(r.baseline_score for r in group) / len(group)
        delta = avg_a - avg_b

        lines.append(f"  [{scenario}] {len(group)} queries")
        lines.append(f"    GSB 分布: G={g}  S={s}  B={b}  "
                     f"(Agentic 胜率 {g/len(group)*100:.0f}%)")
        lines.append(f"    平均分:   Agentic {avg_a:.1f}  vs  Baseline {avg_b:.1f}  "
                     f"(Δ={delta:+.1f})")
        lines.append("")

    lines.append(f"  [总计] {len(results)} queries")
    lines.append(f"    G={total_g}  S={total_s}  B={total_b}  "
                 f"(Agentic 胜率 {total_g/len(results)*100:.0f}%)")
    lines.append("═" * 60)
    return "\n".join(lines)
