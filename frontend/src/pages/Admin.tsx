import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, Users, CreditCard, Plus, Trash2, Crown, Ban, Check, Search, Copy } from 'lucide-react';
import { Button, Input, Card, Loading, useToast, useConfirm } from '@/components/shared';
import { UserMenu } from '@/components/auth';
import { useAuthStore } from '@/store/useAuthStore';
import * as api from '@/api/endpoints';
import type { User } from '@/types';
import type { AdminStats, RechargeCode } from '@/api/endpoints';

type TabType = 'stats' | 'users' | 'codes';

export const Admin: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();

  const [activeTab, setActiveTab] = useState<TabType>('stats');
  const [isLoading, setIsLoading] = useState(true);

  // Stats
  const [stats, setStats] = useState<AdminStats | null>(null);

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
  const [createDays, setCreateDays] = useState(30);
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
      const response = await api.getAdminStats();
      if (response.data) {
        setStats(response.data);
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

  const handleGrantPremium = async (targetUser: User) => {
    const days = prompt('请输入要添加的会员天数：', '30');
    if (!days) return;

    const daysNum = parseInt(days, 10);
    if (isNaN(daysNum) || daysNum <= 0) {
      show({ message: '请输入有效��天数', type: 'error' });
      return;
    }

    try {
      const response = await api.adminGrantPremium(targetUser.id, { duration_days: daysNum });
      if (response.success) {
        show({ message: response.data?.message || '操作成功', type: 'success' });
        loadUsers();
        loadStats();
      }
    } catch (err) {
      show({ message: '操作失败', type: 'error' });
    }
  };

  const handleRevokePremium = async (targetUser: User) => {
    confirm(
      `确定要撤销用户 ${targetUser.username} 的会员资格吗？`,
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
        title: '撤销会员',
        confirmText: '确定撤销',
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

  const handleCreateCodes = async () => {
    if (createCount <= 0 || createDays <= 0) {
      show({ message: '请输入有效的数量和天数', type: 'error' });
      return;
    }

    setIsCreating(true);
    try {
      const response = await api.adminCreateRechargeCodes({
        count: createCount,
        duration_days: createDays,
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
        </div>

        {/* 统计概览 */}
        {activeTab === 'stats' && (
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
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">等级</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">状态</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">会员到期</th>
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
                          {u.tier === 'premium' ? (
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
                        <td className="py-3 px-2 text-sm text-gray-500">
                          {u.premium_expires_at ? formatDate(u.premium_expires_at) : '-'}
                        </td>
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-1">
                            {u.tier === 'premium' ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRevokePremium(u)}
                                className="text-red-600 hover:bg-red-50"
                              >
                                撤销会员
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleGrantPremium(u)}
                                className="text-yellow-600 hover:bg-yellow-50"
                              >
                                授予会员
                              </Button>
                            )}
                            {u.role !== 'admin' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleToggleActive(u)}
                                className={u.is_active ? 'text-red-600 hover:bg-red-50' : 'text-green-600 hover:bg-green-50'}
                              >
                                {u.is_active ? '禁用' : '启用'}
                              </Button>
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
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">天数</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">状态</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">创建时间</th>
                      <th className="text-left py-3 px-2 text-sm font-medium text-gray-500">使用时间</th>
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
                        <td className="py-3 px-2">{code.duration_days} 天</td>
                        <td className="py-3 px-2">
                          {code.is_used ? (
                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">已使用</span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs bg-green-100 text-green-600 rounded">未使用</span>
                          )}
                        </td>
                        <td className="py-3 px-2 text-sm text-gray-500">{formatDate(code.created_at)}</td>
                        <td className="py-3 px-2 text-sm text-gray-500">{formatDate(code.used_at)}</td>
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
                label="会员天数"
                type="number"
                value={createDays}
                onChange={(e) => setCreateDays(parseInt(e.target.value) || 0)}
                min={1}
              />
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
