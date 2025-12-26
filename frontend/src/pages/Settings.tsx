import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Home, Key, Image, Zap, Save, RotateCcw, Globe, FileText, User, Crown, Lock, Gift } from 'lucide-react';
import { Button, Input, Card, Loading, useToast, useConfirm } from '@/components/shared';
import { UserMenu } from '@/components/auth';
import { useAuthStore } from '@/store/useAuthStore';
import * as api from '@/api/endpoints';
import type { OutputLanguage } from '@/api/endpoints';
import { OUTPUT_LANGUAGE_OPTIONS } from '@/api/endpoints';
import type { Settings as SettingsType } from '@/types';

// 配置项类型定义
type FieldType = 'text' | 'password' | 'number' | 'select' | 'buttons';

interface FieldConfig {
  key: keyof typeof initialFormData;
  label: string;
  type: FieldType;
  placeholder?: string;
  description?: string;
  sensitiveField?: boolean;  // 是否为敏感字段（如 API Key）
  lengthKey?: keyof SettingsType;  // 用于显示已有长度的 key（如 api_key_length）
  options?: { value: string; label: string }[];  // select 类型的选项
  min?: number;
  max?: number;
}

interface SectionConfig {
  title: string;
  icon: React.ReactNode;
  fields: FieldConfig[];
}

// 初始表单数据
const initialFormData = {
  ai_provider_format: 'gemini' as 'openai' | 'gemini',
  api_base_url: '',
  api_key: '',
  text_model: '',
  image_model: '',
  image_caption_model: '',
  mineru_api_base: '',
  mineru_token: '',
  image_resolution: '2K',
  image_aspect_ratio: '16:9',
  max_description_workers: 5,
  max_image_workers: 8,
  output_language: 'zh' as OutputLanguage,
};

// 配置驱动的表单区块定义
const settingsSections: SectionConfig[] = [
  {
    title: '大模型 API 配置',
    icon: <Key size={20} />,
    fields: [
      {
        key: 'ai_provider_format',
        label: 'AI 提供商格式',
        type: 'buttons',
        description: '选择 API 请求格式，影响后端如何构造和发送请求。保存设置后生效。',
        options: [
          { value: 'openai', label: 'OpenAI 格式' },
          { value: 'gemini', label: 'Gemini 格式' },
        ],
      },
      {
        key: 'api_base_url',
        label: 'API Base URL',
        type: 'text',
        placeholder: 'https://api.example.com',
        description: '设置大模型提供商 API 的基础 URL',
      },
      {
        key: 'api_key',
        label: 'API Key',
        type: 'password',
        placeholder: '输入新的 API Key',
        sensitiveField: true,
        lengthKey: 'api_key_length',
        description: '留空则保持当前设置不变，输入新值则更新',
      },
    ],
  },
  {
    title: '模型配置',
    icon: <FileText size={20} />,
    fields: [
      {
        key: 'text_model',
        label: '文本大模型',
        type: 'text',
        placeholder: '留空使用环境变量配置 (如: gemini-2.0-flash-exp)',
        description: '用于生成大纲、描述等文本内容的模型名称',
      },
      {
        key: 'image_model',
        label: '图像生成模型',
        type: 'text',
        placeholder: '留空使用环境变量配置 (如: imagen-3.0-generate-001)',
        description: '用于生成页面图片的模型名称',
      },
      {
        key: 'image_caption_model',
        label: '图片识别模型',
        type: 'text',
        placeholder: '留空使用环境变量配置 (如: gemini-2.0-flash-exp)',
        description: '用于识别参考文件中的图片并生成描述',
      },
    ],
  },
  {
    title: 'MinerU 配置',
    icon: <FileText size={20} />,
    fields: [
      {
        key: 'mineru_api_base',
        label: 'MinerU API Base',
        type: 'text',
        placeholder: '留空使用环境变量配置 (如: https://mineru.net)',
        description: 'MinerU 服务地址，用于解析参考文件',
      },
      {
        key: 'mineru_token',
        label: 'MinerU Token',
        type: 'password',
        placeholder: '输入新的 MinerU Token',
        sensitiveField: true,
        lengthKey: 'mineru_token_length',
        description: '留空则保持当前设置不变，输入新值则更新',
      },
    ],
  },
  {
    title: '图像生成配置',
    icon: <Image size={20} />,
    fields: [
      {
        key: 'image_resolution',
        label: '图像清晰度（某些OpenAI格式中转调整该值无效）',
        type: 'select',
        description: '更高的清晰度会生成更详细的图像，但需要更长时间',
        options: [
          { value: '1K', label: '1K (1024px)' },
          { value: '2K', label: '2K (2048px)' },
          { value: '4K', label: '4K (4096px)' },
        ],
      },
    ],
  },
  {
    title: '性能配置',
    icon: <Zap size={20} />,
    fields: [
      {
        key: 'max_description_workers',
        label: '描述生成最大并发数',
        type: 'number',
        min: 1,
        max: 20,
        description: '同时生成描述的最大工作线程数 (1-20)，越大速度越快',
      },
      {
        key: 'max_image_workers',
        label: '图像生成最大并发数',
        type: 'number',
        min: 1,
        max: 20,
        description: '同时生成图像的最大工作线程数 (1-20)，越大速度越快',
      },
    ],
  },
  {
    title: '输出语言设置',
    icon: <Globe size={20} />,
    fields: [
      {
        key: 'output_language',
        label: '默认输出语言',
        type: 'buttons',
        description: 'AI 生成内容时使用的默认语言',
        options: OUTPUT_LANGUAGE_OPTIONS,
      },
    ],
  },
];

