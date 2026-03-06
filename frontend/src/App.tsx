import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { isLoggedIn } from './lib/api';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CourseView from './pages/CourseView';
import LessonView from './pages/LessonView';
import AdminCourses from './pages/admin/AdminCourses';
import AdminCourseDetail from './pages/admin/AdminCourseDetail';
import AdminModuleDetail from './pages/admin/AdminModuleDetail';
import AdminUsers from './pages/admin/AdminUsers';
import AdminSettings from './pages/admin/AdminSettings';
import Layout from './components/Layout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/course/:courseId" element={<CourseView />} />
                  <Route path="/course/:courseId/lesson/:lessonId" element={<LessonView />} />
                  <Route path="/admin" element={<AdminCourses />} />
                  <Route path="/admin/course/:courseId" element={<AdminCourseDetail />} />
                  <Route path="/admin/course/:courseId/module/:moduleId" element={<AdminModuleDetail />} />
                  <Route path="/admin/users" element={<AdminUsers />} />
                  <Route path="/settings" element={<AdminSettings />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
