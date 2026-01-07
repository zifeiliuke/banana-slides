import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { LogIn, UserPlus, Eye, EyeOff, Gift } from 'lucide-react';
import { Button, Input, useToast } from '@/components/shared';
import { useAuthStore } from '@/store/useAuthStore';
import { apiClient } from '@/api/client';
import { getApiErrorMessage } from '@/utils/apiError';

type AuthMode = 'login' | 'register';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { login, register, isLoading, error, setError, isAuthenticated } = useAuthStore();
  const { show, ToastContainer } = useToast();

  const [mode, setMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [requireEmailVerification, setRequireEmailVerification] = useState(false);
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [sendCooldownSeconds, setSendCooldownSeconds] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // 从 URL 获取邀请码（支持 ref 和 referral_code 参数）
  const referralCode = useMemo(() => {
    return searchParams.get('ref') || searchParams.get('referral_code') || '';
  }, [searchParams]);

  // 如果有邀请码，自动切换到注册模式
  useEffect(() => {
    if (referralCode) {
      setMode('register');
    }
  }, [referralCode]);

  useEffect(() => {
    let timer: number | undefined;
    if (sendCooldownSeconds > 0) {
      timer = window.setInterval(() => {
        setSendCooldownSeconds((prev) => Math.max(0, prev - 1));
      }, 1000);
    }
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, [sendCooldownSeconds]);

  // 获取注册设置（例如是否要求邮箱验证）
  useEffect(() => {
    const load = async () => {
      try {
        const response = await apiClient.get('/api/auth/registration-settings');
        if (response.data?.success) {
          setRequireEmailVerification(!!response.data.data?.require_email_verification);
        }
      } catch {
        // 忽略：加载失败时默认不强制邮箱验证，提交注册时后端仍会校验并返回错误
      }
    };
    void load();
  }, []);

  // 如果已登录，重定向到首页
  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  // 显示错误
  useEffect(() => {
    if (error) {
      show({ message: error, type: 'error' });
      setError(null);
    }
  }, [error, show, setError]);

  const isValidEmail = (value: string): boolean => {
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return emailPattern.test(value);
  };

  const validateForm = (): boolean => {
    setFormError(null);

    if (!username.trim()) {
      setFormError('请输入用户名');
      return false;
    }

    if (username.length < 3 || username.length > 50) {
      setFormError('用户名长度需要在3-50个字符之间');
      return false;
    }

    if (!password) {
      setFormError('请输入密码');
      return false;
    }

    if (password.length < 6) {
      setFormError('密码长度至少6个字符');
      return false;
    }

    if (mode === 'register') {
      const trimmedEmail = email.trim().toLowerCase();
      if (requireEmailVerification && !trimmedEmail) {
        setFormError('请输入邮箱');
        return false;
      }
      if (trimmedEmail && !isValidEmail(trimmedEmail)) {
        setFormError('邮箱格式不正确');
        return false;
      }
      if (requireEmailVerification && !verificationCode.trim()) {
        setFormError('请输入验证码');
        return false;
      }

      if (password !== confirmPassword) {
        setFormError('两次输入的密码不一致');
        return false;
      }
    }

    return true;
  };

  const handleSendVerificationCode = async () => {
    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) {
      show({ message: '请输入邮箱', type: 'error' });
      return;
    }
    if (!isValidEmail(trimmedEmail)) {
      show({ message: '邮箱格式不正确', type: 'error' });
      return;
    }

    setIsSendingCode(true);
    try {
      const response = await apiClient.post('/api/auth/send-verification', { email: trimmedEmail });
      if (response.data?.success) {
        show({ message: response.data?.message || '验证码已发送，请查收邮件', type: 'success' });
        setSendCooldownSeconds(60);
      } else {
        show({ message: response.data?.message || '发送失败，请稍后重试', type: 'error' });
      }
    } catch (error: any) {
      const message = getApiErrorMessage(error, '发送失败，请稍后重试');
      show({ message, type: 'error' });
      const match = message.match(/(\d+)\s*秒/);
      if (match) setSendCooldownSeconds(parseInt(match[1], 10));
    } finally {
      setIsSendingCode(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    let success = false;
    if (mode === 'login') {
      success = await login({ username, password });
    } else {
      success = await register({
        username,
        password,
        email: email.trim() ? email.trim().toLowerCase() : undefined,
        verification_code: requireEmailVerification ? verificationCode.trim() : undefined,
        referral_code: referralCode || undefined,
      });
    }

    if (success) {
      show({
        message: mode === 'login' ? '登录成功' : '注册成功',
        type: 'success'
      });
      const from = (location.state as any)?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  };

  const toggleMode = () => {
    setMode(mode === 'login' ? 'register' : 'login');
    setFormError(null);
    setConfirmPassword('');
    setEmail('');
    setVerificationCode('');
    setSendCooldownSeconds(0);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-banana-50 via-white to-banana-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-banana-500 to-banana-600 rounded-2xl shadow-lg mb-4">
            <span className="text-3xl">🍌</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Banana Slides</h1>
          <p className="text-gray-600 mt-1">AI 驱动的 PPT 生成工具</p>
        </div>

        {/* 登录/注册卡片 */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-xl font-semibold text-center mb-6">
            {mode === 'login' ? '登录账户' : '创建账户'}
          </h2>

          {/* 邀请码提示 */}
          {mode === 'register' && referralCode && (
            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 mb-4">
              <Gift size={18} className="text-green-500 shrink-0" />
              <span>
                使用邀请码 <span className="font-mono font-semibold">{referralCode}</span> 注册，将获得额外积分奖励！
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="用户名"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoComplete="username"
              disabled={isLoading}
            />

            {mode === 'register' && (
              <Input
                label={requireEmailVerification ? '邮箱' : '邮箱（可选）'}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="请输入邮箱"
                autoComplete="email"
                disabled={isLoading}
              />
            )}

            {mode === 'register' && requireEmailVerification && (
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <Input
                    label="验证码"
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="请输入验证码"
                    disabled={isLoading}
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  className="shrink-0"
                  disabled={isLoading || isSendingCode || sendCooldownSeconds > 0}
                  onClick={handleSendVerificationCode}
                >
                  {sendCooldownSeconds > 0 ? `${sendCooldownSeconds}s` : '发送验证码'}
                </Button>
              </div>
            )}

            <div className="relative">
              <Input
                label="密码"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                disabled={isLoading}
              />
              <button
                type="button"
                className="absolute right-3 top-9 text-gray-400 hover:text-gray-600"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>

            {mode === 'register' && (
              <Input
                label="确认密码"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入密码"
                autoComplete="new-password"
                disabled={isLoading}
              />
            )}

            {formError && (
              <div className="text-sm text-red-500 text-center">
                {formError}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={isLoading}
              icon={mode === 'login' ? <LogIn size={20} /> : <UserPlus size={20} />}
            >
              {mode === 'login' ? '登录' : '注册'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-gray-600">
              {mode === 'login' ? '还没有账户？' : '已有账户？'}
            </span>
            <button
              type="button"
              className="ml-2 text-banana-600 hover:text-banana-700 font-medium"
              onClick={toggleMode}
              disabled={isLoading}
            >
              {mode === 'login' ? '立即注册' : '立即登录'}
            </button>
          </div>
        </div>

        {/* 版权信息 */}
        <p className="text-center text-gray-500 text-sm mt-6">
          © 2024 Banana Slides. All rights reserved.
        </p>
      </div>

      <ToastContainer />
    </div>
  );
};
