# PRD：会员体系改造 - 从时间制到积分制

## 1. 概述

### 1.1 背景
当前系统采用基于时间的会员制度（premium会员有过期时间），需要改造为基于积分的消费制度，以支持更灵活的商业化运营。

### 1.2 核心变化
| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| 会员判定 | tier字段 + 过期时间 | 有效积分 > 0 即为会员 |
| 充值码 | 充值天数 | 充值积分 + 有效期 |
| 使用限制 | 每日生成页数限制 | 按积分消耗，无数量限制 |
| 邀请奖励 | 奖励天数 | 奖励积分 |

### 1.3 默认配置
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 消耗比例 | 15积分/页 | 每生成1页PPT消耗 |
| 新用户赠送 | 300积分 | 有效期3天 |

---

## 2. 数据库设计

### 2.1 新增表

#### 2.1.1 PointsBalance（积分批次表）
记录每一批积分的来源和有效期，支持FIFO消耗策略。

```sql
CREATE TABLE points_balance (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,

    -- 积分信息
    amount INT NOT NULL,              -- 原始积分数量
    remaining INT NOT NULL,           -- 剩余积分数量

    -- 来源信息
    source VARCHAR(32) NOT NULL,      -- 来源类型
    source_id VARCHAR(36),            -- 关联ID（如充值码ID）
    source_note TEXT,                 -- 备注说明

    -- 有效期
    expires_at DATETIME,              -- 过期时间，NULL表示永不过期

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_expires (user_id, expires_at),
    INDEX idx_source (source, source_id)
);
```

**source 枚举值：**
- `register`: 注册赠送
- `recharge`: 充值码兑换
- `referral_inviter_register`: 邀请者注册奖励
- `referral_invitee_register`: 被邀请者注册奖励
- `referral_inviter_upgrade`: 邀请者升级奖励
- `admin_grant`: 管理员手动发放
- `admin_deduct`: 管理员手动扣除
- `migration`: 历史数据迁移

#### 2.1.2 PointsTransaction（积分流水表）
记录所有积分变动明细。

```sql
CREATE TABLE points_transaction (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,

    -- 变动信息
    type VARCHAR(16) NOT NULL,        -- income/expense
    amount INT NOT NULL,              -- 变动数量（正数）
    balance_after INT NOT NULL,       -- 变动后总有效余额

    -- 关联信息
    balance_id VARCHAR(36),           -- 关联的积分批次ID
    description VARCHAR(255),         -- 描述

    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (balance_id) REFERENCES points_balance(id) ON DELETE SET NULL,
    INDEX idx_user_created (user_id, created_at DESC)
);
```

**type 枚举值：**
- `income`: 积分收入
- `expense`: 积分消耗
- `expired`: 积分过期（自动记录）

### 2.2 修改表

#### 2.2.1 RechargeCode（充值码表）
```sql
-- 删除字段
ALTER TABLE recharge_codes DROP COLUMN duration_days;

-- 新增字段
ALTER TABLE recharge_codes ADD COLUMN points INT NOT NULL DEFAULT 0;
ALTER TABLE recharge_codes ADD COLUMN points_expire_days INT;  -- NULL表示永不过期
```

#### 2.2.2 SystemSettings（系统设置表）
```sql
-- 删除字段
ALTER TABLE system_settings DROP COLUMN default_user_tier;
ALTER TABLE system_settings DROP COLUMN default_premium_days;
ALTER TABLE system_settings DROP COLUMN daily_image_generation_limit;
ALTER TABLE system_settings DROP COLUMN enable_usage_limit;
ALTER TABLE system_settings DROP COLUMN referral_register_reward_days;
ALTER TABLE system_settings DROP COLUMN referral_invitee_reward_days;
ALTER TABLE system_settings DROP COLUMN referral_premium_reward_days;

-- 新增字段：积分配置
ALTER TABLE system_settings ADD COLUMN points_per_yuan INT DEFAULT 10;
ALTER TABLE system_settings ADD COLUMN points_per_page INT DEFAULT 15;

-- 新增字段：注册赠送
ALTER TABLE system_settings ADD COLUMN register_bonus_points INT DEFAULT 300;
ALTER TABLE system_settings ADD COLUMN register_bonus_expire_days INT DEFAULT 3;

-- 新增字段：邀请奖励
ALTER TABLE system_settings ADD COLUMN referral_inviter_register_points INT DEFAULT 100;
ALTER TABLE system_settings ADD COLUMN referral_invitee_register_points INT DEFAULT 100;
ALTER TABLE system_settings ADD COLUMN referral_inviter_upgrade_points INT DEFAULT 450;
ALTER TABLE system_settings ADD COLUMN referral_points_expire_days INT;  -- NULL表示永不过期
```

