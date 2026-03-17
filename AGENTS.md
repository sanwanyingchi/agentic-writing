# Writing Agentic Demo

## 项目目标
对比 Workflow 链路 vs Agentic+Skill 链路在作文、小说、小红书三类场景
下的写作质量差异，产出可量化的 GSB 评测数据。

## 技术栈
- Python 3.10+
- LLM: Qwen 系列（通过 DashScope OpenAI 兼容接口调用，非 Kimi/Moonshot）
- 依赖: openai
- API Key 环境变量: DASHSCOPE_API_KEY

## 模型配置（三层分离，都是 DashScope/Qwen）
- 规划层: qwen3.5-plus（开启 thinking 模式，推理过程通过 reasoning_content 返回）
- 写作层: qwen3-max（旗舰写作质量）
- 评估层: qwen-plus（性价比，评分任务够用）
- llm_client.py 已适配 thinking 模式：自动检测模型名 → 注入 extra_body → 提取 reasoning_content
- JSON 提取有三层容错：直接解析 → 去 markdown 包裹 → 正则提取

## 项目结构
- config.py: 全局配置（模型名、thinking 参数、质量阈值）
- llm_client.py: Qwen 模型调用封装（适配 qwen3.5-plus thinking 模式）
- agent.py: 核心 Agent（模型自主规划 + Skill 调度 + 质量门控 + CLI 展示）
- skills/__init__.py: Skill 基类 + @register_skill 装饰器 + 全局注册表
- skills/shared.py: 共享 Skill × 3（需求分析、质量自检、格式优化）
- skills/essay.py: 作文 Skill × 3（审题、立意、分段写作）
- skills/novel.py: 小说 Skill × 2（世界观设定、场景写作）
- skills/xiaohongshu.py: 小红书 Skill × 1（爆款文案）
- evaluator.py: GSB 评估模块
- run.py: CLI 入口

## 运行方式
- 单条测试: python run.py --query "写一篇关于坚持的高考议论文" --no-eval
- 带 baseline 对比: python run.py --query "..." --baseline-text "..."
- 批量对比: python run.py --baseline data/baseline.csv

## 编码规范
- Skill 的 prompt 模板写在各 Skill 类的 execute() 方法中
- 所有 LLM 调用通过 llm_client.py 统一封装，不要直接实例化 OpenAI client
- 新增 Skill 必须继承 BaseSkill 并用 @register_skill 注册
- 中文注释，英文变量名
- 修改 thinking 相关逻辑时注意：只有规划层用 thinking，Skill 层和评估层不用

## 当前状态
框架代码已完成，需要：
1. 验证单条 query 端到端跑通
2. 调优各 Skill 的 prompt 质量
3. 准备 baseline CSV 数据
4. 批量跑 GSB 对比
