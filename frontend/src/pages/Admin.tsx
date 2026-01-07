import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, Users, CreditCard, Plus, Trash2, Crown, Ban, Check, Search, Copy, Settings, BarChart3 } from 'lucide-react';
import { Button, Input, Card, Loading, useToast, useConfirm } from '@/components/shared';
import { UserMenu } from '@/components/auth';
import { SystemSettingsPanel } from '@/components/admin';
import { useAuthStore } from '@/store/useAuthStore';
import * as api from '@/api/endpoints';
import type { User } from '@/types';
import type { AdminStats, RechargeCode, UserUsageStatsData, UserUsageStat } from '@/api/endpoints';

type TabType = 'stats' | 'users' | 'codes' | 'settings';

export const Admin: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();

  const [activeTab, setActiveTab] = useState<TabType>('stats');
  const [isLoading, setIsLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [userUsageStats, setUserUsageStats] = useState<UserUsageStatsData | null>(null);

  // Users
  const [users, setUsers] = useState<User[]>([]);
  const [userSearch, setUserSearch] = useState('');
  const [userPage, setUserPage] = useState(1);
  const [userTotal, setUserTotal] = useState(0);

  // Recharge codes
  const [codes, setCodes] = useState<RechargeCode[]>([]);
  const [codePage, setCodePage] = useState(1);
  const [codeTotal, setCodeTotal] = useState(0);
  const [showCodeFilter, setShowCodeFilter] = useState<'all' | 'used' | 'unused'>('all');

  // Create codes modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createCount, setCreateCount] = useState(10);
  const [createPoints, setCreatePoints] = useState(500);
  const [createExpireDays, setCreateExpireDays] = useState<number | null>(30);
  const [isCreating, setIsCreating] = useState(false);

  // Check if user is admin
  useEffect(() => {
    if (user && user.role !== 'admin') {
      navigate('/');
    }
  }, [user, navigate]);

  // Load data based on active tab
  useEffect(() => {
    if (activeTab === 'stats') {
      loadStats();
    } else if (activeTab === 'users') {
      loadUsers();
    } else if (activeTab === 'codes') {
      loadCodes();
    }
  }, [activeTab, userPage, userSearch, codePage, showCodeFilter]);

  const loadStats = async () => {
    setIsLoading(true);
    try {
      const [statsResponse, usageResponse] = await Promise.all([
        api.getAdminStats(),
        api.getUserUsageStats(),
      ]);
      if (statsResponse.data) {
        setStats(statsResponse.data);
      }
      if (usageResponse.data) {
        setUserUsageStats(usageResponse.data);
      }
    } catch (err) {
      show({ message: '加载统计数据失败', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const response = await api.adminListUsers({
        page: userPage,
        per_page: 20,
        search: userSearch || undefined,
      });
      if (response.data) {
        setUsers(response.data.users);
        setUserTotal(response.data.total);
      }
    } catch (err) {
      show({ message: '加载用户列表失败', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const loadCodes = async () => {
    setIsLoading(true);
    try {
      const response = await api.adminListRechargeCodes({
        page: codePage,
        per_page: 20,
        is_used: showCodeFilter === 'all' ? undefined : showCodeFilter === 'used' ? 'true' : 'false',
      });
      if (response.data) {
        setCodes(response.data.codes);
        setCodeTotal(response.data.total);
      }
    } catch (err) {
      show({ message: '加载充值码列表失败', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleGrantPoints = async (targetUser: User) => {
    const points = prompt('请输入要发放的积分数量：', '500');
    if (!points) return;

    const pointsNum = parseInt(points, 10);
    if (isNaN(pointsNum) || pointsNum <= 0) {
      show({ message: '请输入有效的积分数量', type: 'error' });
      return;
    }

    const expireDays = prompt('请输入积分有效期（天数，留空表示永久）：', '30');
    const expireDaysNum = expireDays ? parseInt(expireDays, 10) : null;

    try {
      const response = await api.adminGrantPoints(targetUser.id, {
        points: pointsNum,
        expire_days: expireDaysNum
      });
      if (response.success) {
        show({ message: response.data?.message || '操作成功', type: 'success' });
        loadUsers();
        loadStats();
      }
    } catch (err) {
      show({ message: '操作失败', type: 'error' });
    }
  };

  const handleDeductPoints = async (targetUser: User) => {
    const points = prompt('请输入要扣除的积分数量：', '100');
    if (!points) return;

    const pointsNum = parseInt(points, 10);
    if (isNaN(pointsNum) || pointsNum <= 0) {
      show({ message: '请输入有效的积分数量', type: 'error' });
      return;
    }

    const note = prompt('请输入扣除原因（可选）：', '');

    try {
      const response = await api.adminDeductPoints(targetUser.id, {
        points: pointsNum,
        note: note || undefined
      });
      if (response.success) {
        show({ message: response.data?.message || '操作成功', type: 'success' });
        loadUsers();
        loadStats();
      }
    } catch (err: any) {
      show({ message: err?.response?.data?.error?.message || '操作失败', type: 'error' });
    }
  };

  const handleRevokePremium = async (targetUser: User) => {
    confirm(
      `确定要清空用户 ${targetUser.username} 的所有积分吗？此操作不可恢复！`,
      async () => {
        try {
          const response = await api.adminRevokePremium(targetUser.id);
          if (response.success) {
            show({ message: response.data?.message || '操作成功', type: 'success' });
            loadUsers();
            loadStats();
          }
        } catch (err) {
          show({ message: '操作失败', type: 'error' });
        }
      },
      {
        title: '清空积分',
        confirmText: '确定清空',
        cancelText: '取消',
        variant: 'danger',
      }
    );
  };

  const handleToggleActive = async (targetUser: User) => {
    const action = targetUser.is_active ? '禁用' : '启用';
    confirm(
      `确定要${action}用户 ${targetUser.username} 吗？`,
      async () => {
        try {
          const response = await api.adminToggleUserActive(targetUser.id);
          if (response.success) {
            show({ message: response.data?.message || '操作成功', type: 'success' });
            loadUsers();
          }
        } catch (err) {
          show({ message: '操作失败', type: 'error' });
        }
      },
      {
        title: `${action}用户`,
        confirmText: `确定${action}`,
        cancelText: '取消',
        variant: action === '禁用' ? 'danger' : 'warning',
      }
    );
  };

  const handleDeleteUser = async (targetUser: User) => {
    confirm(
      `确定要删除用户 ${targetUser.username} 吗？此操作不可恢复！`,
      async () => {
        try {
          const response = await api.adminDeleteUser(targetUser.id);
          if (response.success) {
            show({ message: response.data?.message || '删除成功', type: 'success' });
            loadUsers();
            loadStats();
          }
        } catch (err: any) {
          show({ message: err?.response?.data?.error?.message || '删除失败', type: 'error' });
        }
      },
      {
        title: '删除用户',
        confirmText: '确定删除',
        cancelText: '取消',
        variant: 'danger',
      }
    );
  };

  const handleCreateCodes = async () => {
    if (createCount <= 0 || createPoints <= 0) {
      show({ message: '请输入有效的数量和积分', type: 'error' });
      return;
    }

    setIsCreating(true);
    try {
      const response = await api.adminCreateRechargeCodes({
        count: createCount,
        points: createPoints,
        points_expire_days: createExpireDays,
      });
      if (response.success) {
        show({ message: response.data?.message || '创建成功', type: 'success' });
        setShowCreateModal(false);
        loadCodes();
        loadStats();
      }
    } catch (err) {
      show({ message: '创建失败', type: 'error' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteCode = async (code: RechargeCode) => {
    if (code.is_used) {
      show({ message: '已使用的充值码不能删除', type: 'error' });
      return;
    }

    confirm(
      `确定要删除充值码 ${code.code} 吗？`,
      async () => {
        try {
          const response = await api.adminDeleteRechargeCode(code.id);
          if (response.success) {
            show({ message: '删除成功', type: 'success' });
            loadCodes();
            loadStats();
          }
        } catch (err) {
          show({ message: '删除失败', type: 'error' });
        }
      },
      {
        title: '删除充值码',
        confirmText: '确定删除',
        cancelText: '取消',
        variant: 'danger',
      }
    );
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    show({ message: '已复制到剪贴板', type: 'success' });
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString('zh-CN');
  };

  const formatCurrency = (num: number) => {
    return `¥${num.toFixed(2)}`;
  };

  if (!user || user.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loading text="验证权限..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-banana-50 via-white to-gray-50">
      <ToastContainer />
      {ConfirmDialog}

      {/* 导航栏 */}
      <nav className="h-14 md:h-16 bg-white shadow-sm border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-3 md:px-4 h-full flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 md:w-10 md:h-10 bg-gradient-to-br from-banana-500 to-banana-600 rounded-lg flex items-center justify-center text-xl md:text-2xl">
              🍌
            </div>
            <span className="text-lg md:text-xl font-bold text-gray-900">管理后台</span>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <Button
              variant="ghost"
              size="sm"
              icon={<Home size={16} />}
              onClick={() => navigate('/')}
            >
              返回首页
            </Button>
            <UserMenu />
          </div>
        </div>
      </nav>

      {/* 标签页 */}
      <div className="max-w-7xl mx-auto px-3 md:px-4 py-4">
        <div className="flex gap-2 mb-6">
          <Button
            variant={activeTab === 'stats' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab('stats')}
          >
            统计概览
          </Button>
          <Button
            variant={activeTab === 'users' ? 'primary' : 'ghost'}
            size="sm"
            icon={<Users size={16} />}
            onClick={() => setActiveTab('users')}
          >
            用户管理
          </Button>
          <Button
            variant={activeTab === 'codes' ? 'primary' : 'ghost'}
            size="sm"
            icon={<CreditCard size={16} />}
            onClick={() => setActiveTab('codes')}
          >
            充值码管理
          </Button>
          <Button
            variant={activeTab === 'settings' ? 'primary' : 'ghost'}
            size="sm"
            icon={<Settings size={16} />}
            onClick={() => setActiveTab('settings')}
          >
            系统设置
          </Button>
        </div>

        {/* 统计概览 */}
        {activeTab === 'stats' && (
          <div className="space-y-6">
            {/* 基础统计卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="p-6">
                <h3 className="text-sm text-gray-500 mb-2">总用户数</h3>
                <p className="text-3xl font-bold text-gray-900">{stats?.users.total || 0}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm text-gray-500 mb-2">高级会员</h3>
                <p className="text-3xl font-bold text-yellow-600">{stats?.users.premium || 0}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm text-gray-500 mb-2">未使用充值码</h3>
                <p className="text-3xl font-bold text-green-600">{stats?.recharge_codes.unused || 0}</p>
              </Card>
              <Card className="p-6">
                <h3 className="text-sm text-gray-500 mb-2">已使用充值码</h3>
                <p className="text-3xl font-bold text-gray-400">{stats?.recharge_codes.used || 0}</p>
              </Card>
            </div>

            {/* 用量统计汇总 */}
            {userUsageStats && (
              <>
                <Card className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <BarChart3 size={20} />
                    系统API消耗统计
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    <div className="text-center p-4 bg-blue-50 rounded-lg">
                      <p className="text-sm text-gray-500">图像生成次数</p>
                      <p className="text-2xl font-bold text-blue-600">{formatNumber(userUsageStats.summary.total_image_count)}</p>
                    </div>
                    <div className="text-center p-4 bg-purple-50 rounded-lg">
                      <p className="text-sm text-gray-500">文本调用次数</p>
                      <p className="text-2xl font-bold text-purple-600">{formatNumber(userUsageStats.summary.total_text_count)}</p>
                    </div>
                    <div className="text-center p-4 bg-indigo-50 rounded-lg">
                      <p className="text-sm text-gray-500">总Tokens消耗</p>
                      <p className="text-2xl font-bold text-indigo-600">{formatNumber(userUsageStats.summary.total_tokens)}</p>
                    </div>
                    <div className="text-center p-4 bg-orange-50 rounded-lg">
                      <p className="text-sm text-gray-500">图像费用</p>
                      <p className="text-2xl font-bold text-orange-600">{formatCurrency(userUsageStats.summary.total_image_cost)}</p>
                    </div>
                    <div className="text-center p-4 bg-pink-50 rounded-lg">
                      <p className="text-sm text-gray-500">文本费用</p>
                      <p className="text-2xl font-bold text-pink-600">{formatCurrency(userUsageStats.summary.total_text_cost)}</p>
                    </div>
                    <div className="text-center p-4 bg-red-50 rounded-lg">
                      <p className="text-sm text-gray-500">总消耗</p>
                      <p className="text-2xl font-bold text-red-600">{formatCurrency(userUsageStats.summary.total_cost)}</p>
                    </div>
                  </div>
                </Card>

                {/* 用户消费柱状图 */}
                {userUsageStats.user_stats.length > 0 && (
                  <Card className="p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">用户消费分布</h3>
                    <div className="space-y-3">
                      {userUsageStats.user_stats.slice(0, 10).map((stat, index) => {
                        const maxCost = userUsageStats.user_stats[0]?.total_cost || 1;
                        const percentage = (stat.total_cost / maxCost) * 100;
                        return (
                          <div key={stat.user_id} className="flex items-center gap-3">
                            <span className="w-24 text-sm font-medium text-gray-700 truncate" title={stat.username}>
                              {stat.username}
                            </span>
                            <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
                                style={{ width: `${Math.max(percentage, 2)}%` }}
                              />
                            </div>
                            <span className="w-20 text-sm font-medium text-gray-900 text-right">
                              {formatCurrency(stat.total_cost)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}

                {/* 用户使用量明细表 */}
                <Card className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">用户使用量明细</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-200 bg-gray-50">
                          <th className="text-left py-3 px-3 text-sm font-medium text-gray-500">用户名</th>
                          <th className="text-left py-3 px-3 text-sm font-medium text-gray-500">邮箱</th>
                          <th className="text-left py-3 px-3 text-sm font-medium text-gray-500">等级</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">图像生成</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">文本调用</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">Tokens</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">图像费用</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">文本费用</th>
                          <th className="text-right py-3 px-3 text-sm font-medium text-gray-500">总消耗</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userUsageStats.user_stats.map((stat) => (
                          <tr key={stat.user_id} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="py-3 px-3 font-medium">{stat.username}</td>
                            <td className="py-3 px-3 text-gray-500">{stat.email || '-'}</td>
                            <td className="py-3 px-3">
                              {stat.tier === 'premium' ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                                  <Crown size={12} /> 高级
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">免费</span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-right">{formatNumber(stat.image_generation_count)}</td>
                            <td className="py-3 px-3 text-right">{formatNumber(stat.text_generation_count)}</td>
                            <td className="py-3 px-3 text-right">{formatNumber(stat.total_tokens)}</td>
                            <td className="py-3 px-3 text-right text-orange-600">{formatCurrency(stat.image_cost)}</td>
                            <td className="py-3 px-3 text-right text-pink-600">{formatCurrency(stat.text_cost)}</td>
                            <td className="py-3 px-3 text-right font-medium text-red-600">{formatCurrency(stat.total_cost)}</td>
                          </tr>
                        ))}
                        {/* 汇总行 */}
                        <tr className="bg-gray-50 font-medium">
                          <td className="py-3 px-3" colSpan={3}>汇总</td>
                          <td className="py-3 px-3 text-right">{formatNumber(userUsageStats.summary.total_image_count)}</td>
                          <td className="py-3 px-3 text-right">{formatNumber(userUsageStats.summary.total_text_count)}</td>
                          <td className="py-3 px-3 text-right">{formatNumber(userUsageStats.summary.total_tokens)}</td>
                          <td className="py-3 px-3 text-right text-orange-600">{formatCurrency(userUsageStats.summary.total_image_cost)}</td>
                          <td className="py-3 px-3 text-right text-pink-600">{formatCurrency(userUsageStats.summary.total_text_cost)}</td>
                          <td className="py-3 px-3 text-right text-red-600">{formatCurrency(userUsageStats.summary.total_cost)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p className="text-xs text-gray-400 mt-4">
                    * 费用计算规则：图像生成 ¥1.5/次，文本调用 ¥3.5/1M tokens。仅统计使用系统API的调用。
                  </p>
                </Card>
              </>
            )}
          </div>
        )}

        {/* 用户管理 */}
        {activeTab === 'users' && (
          <Card className="p-4">
            <div className="flex items-center gap-4 mb-4">
              <div className="flex-1 relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="搜索用户名或邮箱..."
                  value={userSearch}
                  onChange={(e) => {
                    setUserSearch(e.target.value);
                    setUserPage(1);
                  }}
                  className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500"
                />
              </div>
            </div>

            {isLoading ? (
              <Loading text="加载中..." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">用户名</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">邮箱</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">积分</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">等级</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">状态</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{u.username}</span>
                            {u.role === 'admin' && (
                              <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-600 rounded">管理员</span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-2 text-gray-500">{u.email || '-'}</td>
                        <td className="py-3 px-2">
                          <span className="font-bold text-banana-600">{u.valid_points ?? 0}</span>
                        </td>
                        <td className="py-3 px-2">
                          {u.role === 'admin' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded">
                              管理员
                            </span>
                          ) : u.tier === 'premium' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                              <Crown size={12} /> 高级
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">免费</span>
                          )}
                        </td>
                        <td className="py-3 px-2">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 text-green-600">
                              <Check size={14} /> 正常
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-red-600">
                              <Ban size={14} /> 禁用
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-1">
                            {u.role !== 'admin' && (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleGrantPoints(u)}
                                  className="text-green-600 hover:bg-green-50"
                                >
                                  发放积分
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeductPoints(u)}
                                  className="text-orange-600 hover:bg-orange-50"
                                >
                                  扣除积分
                                </Button>
                                {(u.valid_points ?? 0) > 0 && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleRevokePremium(u)}
                                    className="text-red-600 hover:bg-red-50"
                                  >
                                    清空积分
                                  </Button>
                                )}
                              </>
                            )}
                            {u.role !== 'admin' && (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleToggleActive(u)}
                                  className={u.is_active ? 'text-red-600 hover:bg-red-50' : 'text-green-600 hover:bg-green-50'}
                                >
                                  {u.is_active ? '禁用' : '启用'}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  icon={<Trash2 size={14} />}
                                  onClick={() => handleDeleteUser(u)}
                                  className="text-red-600 hover:bg-red-50"
                                >
                                  删除
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* 分页 */}
            <div className="flex justify-between items-center mt-4">
              <span className="text-sm text-gray-500">共 {userTotal} 个用户</span>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={userPage <= 1}
                  onClick={() => setUserPage(userPage - 1)}
                >
                  上一页
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={userPage * 20 >= userTotal}
                  onClick={() => setUserPage(userPage + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* 充值码管理 */}
        {activeTab === 'codes' && (
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex gap-2">
                <Button
                  variant={showCodeFilter === 'all' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => { setShowCodeFilter('all'); setCodePage(1); }}
                >
                  全部
                </Button>
                <Button
                  variant={showCodeFilter === 'unused' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => { setShowCodeFilter('unused'); setCodePage(1); }}
                >
                  未使用
                </Button>
                <Button
                  variant={showCodeFilter === 'used' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => { setShowCodeFilter('used'); setCodePage(1); }}
                >
                  已使用
                </Button>
              </div>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={16} />}
                onClick={() => setShowCreateModal(true)}
              >
                生成充值码
              </Button>
            </div>

            {isLoading ? (
              <Loading text="加载中..." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">充值码</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">积分</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">有效期</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">状态</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">创建时间</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {codes.map((code) => (
                      <tr key={code.id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-2">
                            <code className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">{code.code}</code>
                            <button
                              onClick={() => copyToClipboard(code.code)}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <Copy size={14} />
                            </button>
                          </div>
                        </td>
                        <td className="py-3 px-2 font-medium text-banana-600">{code.points ?? code.duration_days ?? '-'}</td>
                        <td className="py-3 px-2 text-sm text-gray-500">
                          {code.points_expire_days === null || code.points_expire_days === undefined ? '永久' : `${code.points_expire_days}天`}
                        </td>
                        <td className="py-3 px-2">
                          {code.is_used ? (
                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">已使用</span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs bg-green-100 text-green-600 rounded">未使用</span>
                          )}
                        </td>
                        <td className="py-3 px-2 text-sm text-gray-500">{formatDate(code.created_at)}</td>
                        <td className="py-3 px-2">
                          {!code.is_used && (
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<Trash2 size={14} />}
                              onClick={() => handleDeleteCode(code)}
                              className="text-red-600 hover:bg-red-50"
                            >
                              删除
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* 分页 */}
            <div className="flex justify-between items-center mt-4">
              <span className="text-sm text-gray-500">共 {codeTotal} 个充值码</span>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={codePage <= 1}
                  onClick={() => setCodePage(codePage - 1)}
                >
                  上一页
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={codePage * 20 >= codeTotal}
                  onClick={() => setCodePage(codePage + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* 系统设置 */}
        {activeTab === 'settings' && <SystemSettingsPanel />}
      </div>

      {/* 创建充值码弹窗 */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md p-6 m-4">
            <h2 className="text-xl font-bold mb-4">生成充值码</h2>
            <div className="space-y-4">
              <Input
                label="生成数量"
                type="number"
                value={createCount}
                onChange={(e) => setCreateCount(parseInt(e.target.value) || 0)}
                min={1}
                max={100}
              />
              <Input
                label="积分数量"
                type="number"
                value={createPoints}
                onChange={(e) => setCreatePoints(parseInt(e.target.value) || 0)}
                min={1}
                placeholder="每个充值码的积分数量"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">积分有效期</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500"
                    value={createExpireDays ?? ''}
                    onChange={(e) => setCreateExpireDays(e.target.value ? parseInt(e.target.value) : null)}
                    min={1}
                    placeholder="天数"
                  />
                  <button
                    type="button"
                    onClick={() => setCreateExpireDays(null)}
                    className={`px-3 py-2 rounded-lg text-sm ${createExpireDays === null ? 'bg-banana-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    永久
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">留空或点击"永久"表示积分永不过期</p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="ghost" onClick={() => setShowCreateModal(false)}>
                取消
              </Button>
              <Button variant="primary" onClick={handleCreateCodes} loading={isCreating}>
                生成
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
