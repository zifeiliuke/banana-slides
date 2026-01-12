import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Home } from './pages/Home';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { Login } from './pages/Login';
import { Admin } from './pages/Admin';
import { useProjectStore } from './store/useProjectStore';
import { useAuthStore } from './store/useAuthStore';
import { useToast } from './components/shared';
import { AuthGuard } from './components/auth';

function App() {
  const { currentProject, syncProject, error, setError } = useProjectStore();
  const { checkAuth } = useAuthStore();
  const { show, ToastContainer } = useToast();

  // 应用启动时检查认证状态
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // 恢复项目状态
  useEffect(() => {
    const savedProjectId = localStorage.getItem('currentProjectId');
    if (savedProjectId && !currentProject) {
      syncProject();
    }
  }, [currentProject, syncProject]);

  // 显示全局错误
  useEffect(() => {
    if (error) {
      show({ message: error, type: 'error' });
      setError(null);
    }
  }, [error, setError, show]);

  return (
    <BrowserRouter>
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Login />} />

        {/* 受保护的路由 */}
        <Route path="/" element={<AuthGuard><Home /></AuthGuard>} />
        <Route path="/history" element={<AuthGuard><History /></AuthGuard>} />
        <Route path="/settings" element={<AuthGuard><SettingsPage /></AuthGuard>} />
        <Route path="/admin" element={<AuthGuard requireAdmin><Admin /></AuthGuard>} />
        <Route path="/project/:projectId/outline" element={<AuthGuard><OutlineEditor /></AuthGuard>} />
        <Route path="/project/:projectId/detail" element={<AuthGuard><DetailEditor /></AuthGuard>} />
        <Route path="/project/:projectId/preview" element={<AuthGuard><SlidePreview /></AuthGuard>} />

        {/* 默认重定向 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastContainer />
    </BrowserRouter>
  );
}

export default App;
