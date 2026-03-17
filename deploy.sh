#!/bin/bash
# 一键部署脚本

echo "🚀 Agentic Writing 部署脚本"
echo "============================"

# 检查环境
if ! command -v docker &> /dev/null; then
    echo "正在安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

if ! command -v docker-compose &> /dev/null; then
    echo "正在安装 Docker Compose..."
    sudo pip3 install docker-compose
fi

# 检查 API Key
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "请输入 DASHSCOPE_API_KEY:"
    read -s API_KEY
    export DASHSCOPE_API_KEY=$API_KEY
fi

# 构建并启动
echo "正在构建 Docker 镜像..."
docker-compose build

echo "正在启动服务..."
docker-compose up -d

echo ""
echo "✅ 部署完成！"
echo ""
echo "访问地址:"
echo "  - 本地: http://localhost:8000"
echo "  - 公网: http://$(curl -s ip.sb):8000"
echo ""
echo "查看日志: docker-compose logs -f"
echo "停止服务: docker-compose down"