#### 2.2.3 User（用户表）
```sql
-- 删除字段
ALTER TABLE users DROP COLUMN tier;
ALTER TABLE users DROP COLUMN premium_expires_at;
```

**注意**：tier 改为动态计算属性，不再存储。

#### 2.2.4 DailyUsage（每日用量表）
保留此表用于统计，但不再用于限制。

#### 2.2.5 PremiumHistory（会员历史表）
此表将废弃，由 PointsTransaction 替代。可选择保留历史数据或迁移后删除。

---

## 3. 核心业务逻辑

### 3.1 积分计算

#### 3.1.1 有效积分计算
```python
def get_valid_points(user_id: str) -> int:
    """获取用户当前有效积分总数"""
    now = datetime.utcnow()
    total = db.session.query(func.sum(PointsBalance.remaining)).filter(
        PointsBalance.user_id == user_id,
        PointsBalance.remaining > 0,
        or_(
            PointsBalance.expires_at.is_(None),  # 永不过期
            PointsBalance.expires_at > now        # 未过期
        )
    ).scalar()
    return total or 0
```

#### 3.1.2 tier 动态判断
```python
def get_effective_tier(user_id: str) -> str:
    """获取用户有效等级"""
    valid_points = get_valid_points(user_id)
    return 'premium' if valid_points > 0 else 'free'
```

#### 3.1.3 即将过期积分
```python
def get_expiring_points(user_id: str, days: int = 7) -> int:
    """获取N天内即将过期的积分"""
    now = datetime.utcnow()
    deadline = now + timedelta(days=days)
    total = db.session.query(func.sum(PointsBalance.remaining)).filter(
        PointsBalance.user_id == user_id,
        PointsBalance.remaining > 0,
        PointsBalance.expires_at.isnot(None),
        PointsBalance.expires_at > now,
        PointsBalance.expires_at <= deadline
    ).scalar()
    return total or 0
```

### 3.2 积分消耗（FIFO）

```python
def consume_points(user_id: str, amount: int, description: str) -> bool:
    """
    消耗积分（FIFO策略）
    允许最后一次请求产生负积分
    返回是否成功
    """
    valid_points = get_valid_points(user_id)

    # 如果已经是负数或0，拒绝消费
    if valid_points <= 0:
        return False

    # 允许消费（即使会产生负积分）
    now = datetime.utcnow()
    remaining_to_consume = amount
    consumed_from = []

    # 获取所有有效批次，按过期时间排序（先过期的先消耗，NULL最后）
    balances = PointsBalance.query.filter(
        PointsBalance.user_id == user_id,
        PointsBalance.remaining > 0,
        or_(
            PointsBalance.expires_at.is_(None),
            PointsBalance.expires_at > now
        )
    ).order_by(
        # NULL排最后，其他按时间升序
        case((PointsBalance.expires_at.is_(None), 1), else_=0),
        PointsBalance.expires_at.asc()
    ).all()

    for balance in balances:
        if remaining_to_consume <= 0:
            break

        consume_from_this = min(balance.remaining, remaining_to_consume)
        balance.remaining -= consume_from_this
        remaining_to_consume -= consume_from_this
        consumed_from.append((balance.id, consume_from_this))

    # 如果还有剩余未消耗的（产生负积分情况）
    # 从最后一个批次继续扣（允许remaining为负）
    if remaining_to_consume > 0 and balances:
        last_balance = balances[-1]
        last_balance.remaining -= remaining_to_consume
        consumed_from.append((last_balance.id, remaining_to_consume))

    # 记录流水
    new_valid_points = get_valid_points(user_id)
    transaction = PointsTransaction(
        user_id=user_id,
        type='expense',
        amount=amount,
        balance_after=new_valid_points,
        description=description
    )
    db.session.add(transaction)
    db.session.commit()

    return True
```

### 3.3 积分发放

```python
def grant_points(
    user_id: str,
    amount: int,
    source: str,
    source_id: str = None,
    source_note: str = None,
    expire_days: int = None  # None表示永不过期
) -> PointsBalance:
    """发放积分"""
    expires_at = None
    if expire_days is not None:
        expires_at = datetime.utcnow() + timedelta(days=expire_days)

    balance = PointsBalance(
        user_id=user_id,
        amount=amount,
        remaining=amount,
        source=source,
        source_id=source_id,
        source_note=source_note,
        expires_at=expires_at
    )
    db.session.add(balance)

    # 记录流水
    valid_points = get_valid_points(user_id) + amount
    transaction = PointsTransaction(
        user_id=user_id,
        type='income',
        amount=amount,
        balance_after=valid_points,
        balance_id=balance.id,
        description=f"积分入账: {source}"
    )
    db.session.add(transaction)
    db.session.commit()

    return balance
```

