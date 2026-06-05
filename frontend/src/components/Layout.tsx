import { useEffect, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { api, clearToken } from '../lib/api';

interface UserInfo {
  name: string;
  email: string;
  is_admin: boolean;
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api.me().then(setUser).catch(() => {
      clearToken();
      navigate('/login');
    });
  }, [navigate]);

  // Block non-admins from admin routes (A11 from audit)
  useEffect(() => {
    if (user && !user.is_admin && location.pathname.startsWith('/admin')) {
      navigate('/', { replace: true });
    }
  }, [user, location.pathname, navigate]);

  // Close mobile drawer on route change
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    clearToken();
    navigate('/login');
  };

  const closeDrawer = () => setDrawerOpen(false);

  return (
    <div className="min-h-screen md:flex">
      {/* Mobile topbar */}
      <header className="md:hidden sticky top-0 z-30 flex items-center justify-between bg-white border-b border-[var(--nora-pink-light)] px-4 h-14">
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Menü öffnen"
          className="p-2 -ml-2 rounded-md text-gray-700 hover:bg-[var(--nora-pink-light)]"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <img src="/nw-logo.webp" alt="NW" className="w-7 h-7" />
          <span className="text-sm font-semibold text-gray-800">Nora Weweler</span>
        </div>
        <div className="w-9" aria-hidden />
      </header>

      {/* Backdrop */}
      {drawerOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/40 z-40"
          onClick={closeDrawer}
          aria-hidden
        />
      )}

      {/* Sidebar / Drawer */}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-50
          w-72 md:w-64 bg-white border-r border-[var(--nora-pink-light)]
          flex flex-col shrink-0
          transform transition-transform duration-200 ease-out
          ${drawerOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0
        `}
      >
        <div className="p-5 border-b border-[var(--nora-pink-light)] flex items-start justify-between">
          <div className="flex items-center gap-3">
            <img src="/nw-logo.webp" alt="NW" className="w-10 h-10" />
            <div>
              <h1 className="text-sm font-semibold text-gray-800 leading-tight">Nora Weweler</h1>
              <p className="text-xs text-gray-400 leading-tight">Ernährungsberatung · Kurse</p>
            </div>
          </div>
          <button
            type="button"
            onClick={closeDrawer}
            aria-label="Menü schließen"
            className="md:hidden p-1 -mr-1 rounded text-gray-500 hover:bg-[var(--nora-pink-light)]"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {user && (
          <div className="px-5 py-3 border-b border-[var(--nora-pink-light)] flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-[var(--nora-pink-light)] flex items-center justify-center text-xs font-semibold text-[var(--nora-pink-dark)]">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm text-gray-600">{user.name}</span>
          </div>
        )}

        <nav className="flex-1 p-4 overflow-y-auto">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Inhalte
          </p>
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            Meine Kurse
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Einstellungen
          </Link>

          {user?.is_admin && (
            <>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-6 mb-3">
                Admin
              </p>
              <Link
                to="/admin"
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Dashboard
              </Link>
              <Link
                to="/admin/courses"
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                Kurse verwalten
              </Link>
              <Link
                to="/admin/live-calls"
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Live-Call-Importe
              </Link>
              <Link
                to="/admin/users"
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                Nutzer verwalten
              </Link>
              <Link
                to="/admin/integrations"
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-[var(--nora-pink-light)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Integrationen
              </Link>
            </>
          )}
        </nav>

        <div className="p-4 border-t border-[var(--nora-pink-light)]">
          <button
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Abmelden
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 md:overflow-auto min-w-0">
        {children}
      </main>
    </div>
  );
}
