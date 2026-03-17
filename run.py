#!/usr/bin/env python3
"""
Writing Agentic Demo — CLI 主入口

用法:
  # 单条 query 测试（快速验证链路是否跑通）
  python run.py --query "写一篇关于坚持的高考议论文，800字"

  # 加载 baseline CSV 批量对比
  python run.py --baseline data/baseline.csv

  # 只跑 agentic 链路（不做评估）
  python run.py --query "写一篇玄幻小说开篇" --no-eval

CSV 格式要求:
  列名: query, scenario, baseline_output
  scenario 可选值: essay / novel / xiaohongshu
"""
import argparse
import csv
import json
import sys
import os
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import WritingAgent, CLI
from evaluator import evaluate, print_eval_result, generate_report, EvalResult


def run_single(query: str, baseline_text: str = None,
               scenario: str = None, do_eval: bool = True) -> dict:
    """
    运行单条 query：agentic 链路 + (可选) GSB 评估
    """
    agent = WritingAgent()
    result = agent.run(query)

    agentic_text = result["final_text"]

    # 展示生成结果预览
    CLI.header("Agentic 输出预览")
    preview = agentic_text[:500] + "..." if len(agentic_text) > 500 else agentic_text
    print(f"\n{preview}\n")

    eval_result = None
    if do_eval and baseline_text:
        CLI.header("GSB 评估对比")
        sc = scenario or result.get("scenario", "essay")
        eval_result = evaluate(
            query=query,
            scenario=sc,
            baseline_text=baseline_text,
            agentic_text=agentic_text,
        )
        print_eval_result(eval_result)

    return {
        "query": query,
        "scenario": result.get("scenario", scenario or "essay"),
        "agentic_text": agentic_text,
        "agentic_stats": result.get("stats", {}),
        "eval_result": eval_result,
    }


def run_batch(csv_path: str, output_dir: str = "results") -> list[dict]:
    """
    批量运行：读取 baseline CSV，逐条跑 agentic + GSB 评估
    """
    os.makedirs(output_dir, exist_ok=True)

    # 读取 CSV
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("query") and row.get("baseline_output"):
                rows.append(row)

    if not rows:
        print(f"CSV 中没有有效数据（需要 query + baseline_output 列）")
        return []

    print(f"\n  加载 {len(rows)} 条 baseline 数据")
    print(f"  场景分布: {_count_scenarios(rows)}\n")

    all_results = []
    eval_results = []

    for i, row in enumerate(rows, 1):
        query = row["query"]
        baseline = row["baseline_output"]
        scenario = row.get("scenario", "essay")

        print(f"\n{'▓'*60}")
        print(f"  [{i}/{len(rows)}] {query[:50]}{'...' if len(query)>50 else ''}")
        print(f"{'▓'*60}")

        try:
            result = run_single(
                query=query,
                baseline_text=baseline,
                scenario=scenario,
                do_eval=True,
            )
            all_results.append(result)
            if result["eval_result"]:
                eval_results.append(result["eval_result"])
        except Exception as e:
            print(f"\n  ✗ 执行失败: {e}")
            all_results.append({"query": query, "error": str(e)})

    # 生成汇总报告
    if eval_results:
        report = generate_report(eval_results)
        print(report)

        # 保存报告
        report_path = os.path.join(output_dir, "gsb_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

    # 保存详细结果
    detail_path = os.path.join(output_dir, "detailed_results.jsonl")
    with open(detail_path, "w", encoding="utf-8") as f:
        for r in all_results:
            record = {
                "query": r.get("query", ""),
                "scenario": r.get("scenario", ""),
                "agentic_text": r.get("agentic_text", ""),
                "stats": r.get("agentic_stats", {}),
            }
            if r.get("eval_result"):
                er = r["eval_result"]
                record["eval"] = {
                    "verdict": er.verdict,
                    "agentic_score": er.agentic_score,
                    "baseline_score": er.baseline_score,
                    "dimensions": er.dimensions,
                    "reasoning": er.reasoning,
                }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  结果已保存:")
    print(f"    {report_path if eval_results else '(无评估报告)'}")
    print(f"    {detail_path}")

    return all_results


def _count_scenarios(rows):
    counts = {}
    for r in rows:
        s = r.get("scenario", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def main():
    parser = argparse.ArgumentParser(
        description="Writing Agentic Demo — 对比 Workflow vs Agentic+Skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python run.py --query '写一篇关于坚持的高考议论文，800字'\n"
            "  python run.py --baseline data/baseline.csv\n"
            "  python run.py --query '写个玄幻小说开篇' --no-eval\n"
        )
    )
    parser.add_argument("--query", type=str, help="单条 query 测试")
    parser.add_argument("--baseline", type=str, help="baseline CSV 文件路径（批量模式）")
    parser.add_argument("--baseline-text", type=str, help="单条 baseline 文本（与 --query 配合）")
    parser.add_argument("--scenario", type=str, choices=["essay", "novel", "xiaohongshu"],
                       help="强制指定场景（单条模式下可选）")
    parser.add_argument("--no-eval", action="store_true", help="只跑 agentic 链路，不做评估")
    parser.add_argument("--output", type=str, default="results", help="结果输出目录")

    args = parser.parse_args()

    # 检查 API Key
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("错误: 请设置 DASHSCOPE_API_KEY 环境变量")
        print("  export DASHSCOPE_API_KEY=sk-xxxxx")
        sys.exit(1)

    if args.baseline:
        # 批量模式
        run_batch(args.baseline, args.output)
    elif args.query:
        # 单条模式
        run_single(
            query=args.query,
            baseline_text=args.baseline_text,
            scenario=args.scenario,
            do_eval=not args.no_eval and args.baseline_text is not None,
        )
    else:
        parser.print_help()
        print("\n提示: 至少需要 --query 或 --baseline 参数")


if __name__ == "__main__":
    main()
