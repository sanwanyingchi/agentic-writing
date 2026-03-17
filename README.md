# Agentic Writing - 智能写作对比评测平台

基于 Agent + Skill 架构的智能写作系统，支持小学/初中/高中作文、网络小说、小红书文案等多场景，提供 AI 生成与用户内容对比评测功能。

## ✨ 特性

- 🤖 **多场景写作 Agent**: 支持小学/初中/高中作文、网络小说、小红书种草
- 🧠 **流式思考展示**: 实时显示 AI 规划、审题、写作全过程
- ⚖️ **GSB 对比评测**: Agent vs 用户内容的多维度对比
- 🌐 **一键部署**: GitHub + Render/Vercel 免费托管

## 🚀 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置环境变量
export DASHSCOPE_API_KEY=sk-xxxxx

# 3. 启动服务
python api_server.py

# 4. 打开 http://localhost:8000
```

### 部署到公网（GitHub + Render）

```bash
# 一键初始化 GitHub 仓库
./setup-github.sh
```

详细部署指南见 [README_DEPLOY.md](README_DEPLOY.md)

## 🏗️ 架构

```
用户输入 → Agent规划 → Skill执行 → 质量门控 → 输出结果
                ↓
        ├─ 小学/初中/高中作文
        ├─ 网络小说（世界观+写作）
        └─ 小红书文案
```

## 📁 项目结构

```
writing-agentic-demo/
├── api_server.py          # FastAPI 后端服务
├── agent.py               # Agent 核心逻辑
├── config.py              # 全局配置
├── llm_client.py          # LLM 调用封装
├── evaluator.py           # GSB 评测
├── skills/                # Skill 目录
│   ├── __init__.py
│   ├── shared.py          # 通用 Skill（需求分析、评测、排版）
│   ├── essay.py           # 高中作文
│   ├── essay_primary.py   # 小学作文
│   ├── essay_middle.py    # 初中作文
│   ├── novel.py           # 网络小说
│   └── xiaohongshu.py     # 小红书
├── web/                   # 前端页面
│   └── index.html
├── render.yaml            # Render 部署配置
├── Dockerfile             # Docker 镜像
└── README_DEPLOY.md       # 部署指南
```

## 📝 使用示例

### 命令行
```bash
# 生成小学作文
python run.py --query "写一篇小学作文：难忘的一件事，300字" --no-eval

# 生成网络小说
python run.py --query "写网络小说：重生在秦朝当皇帝，1500字" --no-eval

# 生成小红书文案
python run.py --query "写小红书：春天必入的5款平价防晒" --no-eval
```

### Web 界面

访问部署后的地址，输入写作需求，实时观察 AI 思考过程，上传自己的内容进行对比评测。

## 🛠️ 技术栈

- **后端**: Python + FastAPI + OpenAI SDK
- **前端**: HTML5 + TailwindCSS + 原生 JavaScript
- **模型**: 阿里云百炼 (qwen3.5-plus / qwen3-max / qwen-plus)
- **部署**: Docker / Render / GitHub Pages

## 📄 许可证

MIT License
