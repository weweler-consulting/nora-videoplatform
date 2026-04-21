import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { api, setToken } from '../lib/api';

interface InviteInfo {
  email: string;
  name: string;
  course_titles: string[];
}

export default function AcceptInvite() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [loadError, setLoadError] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoadError('Kein Einladungs-Token in der URL.');
      return;
    }
    api.getInvite(token)
      .then(setInvite)
      .catch((err) => setLoadError(err.message || 'Einladungslink ist ungültig oder abgelaufen.'));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Passwort muss mindestens 8 Zeichen haben.');
      return;
    }
    if (password !== confirm) {
      setError('Passwörter stimmen nicht überein.');
      return;
    }
    if (!acceptTerms) {
      setError('Bitte akzeptiere AGB und Datenschutzerklärung.');
      return;
    }
    setSubmitting(true);
    try {
      const { access_token } = await api.acceptInvite(token!, password, acceptTerms);
      setToken(access_token);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Einladungslink ist ungültig oder abgelaufen.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
        <div className="w-full max-w-sm text-center">
          <div className="bg-white rounded-2xl shadow-sm p-8 space-y-4">
            <p className="text-sm text-red-600">{loadError}</p>
            <p className="text-xs text-gray-400">
              Bitte wende dich an Nora, falls du einen neuen Link brauchst.
            </p>
            <Link to="/login" className="text-sm text-[var(--nora-pink)] hover:underline block">
              Zurück zum Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!invite) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-gray-200 border-t-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)] py-10">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/nw-logo.webp" alt="Nora Weweler" className="w-16 h-16 mb-3" />
          <h1 className="text-sm font-semibold text-gray-800">Nora Weweler</h1>
          <p className="text-xs text-gray-400">Ernährungsberatung · Kurse</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm p-8 space-y-5">
          <div className="text-center">
            <h2 className="text-base font-semibold text-gray-800">Willkommen, {invite.name}!</h2>
            <p className="text-sm text-gray-500 mt-2">
              {invite.course_titles.length === 1
                ? <>Du wurdest zum Kurs <strong>{invite.course_titles[0]}</strong> eingeladen.</>
                : <>Du wurdest zu folgenden Kursen eingeladen:<br /><strong>{invite.course_titles.join(', ')}</strong></>}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Lege jetzt dein Passwort fest, um deinen Zugang zu aktivieren.
            </p>
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
            <input
              type="email"
              value={invite.email}
              disabled
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 text-gray-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Passwort festlegen</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
              placeholder="Mindestens 8 Zeichen"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Passwort bestätigen</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
              placeholder="Passwort wiederholen"
            />
          </div>

          <label className="flex items-start gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-gray-300"
            />
            <span>
              Ich akzeptiere die{' '}
              <a href="https://noraweweler.de/agbs" target="_blank" rel="noopener noreferrer" className="text-[var(--nora-pink)] hover:underline">AGB</a>
              {' '}und die{' '}
              <a href="https://noraweweler.de/datenschutz" target="_blank" rel="noopener noreferrer" className="text-[var(--nora-pink)] hover:underline">Datenschutzerklärung</a>.
            </span>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {submitting ? 'Wird gespeichert...' : 'Einladung annehmen'}
          </button>
        </form>

        <footer className="mt-6 text-center text-xs text-gray-400 space-x-3">
          <a href="https://noraweweler.de/impressum" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--nora-pink)] transition-colors">Impressum</a>
          <span>·</span>
          <a href="https://noraweweler.de/datenschutz" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--nora-pink)] transition-colors">Datenschutz</a>
          <span>·</span>
          <a href="https://noraweweler.de/agbs" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--nora-pink)] transition-colors">AGB</a>
        </footer>
      </div>
    </div>
  );
}
