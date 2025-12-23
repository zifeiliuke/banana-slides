"""
多用户体系数据库迁移脚本

使用方法:
    cd backend
    python -m migrations.migrate_to_multi_user

功能:
    1. 创建新的用户相关表
    2. 迁移现有 projects 和 user_templates 数据
    3. 创建默认管理员账户
"""
import uuid
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

# 数据库路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DATABASE_PATH = os.path.join(BACKEND_DIR, 'instance', 'database.db')

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'  # 首次登录后应立即修改


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate():
    print(f"Database path: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print(f"Database file not found: {DATABASE_PATH}")
        print("Please start the application first to create the database.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # ========== Step 1: 创建 users 表 ==========
        print("[1/8] Creating users table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                tier VARCHAR(20) NOT NULL DEFAULT 'free',
                premium_expires_at DATETIME,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                last_login_at DATETIME
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_tier ON users(tier)')

        # ========== Step 2: 创建默认管理员 ==========
        print("[2/8] Creating default admin user...")
        admin_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        cursor.execute('''
            INSERT OR IGNORE INTO users (id, username, password_hash, role, tier, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 'admin', 'premium', 1, ?, ?)
        ''', (admin_id, DEFAULT_ADMIN_USERNAME, generate_password_hash(DEFAULT_ADMIN_PASSWORD), now, now))

        # 获取管理员 ID（可能已存在）
        cursor.execute('SELECT id FROM users WHERE username = ?', (DEFAULT_ADMIN_USERNAME,))
        admin_row = cursor.fetchone()
        admin_id = admin_row['id'] if admin_row else admin_id

        # ========== Step 3: 创建 user_settings 表 ==========
        print("[3/8] Creating user_settings table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) UNIQUE NOT NULL,
                ai_provider_format VARCHAR(20) DEFAULT 'gemini',
                api_base_url VARCHAR(500),
                api_key VARCHAR(500),
                text_model VARCHAR(100),
                image_model VARCHAR(100),
                image_caption_model VARCHAR(100),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        # ========== Step 4: 创建 recharge_codes 表 ==========
        print("[4/8] Creating recharge_codes table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recharge_codes (
                id VARCHAR(36) PRIMARY KEY,
                code VARCHAR(32) UNIQUE NOT NULL,
                duration_days INTEGER NOT NULL,
                is_used BOOLEAN NOT NULL DEFAULT 0,
                used_by_user_id VARCHAR(36),
                used_at DATETIME,
                created_by_admin_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                expires_at DATETIME,
                FOREIGN KEY (used_by_user_id) REFERENCES users(id),
                FOREIGN KEY (created_by_admin_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_recharge_codes_code ON recharge_codes(code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_recharge_codes_is_used ON recharge_codes(is_used)')

        # ========== Step 5: 创建 premium_history 表 ==========
        print("[5/8] Creating premium_history table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_history (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                action VARCHAR(20) NOT NULL,
                duration_days INTEGER,
                recharge_code_id VARCHAR(36),
                admin_id VARCHAR(36),
                note VARCHAR(500),
                created_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (recharge_code_id) REFERENCES recharge_codes(id),
                FOREIGN KEY (admin_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium_history_user_id ON premium_history(user_id)')

        # ========== Step 6: 迁移 projects 表 ==========
        print("[6/8] Migrating projects table...")

        # 检查 projects 表是否已有 user_id 列
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col['name'] for col in cursor.fetchall()]

        if 'user_id' not in columns:
            # 创建新表
            cursor.execute('''
                CREATE TABLE projects_new (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    idea_prompt TEXT,
                    outline_text TEXT,
                    description_text TEXT,
                    extra_requirements TEXT,
                    creation_type VARCHAR(20) NOT NULL DEFAULT 'idea',
                    template_image_path VARCHAR(500),
                    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # 复制数据，所有旧数据归属给 admin
            cursor.execute('''
                INSERT INTO projects_new (id, user_id, idea_prompt, outline_text, description_text,
                    extra_requirements, creation_type, template_image_path, status, created_at, updated_at)
                SELECT id, ?, idea_prompt, outline_text, description_text,
                    extra_requirements, creation_type, template_image_path, status, created_at, updated_at
                FROM projects
            ''', (admin_id,))

            # 获取迁移的数量
            cursor.execute('SELECT COUNT(*) FROM projects')
            project_count = cursor.fetchone()[0]

            # 删除旧表，重命名新表
            cursor.execute('DROP TABLE projects')
            cursor.execute('ALTER TABLE projects_new RENAME TO projects')
            cursor.execute('CREATE INDEX idx_projects_user_id ON projects(user_id)')
            print(f"    -> Migrated {project_count} projects to admin user ({admin_id})")
        else:
            print("    -> projects table already has user_id column, skipping...")

        # ========== Step 7: 迁移 user_templates 表 ==========
        print("[7/8] Migrating user_templates table...")

        cursor.execute("PRAGMA table_info(user_templates)")
        columns = [col['name'] for col in cursor.fetchall()]

        if 'user_id' not in columns:
            cursor.execute('''
                CREATE TABLE user_templates_new (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    name VARCHAR(200),
                    file_path VARCHAR(500) NOT NULL,
                    file_size INTEGER,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            cursor.execute('''
                INSERT INTO user_templates_new (id, user_id, name, file_path, file_size, created_at, updated_at)
                SELECT id, ?, name, file_path, file_size, created_at, updated_at
                FROM user_templates
            ''', (admin_id,))

            # 获取迁移的数量
            cursor.execute('SELECT COUNT(*) FROM user_templates')
            template_count = cursor.fetchone()[0]

            cursor.execute('DROP TABLE user_templates')
            cursor.execute('ALTER TABLE user_templates_new RENAME TO user_templates')
            cursor.execute('CREATE INDEX idx_user_templates_user_id ON user_templates(user_id)')
            print(f"    -> Migrated {template_count} user_templates to admin user ({admin_id})")
        else:
            print("    -> user_templates table already has user_id column, skipping...")

        # ========== Step 8: 提交事务 ==========
        print("[8/8] Committing changes...")
        conn.commit()

        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)
        print(f"\nDefault admin account created:")
        print(f"  Username: {DEFAULT_ADMIN_USERNAME}")
        print(f"  Password: {DEFAULT_ADMIN_PASSWORD}")
        print(f"  ID: {admin_id}")
        print("\n  Please change the admin password after first login!")

    except Exception as e:
        conn.rollback()
        print(f"\nMigration failed: {e}")
        raise
    finally:
        conn.close()


def rollback():
    """回滚迁移（仅用于开发测试）"""
    print(f"Database path: {DATABASE_PATH}")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("Rolling back migration...")
        cursor.execute('DROP TABLE IF EXISTS premium_history')
        cursor.execute('DROP TABLE IF EXISTS recharge_codes')
        cursor.execute('DROP TABLE IF EXISTS user_settings')
        cursor.execute('DROP TABLE IF EXISTS users')
        conn.commit()
        print("Rollback completed!")
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback()
    else:
        migrate()
