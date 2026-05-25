#!/bin/bash

# 纳瓦尔商业诊断系统启动脚本

set -e

echo "🚀 启动纳瓦尔商业诊断系统..."

# 检查.env文件
if [ ! -f .env ]; then
    echo "📝 创建.env配置文件..."
    cp .env.example .env
    echo "⚠️ 请编辑 .env 文件填入API密钥"
fi

# 启动服务
echo "📦 启动Docker服务..."
docker-compose up -d

# 等待数据库就绪
echo "⏳ 等待数据库就绪..."
sleep 5

# 初始化数据库（如果需要）
echo "🗄️ 检查数据库初始化..."
docker-compose exec -T db psql -U postgres -d naval_diagnosis -c "SELECT 1" > /dev/null 2>&1 && echo "✅ 数据库已就绪" || echo "⚠️ 数据库初始化中..."

echo ""
echo "✨ 启动完成！"
echo ""
echo "📍 访问地址："
echo "   前端: http://localhost:5173"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "📝 常用命令："
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose down"
echo "   重启服务: docker-compose restart"
