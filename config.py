"""
全局配置
使用前请设置环境变量 DASHSCOPE_API_KEY
"""
import os

# ── 模型配置 ──────────────────────────────────────────────
# 规划层：qwen3.5-plus 默认开启 thinking 模式，推理规划能力最强
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "qwen3.5-plus")
# Skill 执行层：qwen3-max 旗舰写作质量
SKILL_MODEL = os.getenv("SKILL_MODEL", "qwen3-max")
# GSB 评估层：qwen-plus 性价比高，评分任务够用
EVAL_MODEL = os.getenv("EVAL_MODEL", "qwen-plus")

# ── Thinking 模式配置 ────────────────────────────────────
# qwen3.5-plus 默认开启 thinking，需要通过 extra_body 传参
# 规划层开启 thinking 以获得更深度的推理
PLANNER_ENABLE_THINKING = True
PLANNER_THINKING_BUDGET = 4096   # 规划层思考 token 预算

# ── API 配置 ──────────────────────────────────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ── Agent 配置 ─────────────────────────────────────────────
MAX_SKILL_RETRIES = 2           # 单个 Skill 最大重试次数
QUALITY_THRESHOLD = 0.7         # 质量门控阈值 (0-1)
PLANNER_TEMPERATURE = 0.3       # 规划层低温度，保证确定性
SKILL_TEMPERATURE = 0.7         # 写作 Skill 稍高，保持创意
EVAL_TEMPERATURE = 0.1          # 评估层极低温度，保证一致性

# ── 场景列表 ──────────────────────────────────────────────
SCENARIOS = ["essay", "essay_primary", "essay_middle", "novel", "xiaohongshu"]
