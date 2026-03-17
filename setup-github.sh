#!/bin/bash
# GitHub 部署初始化脚本

set -e

echo "🚀 Agentic Writing - GitHub 部署助手"
echo "======================================"
echo ""

# 检查 git
if ! command -v git &> /dev/null; then
    echo "❌ 请先安装 Git: https://git-scm.com/downloads"
    exit 1
fi

# 获取 GitHub 用户名
echo "请输入您的 GitHub 用户名:"
read USERNAME

# 获取仓库名
echo "请输入仓库名（默认: agentic-writing）:"
read REPO_NAME
REPO_NAME=${REPO_NAME:-agentic-writing}

# 创建仓库
echo ""
echo "📦 步骤 1/4: 初始化 Git 仓库..."
git init
git add .
git commit -m "Initial commit: Agentic Writing Platform"
git branch -M main

# 添加远程仓库
echo ""
echo "📦 步骤 2/4: 关联 GitHub 仓库..."
git remote add origin "https://github.com/$USERNAME/$REPO_NAME.git" 2>/dev/null || true

# 更新前端 API 地址占位符
echo ""
echo "📝 步骤 3/4: 配置 API 地址..."
sed -i '' "s|https://agentic-writing-api.onrender.com|https://$REPO_NAME-api.onrender.com|g" web/index.html 2>/dev/null || \
sed -i "s|https://agentic-writing-api.onrender.com|https://$REPO_NAME-api.onrender.com|g" web/index.html

echo "✅ 配置完成！"
echo ""

# 推送代码
echo "📦 步骤 4/4: 推送代码到 GitHub..."
echo "   请确保您已在 GitHub 创建仓库: https://github.com/new"
echo "   仓库名: $REPO_NAME"
echo ""
read -p "确认已创建仓库？按 Enter 继续..."

git push -u origin main || {
    echo ""
    echo "⚠️  推送失败，请手动执行:"
    echo "   git push -u origin main"
    echo ""
}

echo ""
echo "🎉 代码已推送到 GitHub！"
echo ""
echo "下一步操作:"
echo "=============="
echo ""
echo "1. 部署后端到 Render:"
echo "   - 访问 https://dashboard.render.com"
echo "   - New + → Web Service → 选择 $REPO_NAME"
echo "   - 环境变量添加: DASHSCOPE_API_KEY=sk-xxxxx"
echo ""
echo "2. 开启 GitHub Pages:"
echo "   - 访问 https://github.com/$USERNAME/$REPO_NAME/settings/pages"
echo "   - Source: GitHub Actions"
echo ""
echo "3. 等待 2-3 分钟后访问:"
echo "   https://$USERNAME.github.io/$REPO_NAME"
echo ""
echo "详细说明见 README_DEPLOY.md"
