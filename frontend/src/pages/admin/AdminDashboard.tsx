import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';

interface CourseStats {
  course_id: string;
  title: string;
  enrolled: number;
  total_lessons: number;
  avg_progress: number;
  completed_count: number;
}

interface InactiveUser {
  id: string;
  name: string;
  email: string;
  last_active: string | null;
  completed_lessons: number;
  total_lessons: number;
  progress_percent: number;
}

interface DashboardData {
  total_users: number;
  active_users_7d: number;
  new_users_30d: number;
  total_completed_courses: number;
  courses: CourseStats[];
  inactive_users: InactiveUser[];
}

export default function AdminDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.getDashboardStats()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!data) return <div className="p-8 text-gray-500">Fehler beim Laden.</div>;

  const formatDate = (iso: string | null) => {
    if (!iso) return 'Nie aktiv';
    const d = new Date(iso);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Heute';
    if (diffDays === 1) return 'Gestern';
    if (diffDays < 7) return `Vor ${diffDays} Tagen`;
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Teilnehmer"
          value={data.total_users}
          sub={`${data.new_users_30d} neu (30 Tage)`}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
        <KpiCard
          label="Aktiv (7 Tage)"
          value={data.active_users_7d}
          sub={data.total_users > 0 ? `${Math.round((data.active_users_7d / data.total_users) * 100)}% der Teilnehmer` : '—'}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <KpiCard
          label="Kurs-Abschlüsse"
          value={data.total_completed_courses}
          sub="100% abgeschlossen"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <KpiCard
          label="Inaktiv (14+ Tage)"
          value={data.inactive_users.length}
          sub={data.total_users > 0 ? `${Math.round((data.inactive_users.length / data.total_users) * 100)}% der Teilnehmer` : '—'}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
          warn={data.inactive_users.length > 0}
        />
      </div>

      {/* Course Stats */}
      {data.courses.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Kurse</h2>
          <div className="grid gap-4">
            {data.courses.map((c) => (
              <div key={c.course_id} className="bg-white rounded-xl border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-800">{c.title}</h3>
                  <div className="flex gap-4 text-sm text-gray-500">
                    <span>{c.enrolled} Teilnehmer</span>
                    <span>{c.total_lessons} Lektionen</span>
                    <span>{c.completed_count} Abschlüsse</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${c.avg_progress}%`,
                        background: 'linear-gradient(90deg, var(--nora-pink), var(--nora-berry))',
                      }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-600 w-12 text-right">
                    {c.avg_progress}%
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">Durchschnittlicher Fortschritt</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inactive Users */}
      {data.inactive_users.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Inaktive Teilnehmer
            <span className="ml-2 text-sm font-normal text-gray-400">seit 14+ Tagen keine Aktivität</span>
          </h2>
          <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Name</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">E-Mail</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Letzte Aktivität</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Fortschritt</th>
                </tr>
              </thead>
              <tbody>
                {data.inactive_users.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate('/admin/users')}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-500">
                          {u.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium text-gray-700">{u.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-500">{u.email}</td>
                    <td className="px-5 py-3">
                      <span className={`text-sm ${!u.last_active ? 'text-red-400 font-medium' : 'text-gray-500'}`}>
                        {formatDate(u.last_active)}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-20 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${u.progress_percent}%`,
                              background: u.progress_percent > 50
                                ? 'linear-gradient(90deg, var(--nora-pink), var(--nora-berry))'
                                : '#d1d5db',
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">{u.progress_percent}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.inactive_users.length === 0 && data.total_users > 0 && (
        <div className="bg-green-50 border border-green-100 rounded-xl p-5 text-center">
          <p className="text-green-700 font-medium">Alle Teilnehmer sind aktiv!</p>
          <p className="text-green-600 text-sm mt-1">Keine inaktiven Nutzer in den letzten 14 Tagen.</p>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  icon,
  warn = false,
}: {
  label: string;
  value: number;
  sub: string;
  icon: React.ReactNode;
  warn?: boolean;
}) {
  return (
    <div className={`bg-white rounded-xl border p-5 ${warn ? 'border-amber-200' : 'border-gray-100'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-500">{label}</span>
        <div className={`${warn ? 'text-amber-500' : 'text-gray-400'}`}>{icon}</div>
      </div>
      <p className={`text-3xl font-bold ${warn ? 'text-amber-600' : 'text-gray-800'}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}
