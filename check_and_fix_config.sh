#!/bin/bash

echo "=========================================="
echo "OpenRouter 配置检查和修复脚本"
echo "=========================================="
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 文件"
    echo "请先创建 .env 文件（可以复制 .env.example）"
    exit 1
fi

echo "📄 检查 .env 文件配置..."
echo ""

# 检查关键配置
AI_PROVIDER_FORMAT=$(grep "^AI_PROVIDER_FORMAT=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
OPENAI_API_BASE=$(grep "^OPENAI_API_BASE=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
IMAGE_MODEL=$(grep "^IMAGE_MODEL=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")

echo "当前配置："
echo "  AI_PROVIDER_FORMAT: ${AI_PROVIDER_FORMAT:-未设置}"
echo "  OPENAI_API_BASE: ${OPENAI_API_BASE:-未设置}"
echo "  OPENAI_API_KEY: ${OPENAI_API_KEY:+已设置（隐藏）}"
echo "  IMAGE_MODEL: ${IMAGE_MODEL:-未设置}"
echo ""

# 检查配置是否正确
ISSUES=0

if [ "$AI_PROVIDER_FORMAT" != "openai" ]; then
    echo "⚠️  问题 1: AI_PROVIDER_FORMAT 应该是 'openai'，当前是 '${AI_PROVIDER_FORMAT:-未设置}'"
    ISSUES=$((ISSUES + 1))
fi

if [ -z "$OPENAI_API_BASE" ] || [ "$OPENAI_API_BASE" != "https://openrouter.ai/api/v1" ]; then
    echo "⚠️  问题 2: OPENAI_API_BASE 应该是 'https://openrouter.ai/api/v1'，当前是 '${OPENAI_API_BASE:-未设置}'"
    ISSUES=$((ISSUES + 1))
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  问题 3: OPENAI_API_KEY 未设置"
    ISSUES=$((ISSUES + 1))
fi

if [ -z "$IMAGE_MODEL" ] || [[ ! "$IMAGE_MODEL" =~ ^google/ ]]; then
    echo "⚠️  问题 4: IMAGE_MODEL 应该使用 OpenRouter 格式（如 'google/gemini-3-pro-image-preview'），当前是 '${IMAGE_MODEL:-未设置}'"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✅ 配置看起来正确！"
    echo ""
    echo "下一步："
    echo "1. 清除数据库设置（如果存在）："
    echo "   curl -X POST http://localhost:5000/api/settings/reset"
    echo ""
    echo "2. 重启服务："
    echo "   docker compose restart backend"
    echo ""
    echo "3. 查看日志验证："
    echo "   docker compose logs -f backend | grep -i 'provider\|image\|error'"
else
    echo ""
    echo "发现 $ISSUES 个配置问题。"
    echo ""
    echo "修复建议："
    echo ""
    echo "请在 .env 文件中设置以下配置："
    echo ""
    echo "AI_PROVIDER_FORMAT=openai"
    echo "OPENAI_API_BASE=https://openrouter.ai/api/v1"
    echo "OPENAI_API_KEY=your-openrouter-api-key-here"
    echo "IMAGE_MODEL=google/gemini-3-pro-image-preview"
    echo "TEXT_MODEL=google/gemini-2.0-flash-exp"
    echo ""
    echo "注意：模型名称需要使用 OpenRouter 格式（provider/model-name）"
fi

echo ""
echo "=========================================="

