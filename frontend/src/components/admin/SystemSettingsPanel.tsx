import React, { useState, useEffect } from 'react';
import { Save, Mail, Users, Gift, Image, RefreshCw, Coins } from 'lucide-react';
import { Button, Input, Card, Loading, useToast } from '@/components/shared';
import * as api from '@/api/endpoints';

interface SystemSettings {
  // 注册设置
  default_user_tier: 'free' | 'premium';
  default_premium_days: number;
  require_email_verification: boolean;
  // 积分设置
  points_per_page: number;
  register_bonus_points: number;
  register_bonus_expire_days: number | null;
  // 裂变积分设置
  referral_enabled: boolean;
  referral_inviter_register_points: number;
  referral_invitee_register_points: number;
  referral_inviter_upgrade_points: number;
  referral_points_expire_days: number | null;
  referral_domain: string;
  // 旧版设置（兼容）
  referral_register_reward_days?: number;
  referral_invitee_reward_days?: number;
  referral_premium_reward_days?: number;
  daily_image_generation_limit?: number;
  enable_usage_limit?: boolean;
  // SMTP设置
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password?: string;
  smtp_use_ssl: boolean;
  smtp_sender_name: string;
  smtp_configured: boolean;
}

interface UsageStats {
  daily_stats: Array<{ date: string; image_count: number; user_count: number }>;
  today_total: number;
  all_time_total: number;
}

interface ReferralStats {
  total_referrals: number;
  registered_referrals: number;
  premium_referrals: number;
  total_rewards_days: number;
}

