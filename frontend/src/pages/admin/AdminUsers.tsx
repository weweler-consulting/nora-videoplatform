import { useEffect, useState } from 'react';
import { api, type UserWithEnrollments, type CourseListItem } from '../../lib/api';

export default function AdminUsers() {
  const [users, setUsers] = useState<UserWithEnrollments[]>([]);
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);

  // Invite form
  const [invEmail, setInvEmail] = useState('');
  const [invName, setInvName] = useState('');
  const [invPassword, setInvPassword] = useState('');
  const [invCourseId, setInvCourseId] = useState('');
  const [invError, setInvError] = useState('');
  const [invSendEmail, setInvSendEmail] = useState(false);
  const [enrollingUserId, setEnrollingUserId] = useState<string | null>(null);
  const [inviteResult, setInviteResult] = useState<{ name: string; email: string; password: string; courseTitle: string; emailSent: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const [filterCourseId, setFilterCourseId] = useState('');

  const load = () => {
    Promise.all([api.getUsers(), api.getAllCourses()])
      .then(([u, c]) => { setUsers(u); setCourses(c); })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInvError('');
    if (!invEmail.trim() || !invName.trim() || !invCourseId) {
      setInvError('Bitte alle Felder ausfuellen.');
      return;
    }
    const password = invPassword || 'changeme123';
    const courseTitle = courses.find((c) => c.id === invCourseId)?.title || '';
    try {
      const result = await api.inviteUser({
        email: invEmail,
        name: invName,
        course_id: invCourseId,
        password: invPassword || undefined,
        send_email: invSendEmail,
      });
      setInviteResult({ name: invName, email: invEmail, password, courseTitle, emailSent: result.email_sent });
      setCopied(false);
      setInvEmail('');
      setInvName('');
      setInvPassword('');
      setInvCourseId('');
      setInvSendEmail(false);
      setShowInvite(false);
      load();
    } catch (err: any) {
      setInvError(err.message || 'Fehler beim Einladen.');
    }
  };

  const handleEnrollUser = async (userId: string, courseId: string) => {
    try {
      await api.enrollUser(userId, courseId);
      setEnrollingUserId(null);
      load();
    } catch (err: any) {
      alert(err.message || 'Fehler beim Zuordnen.');
    }
  };

  const handleRemoveEnrollment = async (enrollmentId: string, userName: string, courseTitle: string) => {
    if (!confirm(`${userName} aus "${courseTitle}" entfernen?`)) return;
    await api.removeEnrollment(enrollmentId);
    load();
  };

  const handleToggleActive = async (userId: string) => {
    try {
      await api.toggleUserActive(userId);
      load();
    } catch (err: any) {
      alert(err.message || 'Fehler.');
    }
  };

  const handleDeleteUser = async (userId: string, name: string) => {
    if (!confirm(`Nutzer "${name}" wirklich löschen? Alle Daten gehen verloren.`)) return;
    try {
      await api.deleteUser(userId);
      load();
    } catch (err: any) {
      alert(err.message || 'Fehler beim Löschen.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-[var(--nora-coco)] border-t-[var(--nora-soy)]" />
      </div>
    );
  }

  const filteredUsers = filterCourseId
    ? users.filter((u) => u.enrollments.some((e) => e.course_id === filterCourseId))
    : users;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-bold text-[var(--nora-soy)]">Teilnehmer</h2>
        <button
          onClick={() => setShowInvite(!showInvite)}
          className="px-4 py-1.5 text-[13px] font-medium bg-[var(--nora-berry)] text-white rounded-lg hover:bg-[var(--nora-berry-dark)] transition-colors"
        >
          + Einladen
        </button>
      </div>

      {/* Invite Form */}
      {showInvite && (
        <form onSubmit={handleInvite} className="bg-white rounded-xl border border-[var(--nora-coco)] p-5 mb-5 space-y-3">
          {invError && (
            <div className="bg-red-50 text-red-600 text-[13px] px-3 py-2 rounded-lg">{invError}</div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[13px] font-medium text-[var(--nora-soy)] mb-1">Name</label>
              <input
                type="text"
                value={invName}
                onChange={(e) => setInvName(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[var(--nora-coco)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-berry)] focus:border-transparent"
                placeholder="Vorname Nachname"
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-[var(--nora-soy)] mb-1">E-Mail</label>
              <input
                type="email"
                value={invEmail}
                onChange={(e) => setInvEmail(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[var(--nora-coco)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-berry)] focus:border-transparent"
                placeholder="nutzer@email.de"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[13px] font-medium text-[var(--nora-soy)] mb-1">Passwort</label>
              <input
                type="text"
                value={invPassword}
                onChange={(e) => setInvPassword(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[var(--nora-coco)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-berry)] focus:border-transparent"
                placeholder="Standard: changeme123"
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-[var(--nora-soy)] mb-1">Kurs</label>
              <select
                value={invCourseId}
                onChange={(e) => setInvCourseId(e.target.value)}
                className="w-full px-3 py-2 text-[13px] border border-[var(--nora-coco)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-berry)] focus:border-transparent bg-white"
              >
                <option value="">Kurs wählen...</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center justify-between pt-1">
            <label className="flex items-center gap-2 text-[13px] text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={invSendEmail}
                onChange={(e) => setInvSendEmail(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-gray-300 text-[var(--nora-berry)] focus:ring-[var(--nora-berry)]"
              />
              Einladung per E-Mail senden
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowInvite(false)}
                className="px-3 py-1.5 text-[13px] border border-[var(--nora-coco)] rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Abbrechen
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 text-[13px] font-medium bg-[var(--nora-berry)] text-white rounded-lg hover:bg-[var(--nora-berry-dark)] transition-colors"
              >
                Einladen
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Invite Result */}
      {inviteResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-green-800">Einladung erstellt</span>
              {inviteResult.emailSent && (
                <span className="text-[11px] bg-green-200 text-green-800 px-2 py-0.5 rounded-full">E-Mail gesendet</span>
              )}
            </div>
            <button onClick={() => setInviteResult(null)} className="text-green-600 hover:text-green-800">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          <div className="bg-white rounded-lg p-3 text-[13px] text-gray-700 whitespace-pre-line font-mono leading-relaxed">
            {`Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\nLink: ${window.location.origin}/login\nE-Mail: ${inviteResult.email}\nPasswort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`}
          </div>
          <button
            onClick={() => {
              const text = `Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\nLink: ${window.location.origin}/login\nE-Mail: ${inviteResult.email}\nPasswort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`;
              navigator.clipboard.writeText(text.replace(/\\n/g, '\n'));
              setCopied(true);
            }}
            className={`mt-2 px-3 py-1.5 rounded-lg font-medium text-[13px] transition-colors ${
              copied ? 'bg-green-600 text-white' : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            {copied ? 'Kopiert!' : 'Nachricht kopieren'}
          </button>
        </div>
      )}

      {/* Table Card */}
      <div className="bg-white rounded-xl border border-[var(--nora-coco)] overflow-hidden">
        {/* Filter Bar */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-[var(--nora-coco)]">
          <select
            value={filterCourseId}
            onChange={(e) => setFilterCourseId(e.target.value)}
            className="px-3 py-1.5 text-[13px] border border-[var(--nora-coco)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-berry)] bg-white"
          >
            <option value="">Alle Kurse</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
          <span className="text-[13px] text-gray-400">
            {filteredUsers.filter((u) => !u.is_admin).length} Teilnehmer
          </span>
        </div>

        {/* Table */}
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--nora-coco)] bg-[#fafaf8]">
              <th className="text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-5 py-2.5">Name</th>
              <th className="text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-5 py-2.5">E-Mail</th>
              <th className="text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-5 py-2.5">Kurse</th>
              <th className="text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-5 py-2.5">Status</th>
              <th className="text-right text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-5 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center text-[13px] text-gray-400 py-12">
                  {filterCourseId ? 'Keine Nutzer in diesem Kurs.' : 'Noch keine Nutzer vorhanden.'}
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr key={user.id} className="border-b border-[var(--nora-coco)] last:border-b-0 hover:bg-[#fdfdf8] transition-colors">
                  {/* Name */}
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium text-[var(--nora-soy)]">{user.name}</span>
                      {user.is_admin && (
                        <span className="text-[11px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">Admin</span>
                      )}
                    </div>
                  </td>

                  {/* Email */}
                  <td className="px-5 py-2.5">
                    <span className="text-[13px] text-gray-500">{user.email}</span>
                  </td>

                  {/* Courses */}
                  <td className="px-5 py-2.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {user.enrollments.map((enr) => (
                        <span
                          key={enr.enrollment_id}
                          className="inline-flex items-center gap-1 text-[11px] bg-[var(--nora-pink-light)] text-[var(--nora-berry-dark)] px-2 py-0.5 rounded-full"
                        >
                          {enr.course_title}
                          <button
                            onClick={() => handleRemoveEnrollment(enr.enrollment_id, user.name, enr.course_title)}
                            className="hover:text-red-500 transition-colors"
                          >
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                          </button>
                        </span>
                      ))}
                      {!user.is_admin && (
                        enrollingUserId === user.id ? (
                          <select
                            autoFocus
                            className="text-[11px] border border-[var(--nora-coco)] rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-[var(--nora-berry)] bg-white"
                            value=""
                            onChange={(e) => handleEnrollUser(user.id, e.target.value)}
                            onBlur={() => setEnrollingUserId(null)}
                          >
                            <option value="">+Kurs...</option>
                            {courses
                              .filter((c) => !user.enrollments.some((enr) => enr.course_id === c.id))
                              .map((c) => (
                                <option key={c.id} value={c.id}>{c.title}</option>
                              ))}
                          </select>
                        ) : (
                          <button
                            onClick={() => setEnrollingUserId(user.id)}
                            className="text-[11px] text-gray-400 hover:text-[var(--nora-berry)] transition-colors px-1"
                            title="Kurs zuordnen"
                          >
                            +
                          </button>
                        )
                      )}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="px-5 py-2.5">
                    {!user.is_admin && (
                      <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        user.is_active
                          ? 'bg-green-50 text-green-700'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                        {user.is_active ? 'aktiv' : 'inaktiv'}
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-5 py-2.5 text-right">
                    {!user.is_admin && (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleToggleActive(user.id)}
                          className="text-[12px] text-gray-400 hover:text-[var(--nora-soy)] transition-colors px-2 py-1 rounded hover:bg-gray-50"
                        >
                          {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                        </button>
                        <button
                          onClick={() => handleDeleteUser(user.id, user.name)}
                          className="text-[12px] text-gray-400 hover:text-red-500 transition-colors px-2 py-1 rounded hover:bg-red-50"
                        >
                          Löschen
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
