#!/bin/bash
# 创建新的数据库迁移文件
# 使用方法: ./create_migration.sh "描述信息"
# 例如: ./create_migration.sh "add_user_avatar_column"

if [ -z "$1" ]; then
    echo "用法: $0 <迁移描述>"
    echo "例如: $0 add_user_avatar"
    exit 1
fi

# 进入 backend 目录
cd "$(dirname "$0")"

# 激活虚拟环境并创建迁移
source ../.venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null

# 使用 flask db revision 创建迁移（自动生成随机 ID）
flask db revision -m "$1"

echo ""
echo "✅ 迁移文件已创建！"
echo "📝 请编辑生成的文件，添加 upgrade() 和 downgrade() 逻辑"
echo ""
echo "⚠️  重要提示："
echo "   - 不要手动修改 revision ID"
echo "   - 合并分支后如有冲突，运行: flask db merge heads -m 'merge_branches'"
