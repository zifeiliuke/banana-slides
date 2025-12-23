import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { Loading } from '@/components/shared';

interface AuthGuardProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children, requireAdmin = false }) => {
  const location = useLocation();
  const { isAuthenticated, user, checkAuth } = useAuthStore();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const verify = async () => {
      await checkAuth();
      setIsChecking(false);
    };
    verify();
  }, [checkAuth]);

  // 正在检查认证状态
  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loading text="验证登录状态..." />
      </div>
    );
  }

  // 未登录，重定向到登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 需要管理员权限但当前用户不是管理员
  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
