#!/bin/bash

# Banana Slides 数据库重置脚本

echo "╔══════════════════════════════════════╗"
echo "║   🗑️  数据库重置脚本  🗑️          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 检查是否在项目根目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 询问用户确认
echo "⚠️  警告: 此操作将删除所有数据库数据！"
echo ""
read -p "确定要继续吗？(yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "🛑 正在停止 Docker 容器..."
docker compose down

echo ""
echo "🗑️  正在删除数据库文件..."

# 删除数据库文件
if [ -d "backend/instance" ]; then
    rm -f backend/instance/database.db
    rm -f backend/instance/database.db-shm
    rm -f backend/instance/database.db-wal
    echo "✅ 数据库文件已删除"
else
    echo "⚠️  backend/instance 目录不存在，跳过"
fi

# 询问是否删除上传的文件
echo ""
read -p "是否同时删除上传的文件？(yes/no，默认: no): " delete_uploads

if [ "$delete_uploads" = "yes" ]; then
    if [ -d "uploads" ]; then
        rm -rf uploads/*
        echo "✅ 上传文件已删除"
    else
        echo "⚠️  uploads 目录不存在，跳过"
    fi
fi

echo ""
echo "🚀 正在启动 Docker 容器..."
docker compose up -d

echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
if docker compose ps | grep -q "Up"; then
    echo ""
    echo "✅ 数据库重置完成！"
    echo ""
    echo "📝 提示:"
    echo "   - 数据库已重新初始化"
    echo "   - 所有表已自动创建"
    echo "   - 可以通过 http://localhost:5000/health 检查服务状态"
    echo ""
else
    echo ""
    echo "⚠️  服务可能未正常启动，请检查日志:"
    echo "   docker compose logs backend"
fi