export const SystemSettingsPanel: React.FC = () => {
  const { show, ToastContainer } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [referralStats, setReferralStats] = useState<ReferralStats | null>(null);
  const [testEmail, setTestEmail] = useState('');
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [settingsRes, usageRes, referralRes] = await Promise.all([
        api.getSystemSettings(),
        api.getUsageStats({ days: 7 }),
        api.getReferralStats(),
      ]);

      if (settingsRes.data) setSettings(settingsRes.data);
      if (usageRes.data) setUsageStats(usageRes.data);
      if (referralRes.data) setReferralStats(referralRes.data);
    } catch (err) {
      show({ message: '加载设置失败', type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    setIsSaving(true);
    try {
      const response = await api.updateSystemSettings(settings);
      if (response.success) {
        show({ message: '设置已保存', type: 'success' });
        if (response.data?.settings) {
          setSettings(response.data.settings);
        }
      }
    } catch (err) {
      show({ message: '保存失败', type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestSmtp = async () => {
    if (!testEmail) {
      show({ message: '请输入测试邮箱地址', type: 'error' });
      return;
    }

    setIsTesting(true);
    try {
      const response = await api.testSmtp({ test_email: testEmail });
      if (response.success) {
        show({ message: response.data?.message || '测试邮件已发送', type: 'success' });
      }
    } catch (err: any) {
      const apiMessage =
        err?.response?.data?.error?.message ||
        err?.response?.data?.message ||
        err?.message;
      show({ message: apiMessage || '发送测试邮件失败', type: 'error' });
    } finally {
      setIsTesting(false);
    }
  };

  if (isLoading) {
    return <Loading text="加载设置..." />;
  }

  if (!settings) {
    return <div className="text-center text-gray-500">无法加载设置</div>;
  }

  return (
    <div className="space-y-6">
      <ToastContainer />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Image size={20} className="text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">今日图片生成</p>
              <p className="text-xl font-bold">{usageStats?.today_total || 0} 页</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Image size={20} className="text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">累计图片生成</p>
              <p className="text-xl font-bold">{usageStats?.all_time_total || 0} 页</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Gift size={20} className="text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">邀请注册用户</p>
              <p className="text-xl font-bold">{referralStats?.registered_referrals || 0} 人</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Gift size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">邀请奖励天数</p>
              <p className="text-xl font-bold">{referralStats?.total_rewards_days || 0} 天</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 积分设置 */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Coins size={20} className="text-yellow-600" />
          积分设置
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="每页消耗积分"
            type="number"
            value={settings.points_per_page || 15}
            onChange={(e) => setSettings({ ...settings, points_per_page: parseInt(e.target.value) || 15 })}
            min={1}
            hint="生成1页PPT消耗的积分"
          />
          <Input
            label="新用户赠送积分"
            type="number"
            value={settings.register_bonus_points || 300}
            onChange={(e) => setSettings({ ...settings, register_bonus_points: parseInt(e.target.value) || 0 })}
            min={0}
            hint="新用户注册时赠送的积分"
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">赠送积分有效期（天）</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500"
                value={settings.register_bonus_expire_days ?? ''}
                onChange={(e) => setSettings({ ...settings, register_bonus_expire_days: e.target.value ? parseInt(e.target.value) : null })}
                min={1}
                placeholder="天数"
              />
              <button
                type="button"
                onClick={() => setSettings({ ...settings, register_bonus_expire_days: null })}
                className={`px-3 py-2 rounded-lg text-sm ${settings.register_bonus_expire_days === null ? 'bg-banana-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                永久
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* 注册设置 */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Users size={20} className="text-blue-600" />
          注册设置
        </h3>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="require_email_verification"
            checked={settings.require_email_verification}
            onChange={(e) => setSettings({ ...settings, require_email_verification: e.target.checked })}
            className="w-4 h-4 rounded border-gray-300 text-banana-600 focus:ring-banana-500"
          />
          <label htmlFor="require_email_verification" className="text-sm text-gray-700">
            要求邮箱验证（需先配置SMTP）
          </label>
        </div>
      </Card>

      {/* 裂变积分设置 */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Gift size={20} className="text-yellow-600" />
          邀请裂变设置
        </h3>
        <div className="space-y-4">
          {/* 功能开关 */}
          <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
            <input
              type="checkbox"
              id="referral_enabled"
              checked={settings.referral_enabled}
              onChange={(e) => setSettings({ ...settings, referral_enabled: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-banana-600 focus:ring-banana-500"
            />
            <label htmlFor="referral_enabled" className="text-sm text-gray-700 font-medium">
              启用邀请裂变功能
            </label>
            {!settings.referral_enabled && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded">已关闭</span>
            )}
          </div>

          {settings.referral_enabled && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="邀请者注册奖励（积分）"
                  type="number"
                  value={settings.referral_inviter_register_points || 100}
                  onChange={(e) => setSettings({ ...settings, referral_inviter_register_points: parseInt(e.target.value) || 0 })}
                  min={0}
                  hint="被邀请用户注册后，邀请者获得的积分"
                />
                <Input
                  label="被邀请者注册奖励（积分）"
                  type="number"
                  value={settings.referral_invitee_register_points || 100}
                  onChange={(e) => setSettings({ ...settings, referral_invitee_register_points: parseInt(e.target.value) || 0 })}
                  min={0}
                  hint="被邀请用户注册后，自己获得的积分"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="邀请者首充奖励（积分）"
                  type="number"
                  value={settings.referral_inviter_upgrade_points || 450}
                  onChange={(e) => setSettings({ ...settings, referral_inviter_upgrade_points: parseInt(e.target.value) || 0 })}
                  min={0}
                  hint="被邀请用户首次充值后，邀请者获得的积分"
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">邀请奖励积分有效期（天）</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-banana-500"
                      value={settings.referral_points_expire_days ?? ''}
                      onChange={(e) => setSettings({ ...settings, referral_points_expire_days: e.target.value ? parseInt(e.target.value) : null })}
                      min={1}
                      placeholder="天数"
                    />
                    <button
                      type="button"
                      onClick={() => setSettings({ ...settings, referral_points_expire_days: null })}
                      className={`px-3 py-2 rounded-lg text-sm ${settings.referral_points_expire_days === null ? 'bg-banana-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                    >
                      永久
                    </button>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="邀请链接域名"
                  type="text"
                  value={settings.referral_domain}
                  onChange={(e) => setSettings({ ...settings, referral_domain: e.target.value })}
                  hint="用于生成邀请链接（如：ppt.netopstec.com）"
                />
              </div>
            </>
          )}
        </div>
      </Card>

      {/* SMTP设置 */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Mail size={20} className="text-purple-600" />
          邮件服务器设置 (SMTP)
          {settings.smtp_configured && (
            <span className="ml-2 px-2 py-0.5 text-xs bg-green-100 text-green-600 rounded">已配置</span>
          )}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="SMTP服务器地址"
            type="text"
            value={settings.smtp_host || ''}
            onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
            placeholder="如: smtp.example.com"
          />
          <Input
            label="SMTP端口"
            type="number"
            value={settings.smtp_port || 465}
            onChange={(e) => setSettings({ ...settings, smtp_port: parseInt(e.target.value) || 465 })}
            placeholder="常用：25 / 465 / 587"
          />
          <Input
            label="发件人邮箱"
            type="email"
            value={settings.smtp_user || ''}
            onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })}
            placeholder="如: noreply@example.com"
          />
          <Input
            label="邮箱密码/授权码"
            type="password"
            value={settings.smtp_password || ''}
            onChange={(e) => setSettings({ ...settings, smtp_password: e.target.value })}
            placeholder="留空则不修改"
          />
          <Input
            label="发件人名称"
            type="text"
            value={settings.smtp_sender_name || ''}
            onChange={(e) => setSettings({ ...settings, smtp_sender_name: e.target.value })}
            placeholder="如: Banana Slides"
          />
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="smtp_use_ssl"
              checked={settings.smtp_use_ssl}
              onChange={(e) => setSettings({ ...settings, smtp_use_ssl: e.target.checked })}
              className="w-4 h-4 rounded border-gray-300 text-banana-600 focus:ring-banana-500"
            />
            <label htmlFor="smtp_use_ssl" className="text-sm text-gray-700">
              使用加密连接（SSL/STARTTLS）
            </label>
          </div>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          常用端口：465（SSL）/ 587（STARTTLS）/ 25（无加密或 STARTTLS）。110/143 等通常是收信端口，填在这里会导致测试失败。
        </p>

        {/* 测试SMTP */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <Input
              label=""
              type="email"
              value={testEmail}
              onChange={(e) => setTestEmail(e.target.value)}
              placeholder="输入测试邮箱地址"
              className="flex-1"
            />
            <Button
              variant="secondary"
              onClick={handleTestSmtp}
              loading={isTesting}
              disabled={!settings.smtp_configured && !settings.smtp_host}
            >
              发送测试邮件
            </Button>
          </div>
        </div>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end gap-3">
        <Button variant="ghost" icon={<RefreshCw size={16} />} onClick={loadData}>
          刷新
        </Button>
        <Button variant="primary" icon={<Save size={16} />} onClick={handleSave} loading={isSaving}>
          保存设置
        </Button>
      </div>
    </div>
  );
};
