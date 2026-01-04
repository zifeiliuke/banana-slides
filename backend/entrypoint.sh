#!/bin/bash
set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查数据库配置是否完整
check_db_config() {
    if [ -n "$DATABASE_URL" ]; then
        log_info "Using DATABASE_URL for database connection"
        return 0
    fi

    if [ -z "$MYSQL_HOST" ] || [ -z "$MYSQL_USER" ]; then
        log_error "Database configuration is incomplete!"
        log_error "Please set either DATABASE_URL or (MYSQL_HOST + MYSQL_USER + MYSQL_PASSWORD + MYSQL_DATABASE)"
        log_error ""
        log_error "Example .env configuration:"
        log_error "  MYSQL_HOST=localhost"
        log_error "  MYSQL_PORT=3306"
        log_error "  MYSQL_USER=myuser"
        log_error "  MYSQL_PASSWORD=mypassword"
        log_error "  MYSQL_DATABASE=banana_slides"
        exit 1
    fi

    log_info "Database config: ${MYSQL_USER}@${MYSQL_HOST}:${MYSQL_PORT:-3306}/${MYSQL_DATABASE:-banana_slides}"
    return 0
}

# 等待数据库可用
wait_for_db() {
    local host="${MYSQL_HOST:-localhost}"
    local port="${MYSQL_PORT:-3306}"
    local max_attempts=30
    local attempt=1

    log_info "Waiting for database at ${host}:${port}..."

    while [ $attempt -le $max_attempts ]; do
        if python3 -c "
import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    s.connect(('${host}', ${port}))
    s.close()
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
            log_info "Database is available!"
            return 0
        fi

        log_warn "Attempt ${attempt}/${max_attempts}: Database not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "Could not connect to database after ${max_attempts} attempts"
    exit 1
}

# 运行数据库迁移
run_migrations() {
    log_info "Running database migrations..."

    cd /app/backend

    # 运行 alembic 迁移
    if /app/.venv/bin/python -m alembic upgrade head; then
        log_info "Database migrations completed successfully"
    else
        log_error "Database migration failed!"
        exit 1
    fi
}

# 初始化默认管理员用户（如果不存在）
init_admin_user() {
    log_info "Checking for admin user..."

    cd /app/backend

    /app/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/app/backend')

from app import create_app
from models import db
from models.user import User
from datetime import datetime, timezone
import uuid

app = create_app()

with app.app_context():
    # 检查是否已存在管理员
    admin = User.query.filter_by(username='admin').first()
    if admin:
        print('Admin user already exists')
    else:
        # 创建默认管理员
        admin = User(
            id=str(uuid.uuid4()),
            username='admin',
            role='admin',
            tier='premium',
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        admin.set_password('admin123')
        admin.ensure_referral_code()
        db.session.add(admin)
        db.session.commit()
        print('Created default admin user (username: admin, password: admin123)')
        print('WARNING: Please change the admin password after first login!')
"
}

# 主流程
main() {
    log_info "Starting Banana Slides Backend..."

    # 1. 检查数据库配置
    check_db_config

    # 2. 等待数据库可用
    wait_for_db

    # 3. 运行数据库迁移
    run_migrations

    # 4. 初始化管理员用户
    init_admin_user

    # 5. 启动应用
    log_info "Starting Flask application..."
    cd /app/backend
    exec /app/.venv/bin/python app.py
}

main "$@"