export const Settings: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();
  const { user } = useAuthStore();

  const [activeTab, setActiveTab] = useState<'settings' | 'account'>(
    searchParams.get('tab') === 'account' ? 'account' : 'settings'
  );
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState(initialFormData);

  // 密码修改表单
  const [passwordForm, setPasswordForm] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });

  // 充值码兑换
  const [redeemCode, setRedeemCode] = useState('');
  const [isRedeeming, setIsRedeeming] = useState(false);

  // 处理 URL 参数变化
  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'account') {
      setActiveTab('account');
    } else {
      setActiveTab('settings');
    }
  }, [searchParams]);

  const handleTabChange = (tab: 'settings' | 'account') => {
    setActiveTab(tab);
    if (tab === 'account') {
      setSearchParams({ tab: 'account' });
    } else {
      setSearchParams({});
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setIsLoading(true);
    try {
      const response = await api.getSettings();
      if (response.data) {
        setSettings(response.data);
        setFormData({
          ai_provider_format: response.data.ai_provider_format || 'gemini',
          api_base_url: response.data.api_base_url || '',
          api_key: '',
          image_resolution: response.data.image_resolution || '2K',
          image_aspect_ratio: response.data.image_aspect_ratio || '16:9',
          max_description_workers: response.data.max_description_workers || 5,
          max_image_workers: response.data.max_image_workers || 8,
          text_model: response.data.text_model || '',
          image_model: response.data.image_model || '',
          mineru_api_base: response.data.mineru_api_base || '',
          mineru_token: '',
          image_caption_model: response.data.image_caption_model || '',
          output_language: response.data.output_language || 'zh',
        });
      }
    } catch (error: any) {
      console.error('加载设置失败:', error);
      show({
        message: '加载设置失败: ' + (error?.message || '未知错误'),
        type: 'error'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const { api_key, mineru_token, ...otherData } = formData;
      const payload: Parameters<typeof api.updateSettings>[0] = {
        ...otherData,
      };

      if (api_key) {
        payload.api_key = api_key;
      }

      if (mineru_token) {
        payload.mineru_token = mineru_token;
      }

      const response = await api.updateSettings(payload);
      if (response.data) {
        setSettings(response.data);
        show({ message: '设置保存成功', type: 'success' });
        setFormData(prev => ({ ...prev, api_key: '', mineru_token: '' }));
      }
    } catch (error: any) {
      console.error('保存设置失败:', error);
      show({
        message: '保存设置失败: ' + (error?.response?.data?.error?.message || error?.message || '未知错误'),
        type: 'error'
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    confirm(
      '将把大模型、图像生成和并发等所有配置恢复为环境默认值，已保存的自定义设置将丢失，确定继续吗？',
      async () => {
        setIsSaving(true);
        try {
          const response = await api.resetSettings();
          if (response.data) {
            setSettings(response.data);
            setFormData({
              ai_provider_format: response.data.ai_provider_format || 'gemini',
              api_base_url: response.data.api_base_url || '',
              api_key: '',
              image_resolution: response.data.image_resolution || '2K',
              image_aspect_ratio: response.data.image_aspect_ratio || '16:9',
              max_description_workers: response.data.max_description_workers || 5,
              max_image_workers: response.data.max_image_workers || 8,
              text_model: response.data.text_model || '',
              image_model: response.data.image_model || '',
              mineru_api_base: response.data.mineru_api_base || '',
              mineru_token: '',
              image_caption_model: response.data.image_caption_model || '',
              output_language: response.data.output_language || 'zh',
            });
            show({ message: '设置已重置', type: 'success' });
          }
        } catch (error: any) {
          console.error('重置设置失败:', error);
          show({
            message: '重置设置失败: ' + (error?.message || '未知错误'),
            type: 'error'
          });
        } finally {
          setIsSaving(false);
        }
      },
      {
        title: '确认重置为默认配置',
        confirmText: '确定重置',
        cancelText: '取消',
        variant: 'warning',
      }
    );
  };

  const handlePasswordChange = async () => {
    if (!passwordForm.old_password || !passwordForm.new_password) {
      show({ message: '请填写完整的密码信息', type: 'error' });
      return;
    }

    if (passwordForm.new_password.length < 6) {
      show({ message: '新密码长度至少6个字符', type: 'error' });
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      show({ message: '两次输入的密码不一致', type: 'error' });
      return;
    }

    setIsSaving(true);
    try {
      await api.changePassword(passwordForm.old_password, passwordForm.new_password);
      show({ message: '密码修改成功', type: 'success' });
      setPasswordForm({ old_password: '', new_password: '', confirm_password: '' });
    } catch (error: any) {
      show({
        message: error?.response?.data?.error || '密码修改失败',
        type: 'error'
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRedeemCode = async () => {
    if (!redeemCode.trim()) {
      show({ message: '请输入充值码', type: 'error' });
      return;
    }

    setIsRedeeming(true);
    try {
      const response = await api.redeemCode(redeemCode.trim());
      if (response.success && response.data) {
        show({ message: response.data.message, type: 'success' });
        setRedeemCode('');
        // 更新用户信息
        const { updateUser } = useAuthStore.getState();
        updateUser({
          tier: response.data.tier as 'free' | 'premium',
          is_premium_active: response.data.is_premium_active,
          premium_expires_at: response.data.premium_expires_at,
        });
      }
    } catch (error: any) {
      show({
        message: error?.response?.data?.error?.message || error?.response?.data?.error || '兑换失败',
        type: 'error'
      });
    } finally {
      setIsRedeeming(false);
    }
  };

  const handleFieldChange = (key: string, value: any) => {
    setFormData(prev => ({ ...prev, [key]: value }));
  };

  const renderField = (field: FieldConfig) => {
    const value = formData[field.key];

    if (field.type === 'buttons' && field.options) {
      return (
        <div key={field.key}>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {field.label}
          </label>
          <div className="flex flex-wrap gap-2">
            {field.options.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => handleFieldChange(field.key, option.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  value === option.value
                    ? option.value === 'openai'
                      ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white shadow-md'
                      : 'bg-gradient-to-r from-emerald-500 to-green-600 text-white shadow-md'
                    : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          {field.description && (
            <p className="mt-1 text-xs text-gray-500">{field.description}</p>
          )}
        </div>
      );
    }

    if (field.type === 'select' && field.options) {
      return (
        <div key={field.key}>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {field.label}
          </label>
          <select
            value={value as string}
            onChange={(e) => handleFieldChange(field.key, e.target.value)}
            className="w-full h-10 px-4 rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-banana-500 focus:border-transparent"
          >
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {field.description && (
            <p className="mt-1 text-sm text-gray-500">{field.description}</p>
          )}
        </div>
      );
    }

    // text, password, number 类型
    const placeholder = field.sensitiveField && settings && field.lengthKey
      ? `已设置（长度: ${settings[field.lengthKey]}）`
      : field.placeholder || '';

    return (
      <div key={field.key}>
        <Input
          label={field.label}
          type={field.type === 'number' ? 'number' : field.type}
          placeholder={placeholder}
          value={value as string | number}
          onChange={(e) => {
            const newValue = field.type === 'number' 
              ? parseInt(e.target.value) || (field.min ?? 0)
              : e.target.value;
            handleFieldChange(field.key, newValue);
          }}
          min={field.min}
          max={field.max}
        />
        {field.description && (
          <p className="mt-1 text-sm text-gray-500">{field.description}</p>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-banana-50 to-yellow-50 flex items-center justify-center">
        <Loading text="加载设置中..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-banana-50 to-yellow-50">
      <ToastContainer />
      {ConfirmDialog}

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Card className="p-6 md:p-8">
          <div className="space-y-8">
            {/* 顶部标题 */}
            <div className="flex items-center justify-between pb-6 border-b border-gray-200">
              <div className="flex items-center">
                <Button
                  variant="secondary"
                  icon={<Home size={18} />}
                  onClick={() => navigate('/')}
                  className="mr-4"
                >
                  返回首页
                </Button>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">设置</h1>
                  <p className="text-sm text-gray-500 mt-1">
                    管理账户和系统配置
                  </p>
                </div>
              </div>
              <UserMenu />
            </div>

            {/* 标签页导航 */}
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => handleTabChange('settings')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'settings'
                    ? 'border-banana-500 text-banana-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Key size={16} className="inline mr-2" />
                系统设置
              </button>
              <button
                onClick={() => handleTabChange('account')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'account'
                    ? 'border-banana-500 text-banana-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <User size={16} className="inline mr-2" />
                账户信息
              </button>
            </div>

            {/* 系统设置内容 */}
            {activeTab === 'settings' && (
              <>
                <div className="space-y-8">
                  {settingsSections.map((section) => (
                    <div key={section.title}>
                      <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                        {section.icon}
                        <span className="ml-2">{section.title}</span>
                      </h2>
                      <div className="space-y-4">
                        {section.fields.map((field) => renderField(field))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* 操作按钮 */}
                <div className="flex items-center justify-between pt-4 border-t border-gray-200">
                  <Button
                    variant="secondary"
                    icon={<RotateCcw size={18} />}
                    onClick={handleReset}
                    disabled={isSaving}
                  >
                    重置为默认配置
                  </Button>
                  <Button
                    variant="primary"
                    icon={<Save size={18} />}
                    onClick={handleSave}
                    loading={isSaving}
                  >
                    {isSaving ? '保存中...' : '保存设置'}
                  </Button>
                </div>
              </>
            )}

            {/* 账户信息内容 */}
            {activeTab === 'account' && user && (
              <div className="space-y-8">
                {/* 用户信息 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                    <User size={20} />
                    <span className="ml-2">个人信息</span>
                  </h2>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">用户名</span>
                      <span className="font-medium">{user.username}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">邮箱</span>
                      <span className="font-medium">{user.email || '未设置'}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">角色</span>
                      <span className="font-medium">
                        {user.role === 'admin' ? '管理员' : '普通用户'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">注册时间</span>
                      <span className="font-medium">
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 会员状态 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                    <Crown size={20} />
                    <span className="ml-2">会员状态</span>
                  </h2>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">当前等级</span>
                      <span className={`font-medium flex items-center gap-1 ${
                        user.tier === 'premium' ? 'text-yellow-600' : 'text-gray-600'
                      }`}>
                        {user.tier === 'premium' && <Crown size={16} />}
                        {user.tier === 'premium' ? '高级会员' : '免费用户'}
                      </span>
                    </div>
                    {user.tier === 'premium' && (
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">到期时间</span>
                        <span className="font-medium">
                          {user.premium_expires_at
                            ? new Date(user.premium_expires_at).toLocaleDateString()
                            : '永久'}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">会员状态</span>
                      <span className={`font-medium ${
                        user.is_premium_active ? 'text-green-600' : 'text-gray-500'
                      }`}>
                        {user.is_premium_active ? '有效' : '未激活'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 修改密码 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                    <Lock size={20} />
                    <span className="ml-2">修改密码</span>
                  </h2>
                  <div className="space-y-4">
                    <Input
                      label="当前密码"
                      type="password"
                      placeholder="请输入当前密码"
                      value={passwordForm.old_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, old_password: e.target.value }))}
                    />
                    <Input
                      label="新密码"
                      type="password"
                      placeholder="请输入新密码（至少6个字符）"
                      value={passwordForm.new_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, new_password: e.target.value }))}
                    />
                    <Input
                      label="确认新密码"
                      type="password"
                      placeholder="请再次输入新密码"
                      value={passwordForm.confirm_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                    />
                    <div className="pt-2">
                      <Button
                        variant="primary"
                        icon={<Save size={18} />}
                        onClick={handlePasswordChange}
                        loading={isSaving}
                      >
                        {isSaving ? '保存中...' : '修改密码'}
                      </Button>
                    </div>
                  </div>
                </div>

                {/* 充值码兑换 */}
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                    <Gift size={20} />
                    <span className="ml-2">充值码兑换</span>
                  </h2>
                  <div className="space-y-4">
                    <Input
                      label="充值码"
                      type="text"
                      placeholder="请输入充值码（如: ABCD1234EFGH5678）"
                      value={redeemCode}
                      onChange={(e) => setRedeemCode(e.target.value.toUpperCase())}
                    />
                    <p className="text-sm text-gray-500">
                      输入有效的充值码可激活或延长您的高级会员资格
                    </p>
                    <div className="pt-2">
                      <Button
                        variant="primary"
                        icon={<Gift size={18} />}
                        onClick={handleRedeemCode}
                        loading={isRedeeming}
                      >
                        {isRedeeming ? '兑换中...' : '立即兑换'}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};
