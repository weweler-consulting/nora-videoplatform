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
    if (!confirm(`Nutzer "${name}" wirklich loschen? Alle Daten gehen verloren.`)) return;
    try {
      await api.deleteUser(userId);
      load();
    } catch (err: any) {
      alert(err.message || 'Fehler beim Loschen.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Nutzer verwalten</h2>
        <button
          onClick={() => setShowInvite(!showInvite)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Nutzer einladen
        </button>
      </div>

      {/* Course filter */}
      <div className="flex items-center gap-3 mb-6">
        <label className="text-sm text-gray-500">Filtern nach Kurs:</label>
        <select
          value={filterCourseId}
          onChange={(e) => setFilterCourseId(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] bg-white"
        >
          <option value="">Alle Nutzer</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
        {filterCourseId && (
          <span className="text-sm text-gray-400">
            {users.filter((u) => !u.is_admin && u.enrollments.some((e) => e.course_id === filterCourseId)).length} Teilnehmer
          </span>
        )}
      </div>

      {showInvite && (
        <form onSubmit={handleInvite} className="bg-white rounded-2xl p-6 mb-6 shadow-sm space-y-4">
          {invError && (
            <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{invError}</div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={invName}
                onChange={(e) => setInvName(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
                placeholder="Vorname Nachname"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
              <input
                type="email"
                value={invEmail}
                onChange={(e) => setInvEmail(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
                placeholder="nutzer@email.de"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Passwort</label>
              <input
                type="text"
                value={invPassword}
                onChange={(e) => setInvPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
                placeholder="Standard: changeme123"
              />
              <p className="text-xs text-gray-400 mt-1">Leer lassen fur Standard-Passwort</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Kurs zuweisen</label>
              <select
                value={invCourseId}
                onChange={(e) => setInvCourseId(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent bg-white"
              >
                <option value="">Kurs wahlen...</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={invSendEmail}
                onChange={(e) => setInvSendEmail(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-[var(--nora-pink)] focus:ring-[var(--nora-pink)]"
              />
              Einladung per E-Mail senden
            </label>
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
            >
              Einladen
            </button>
            <button
              type="button"
              onClick={() => setShowInvite(false)}
              className="px-5 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </form>
      )}

      {inviteResult && (
        <div className="bg-green-50 border border-green-200 rounded-2xl p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <h3 className="font-semibold text-green-800">Einladung erstellt</h3>
              {inviteResult.emailSent && (
                <span className="text-xs bg-green-200 text-green-800 px-2 py-0.5 rounded-full">E-Mail gesendet</span>
              )}
            </div>
            <button
              onClick={() => setInviteResult(null)}
              className="text-green-600 hover:text-green-800 transition-colors"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          <div className="bg-white rounded-lg p-4 text-sm text-gray-700 whitespace-pre-line font-mono leading-relaxed">
            {`Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\n🔗 Link: ${window.location.origin}/login\n📧 E-Mail: ${inviteResult.email}\n🔑 Passwort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`}
          </div>
          <button
            onClick={() => {
              const text = `Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\nLink: ${window.location.origin}/login\nE-Mail: ${inviteResult.email}\nPasswort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`;
              navigator.clipboard.writeText(text.replace(/\\n/g, '\n'));
              setCopied(true);
            }}
            className={`mt-3 px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
              copied
                ? 'bg-green-600 text-white'
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            {copied ? 'Kopiert!' : 'Nachricht kopieren'}
          </button>
        </div>
      )}

      {(() => {
        const filteredUsers = filterCourseId
          ? users.filter((u) => u.enrollments.some((e) => e.course_id === filterCourseId))
          : users;
        return filteredUsers.length === 0 ? (
          <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
            {filterCourseId ? 'Keine Nutzer in diesem Kurs.' : 'Noch keine Nutzer vorhanden.'}
          </div>
        ) : (
          <div className="space-y-3">
            {filteredUsers.map((user) => (
              <div key={user.id} className="bg-white rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-800">{user.name}</h3>
                      {user.is_admin && (
                        <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                          Admin
                        </span>
                      )}
                      {!user.is_admin && (
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          user.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}>
                          {user.is_active ? 'aktiv' : 'inaktiv'}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500">{user.email}</p>
                  </div>
                  {!user.is_admin && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleActive(user.id)}
                        className={`px-3 py-1.5 text-sm border rounded-lg transition-colors ${
                          user.is_active
                            ? 'border-gray-200 text-gray-500 hover:bg-gray-50'
                            : 'border-green-200 text-green-600 hover:bg-green-50'
                        }`}
                      >
                        {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                      </button>
                      <button
                        onClick={() => handleDeleteUser(user.id, user.name)}
                        className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                      >
                        Loschen
                      </button>
                    </div>
                  )}
                </div>

                {/* Enrollments */}
                {!user.is_admin && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {user.enrollments.map((enr) => (
                      <span
                        key={enr.enrollment_id}
                        className="inline-flex items-center gap-1.5 text-sm bg-[var(--nora-pink-light)] text-[var(--nora-pink-dark)] px-3 py-1 rounded-full"
                      >
                        {enr.course_title}
                        <button
                          onClick={() => handleRemoveEnrollment(enr.enrollment_id, user.name, enr.course_title)}
                          className="hover:text-red-500 transition-colors"
                          title="Aus Kurs entfernen"
                        >
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </span>
                    ))}
                    {enrollingUserId === user.id ? (
                      <select
                        autoFocus
                        className="text-sm border border-gray-200 rounded-lg px-3 py-1 focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] bg-white"
                        value=""
                        onChange={(e) => handleEnrollUser(user.id, e.target.value)}
                        onBlur={() => setEnrollingUserId(null)}
                      >
                        <option value="">Kurs wählen...</option>
                        {courses
                          .filter((c) => !user.enrollments.some((enr) => enr.course_id === c.id))
                          .map((c) => (
                            <option key={c.id} value={c.id}>{c.title}</option>
                          ))}
                      </select>
                    ) : (
                      <button
                        onClick={() => setEnrollingUserId(user.id)}
                        className="inline-flex items-center justify-center w-7 h-7 rounded-full border border-dashed border-gray-300 text-gray-400 hover:border-[var(--nora-pink)] hover:text-[var(--nora-pink)] transition-colors"
                        title="Kurs zuordnen"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v12m6-6H6" />
                        </svg>
                      </button>
                    )}
                    {user.enrollments.length === 0 && enrollingUserId !== user.id && (
                      <span className="text-xs text-gray-400">Kein Kurs zugewiesen</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}