---

## 4. API 设计

### 4.1 用户积分相关

#### GET /api/points/balance
获取用户积分信息

**响应：**
```json
{
  "valid_points": 850,
  "tier": "premium",
  "expiring_soon": {
    "points": 100,
    "days": 7,
    "earliest_expire": "2025-01-20T00:00:00Z"
  },
  "points_per_page": 15,
  "can_generate_pages": 56
}
```

#### GET /api/points/transactions
获取积分流水记录

**参数：**
- `page`: 页码（默认1）
- `per_page`: 每页数量（默认20）
- `type`: 筛选类型（income/expense/expired）

**响应：**
```json
{
  "transactions": [
    {
      "id": "xxx",
      "type": "expense",
      "amount": 15,
      "balance_after": 835,
      "description": "生成PPT页面",
      "created_at": "2025-01-10T10:30:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

#### GET /api/points/balances
获取积分批次明细

**响应：**
```json
{
  "balances": [
    {
      "id": "xxx",
      "amount": 300,
      "remaining": 150,
      "source": "register",
      "expires_at": "2025-01-15T00:00:00Z",
      "is_expiring_soon": true,
      "created_at": "2025-01-12T00:00:00Z"
    }
  ]
}
```

### 4.2 充值码相关

#### POST /api/points/redeem
兑换充值码

**请求：**
```json
{
  "code": "ABCD1234"
}
```

**响应：**
```json
{
  "success": true,
  "points_added": 500,
  "expires_at": null,
  "new_balance": 850
}
```

### 4.3 管理员相关

#### POST /api/admin/recharge-codes
创建充值码（修改）

**请求：**
```json
{
  "points": 500,
  "expire_days": null,
  "count": 10,
  "code_expires_at": "2025-06-01T00:00:00Z"
}
```

#### POST /api/admin/users/{user_id}/grant-points
管理员发放积分

**请求：**
```json
{
  "points": 1000,
  "expire_days": null,
  "note": "活动奖励"
}
```

#### POST /api/admin/users/{user_id}/deduct-points
管理员扣除积分

**请求：**
```json
{
  "points": 100,
  "note": "违规扣除"
}
```

#### GET /api/admin/system-settings
获取系统设置（修改响应）

**响应新增字段：**
```json
{
  "points_per_yuan": 10,
  "points_per_page": 15,
  "register_bonus_points": 300,
  "register_bonus_expire_days": 3,
  "referral_inviter_register_points": 100,
  "referral_invitee_register_points": 100,
  "referral_inviter_upgrade_points": 450,
  "referral_points_expire_days": null
}
```

#### PUT /api/admin/system-settings
更新系统设置（支持新字段）

---

## 5. 业务流程

### 5.1 新用户注册
```
1. 创建用户账户
2. 发放注册赠送积分（300积分，3天有效期）
3. 如有邀请码，处理邀请奖励
   - 被邀请者获得100积分（永久）
   - 邀请者获得100积分（永久）
4. 返回用户信息（包含积分和tier）
```

### 5.2 兑换充值码
```
1. 验证充值码有效性
2. 标记充值码为已使用
3. 发放积分到用户账户
4. 检查是否为被邀请用户的首次充值
   - 是：发放邀请者升级奖励（450积分）
5. 记录流水
6. 返回结果
```

### 5.3 生成PPT页面
```
1. 检查用户有效积分
   - <= 0：拒绝，返回积分不足
   - > 0：继续
2. 执行图片生成
3. 消耗积分（15积分/页）
4. 更新DailyUsage统计
5. 返回结果
```

### 5.4 积分过期处理
```
采用懒计算方式：
- 查询有效积分时自动过滤过期批次
- 无需定时任务

