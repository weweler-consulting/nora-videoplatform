import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { api } from '../lib/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password.length < 6) {
      setError('Passwort muss mindestens 6 Zeichen haben.');
      return;
    }
    if (password !== confirm) {
      setError('Passwörter stimmen nicht überein.');
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(token!, password);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Link ist ungültig oder abgelaufen.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
        <div className="w-full max-w-sm text-center">
          <p className="text-sm text-gray-600 mb-4">Ungültiger Link.</p>
          <Link to="/login" className="text-sm text-[var(--nora-pink)] hover:underline">
            Zurück zum Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/nw-logo.webp" alt="Nora Weweler" className="w-16 h-16 mb-3" />
          <h1 className="text-sm font-semibold text-gray-800">Nora Weweler</h1>
          <p className="text-xs text-gray-400">Ernährungsberatung · Kurse</p>
        </div>

        {success ? (
          <div className="bg-white rounded-2xl shadow-sm p-8 text-center space-y-4">
            <div className="text-green-600 text-sm font-medium">Passwort erfolgreich geändert!</div>
            <button
              onClick={() => navigate('/login')}
              className="w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors"
            >
              Zum Login
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm p-8 space-y-5">
            <h2 className="text-base font-semibold text-gray-800 text-center">Neues Passwort vergeben</h2>

            {error && (
              <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Neues Passwort</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
                placeholder="Mindestens 6 Zeichen"
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

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {loading ? 'Wird gespeichert...' : 'Passwort speichern'}
            </button>

            <div className="text-center">
              <Link to="/login" className="text-sm text-[var(--nora-pink)] hover:underline">
                Zurück zum Login
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
