# 🚀 部署指南

## 方案一：GitHub + Render（推荐，免费）

### 步骤 1：推送代码到 GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/agentic-writing.git
git push -u origin main
```

### 步骤 2：部署后端到 Render

1. 访问 [render.com](https://render.com)，用 GitHub 账号登录
2. 点击 "New +" → "Web Service"
3. 选择您的 GitHub 仓库
4. 配置：
   - **Name**: `agentic-writing-api`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
5. 添加环境变量：
   - `DASHSCOPE_API_KEY`: 您的阿里云百炼 API Key
6. 点击 "Create Web Service"
7. 等待部署完成，记录分配的域名（如 `https://agentic-writing-api.onrender.com`）

### 步骤 3：部署前端到 GitHub Pages

1. 修改 `web/index.html` 中的 `API_BASE` 为您的 Render 地址
2. 提交并推送代码：
   ```bash
   git add .
   git commit -m "Update API URL"
   git push
   ```
3. 进入 GitHub 仓库 → Settings → Pages
4. Source 选择 "GitHub Actions"
5. 等待部署完成

### 访问地址

- **前端**: `https://YOUR_USERNAME.github.io/agentic-writing`
- **后端**: `https://agentic-writing-api.onrender.com`

---

## 方案二：Vercel + Railway（国内访问更快）

### 部署后端到 Railway

1. 访问 [railway.app](https://railway.app)，用 GitHub 登录
2. New Project → Deploy from GitHub repo
3. 选择仓库，添加环境变量 `DASHSCOPE_API_KEY`
4. 自动生成域名

### 部署前端到 Vercel

```bash
npm i -g vercel
cd web
vercel --prod
```

---

## 方案三：Docker 一键部署（自有服务器）

```bash
# 克隆代码
git clone https://github.com/YOUR_USERNAME/agentic-writing.git
cd agentic-writing

# 设置环境变量
export DASHSCOPE_API_KEY=sk-xxxxx

# 启动
docker-compose up -d

# 访问 http://服务器IP:8000
```

---

## 🔧 配置说明

### 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | ✅ |
| `PLANNER_MODEL` | 规划层模型，默认 qwen3.5-plus | ❌ |
| `SKILL_MODEL` | 写作层模型，默认 qwen3-max | ❌ |

### 免费额度

| 平台 | 限制 | 说明 |
|------|------|------|
| Render | 15分钟无访问休眠 | 首次访问需唤醒，约30秒 |
| GitHub Pages | 100GB/月流量 | 个人使用足够 |
| 阿里云百炼 | 100万 token | 新用户免费额度 |

---

## 🚀 快速部署脚本

```bash
# 一键部署到 Render（需要安装 render CLI）
render deploy

# 一键部署到 Vercel
vercel --prod
```
