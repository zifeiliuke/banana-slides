import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, LogOut, Settings, Crown, Shield, Coins } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import * as api from '@/api/endpoints';
import type { PointsBalance } from '@/types';

export const UserMenu: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuthStore();
  const [isOpen, setIsOpen] = useState(false);
  const [pointsBalance, setPointsBalance] = useState<PointsBalance | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 获取积分余额
  useEffect(() => {
    if (isAuthenticated && user) {
      api.getPointsBalance().then(res => {
        if (res.success && res.data) {
          setPointsBalance(res.data);
        }
      }).catch(() => {
        // 忽略错误
      });
    }
  }, [isAuthenticated, user]);

  if (!isAuthenticated || !user) {
    return null;
  }

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isAdmin = user.role === 'admin';
  const isPremium = user.tier === 'premium' && user.is_premium_active;
  const validPoints = pointsBalance?.valid_points ?? user.valid_points ?? 0;

  return (
    <div className="relative" ref={menuRef}>
      {/* 用户头像按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-banana-100/60 transition-all duration-200"
      >
        <div className="w-8 h-8 rounded-full bg-gradient-to-r from-banana-500 to-banana-600 flex items-center justify-center text-white font-semibold text-sm shadow-sm">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <span className="hidden md:inline text-sm font-medium text-gray-700 max-w-[100px] truncate">
          {user.username}
        </span>
        {isPremium && (
          <Crown size={14} className="text-yellow-500" />
        )}
      </button>

      {/* 下拉菜单 */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-100 py-2 z-50">
          {/* 用户信息 */}
          <div className="px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-r from-banana-500 to-banana-600 flex items-center justify-center text-white font-semibold">
                {user.username.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{user.username}</p>
                <p className="text-xs text-gray-500 flex items-center gap-1">
                  {isAdmin ? (
                    <>
                      <Shield size={12} className="text-red-400" />
                      <span>管理员</span>
                    </>
                  ) : isPremium ? (
                    <>
                      <Crown size={12} className="text-yellow-500" />
                      <span>高级会员</span>
                    </>
                  ) : (
                    <span>免费用户</span>
                  )}
                </p>
              </div>
            </div>
            {/* 积分余额 */}
            {!isAdmin && (
              <div className="mt-2 pt-2 border-t border-gray-50">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 flex items-center gap-1">
                    <Coins size={14} className="text-yellow-500" />
                    积分余额
                  </span>
                  <span className="font-semibold text-banana-600">{validPoints}</span>
                </div>
                {pointsBalance && pointsBalance.expiring_soon.points > 0 && (
                  <p className="text-xs text-orange-500 mt-1">
                    {pointsBalance.expiring_soon.points} 积分将在 {pointsBalance.expiring_soon.days} 天内过期
                  </p>
                )}
              </div>
            )}
          </div>

          {/* 菜单项 */}
          <div className="py-1">
            {user.role === 'admin' && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  navigate('/admin');
                }}
                className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3"
              >
                <Shield size={16} className="text-red-400" />
                管理后台
              </button>
            )}
            <button
              onClick={() => {
                setIsOpen(false);
                navigate('/settings');
              }}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3"
            >
              <Settings size={16} className="text-gray-400" />
              设置
            </button>
            <button
              onClick={() => {
                setIsOpen(false);
                navigate('/settings?tab=account');
              }}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-3"
            >
              <User size={16} className="text-gray-400" />
              账户信息
            </button>
          </div>

          {/* 登出 */}
          <div className="border-t border-gray-100 pt-1">
            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-3"
            >
              <LogOut size={16} className="text-red-400" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