可选：定期清理任务
- 每天凌晨扫描已过期且remaining>0的批次
- 记录过期流水
- 将remaining设为0
```

---

## 6. 前端改动

### 6.1 用户界面

#### 6.1.1 顶部状态栏
- 显示当前积分余额
- 会员标识（有积分=皇冠图标）
- 点击查看积分详情

#### 6.1.2 积分详情页（新增）
- 当前有效积分
- 即将过期提醒（7天内）
- 积分明细列表（收入/支出）
- 积分批次列表（显示来源和过期时间）
- 兑换充值码入口

#### 6.1.3 生成页面
- 显示本次预计消耗积分
- 积分不足时显示提示
- 生成后显示消耗积分和剩余

### 6.2 管理后台

#### 6.2.1 充值码管理
- 创建时：积分数量 + 有效期天数（可选永久）
- 列表显示：积分数量、有效期

#### 6.2.2 用户管理
- 显示用户当前积分
- 操作：发放积分、扣除积分
- 发放时：输入积分数量、有效期、备注

#### 6.2.3 系统设置
- 积分配置区域
- 注册赠送配置
- 邀请奖励配置

---

## 7. 数据迁移

### 7.1 迁移策略

#### 7.1.1 已使用充值码的用户
```sql
-- 为每个曾经使用过充值码的用户发放积分
INSERT INTO points_balance (id, user_id, amount, remaining, source, source_note, expires_at, created_at)
SELECT
    UUID(),
    u.id,
    6000,
    6000,
    'migration',
    '历史会员迁移奖励',
    DATE_ADD(NOW(), INTERVAL 30 DAY),
    NOW()
FROM users u
WHERE EXISTS (
    SELECT 1 FROM recharge_codes rc
    WHERE rc.used_by_user_id = u.id
);

-- 额外赠送永久积分
INSERT INTO points_balance (id, user_id, amount, remaining, source, source_note, expires_at, created_at)
SELECT
    UUID(),
    u.id,
    300,
    300,
    'migration',
    '历史会员永久奖励',
    NULL,
    NOW()
FROM users u
WHERE EXISTS (
    SELECT 1 FROM recharge_codes rc
    WHERE rc.used_by_user_id = u.id
);
```

#### 7.1.2 未使用的充值码
```sql
-- 更新充值码表结构后，设置默认值
UPDATE recharge_codes
SET points = 300, points_expire_days = NULL
WHERE is_used = FALSE;
```

#### 7.1.3 用户表清理
```sql
-- 删除废弃字段（在迁移完成后执行）
ALTER TABLE users DROP COLUMN tier;
ALTER TABLE users DROP COLUMN premium_expires_at;
```

### 7.2 迁移脚本顺序
1. 创建新表（points_balance, points_transaction）
2. 修改 recharge_codes 表
3. 修改 system_settings 表
4. 迁移用户积分数据
5. 更新未使用充值码
6. 删除 users 表废弃字段
7. （可选）清理 premium_history 表

---

## 8. 兼容性考虑

### 8.1 管理员角色
- 管理员（role='admin'）不消耗积分
- 管理员始终可以使用系统API

### 8.2 API兼容
- `/api/premium/status` 保留，返回格式调整为积分信息
- 新增 `/api/points/*` 系列接口
- 旧接口逐步废弃

### 8.3 主分支兼容
- 主分支没有用户系统，不受影响
- 积分检查逻辑在用户系统模块内
- 保持模块独立性

---

## 9. 开发任务清单

### Phase 1: 数据库改造
- [ ] 创建 PointsBalance 模型
- [ ] 创建 PointsTransaction 模型
- [ ] 修改 RechargeCode 模型
- [ ] 修改 SystemSettings 模型
- [ ] 创建数据库迁移脚本

### Phase 2: 后端服务
- [ ] 创建 PointsService（积分核心服务）
- [ ] 修改 UsageService（消耗逻辑）
- [ ] 修改 ReferralService（邀请奖励）
- [ ] 修改注册流程
- [ ] 修改充值码兑换流程

### Phase 3: API接口
- [ ] 实现积分查询接口
- [ ] 实现积分流水接口
- [ ] 修改充值码接口
- [ ] 修改管理员接口
- [ ] 修改系统设置接口

### Phase 4: 前端改造
- [ ] 积分状态组件
- [ ] 积分详情页
- [ ] 修改生成页面
- [ ] 修改管理后台-充值码管理
- [ ] 修改管理后台-用户管理
- [ ] 修改管理后台-系统设置

### Phase 5: 数据迁移
- [ ] 编写迁移脚本
- [ ] 测试迁移
- [ ] 执行生产迁移

### Phase 6: 测试与上线
- [ ] 单元测试
- [ ] 集成测试
- [ ] 上线部署

---

## 10. 风险与注意事项

1. **并发消耗**：积分消耗需要考虑并发情况，建议使用数据库事务和行锁
2. **负积分处理**：允许最后一次请求产生负积分，需要在前端明确提示
3. **迁移回滚**：准备回滚方案，保留旧数据直到确认无误
4. **性能优化**：积分查询频繁，考虑缓存策略
5. **审计日志**：所有积分变动都有流水记录，便于审计
