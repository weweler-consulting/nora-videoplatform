import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken } from '../lib/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      navigate('/');
    } catch (err) {
      setError('E-Mail oder Passwort falsch.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setForgotLoading(true);
    try {
      await api.forgotPassword(forgotEmail);
      setForgotSent(true);
    } catch {
      setError('Fehler beim Senden. Bitte versuche es erneut.');
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/nw-logo.webp" alt="Nora Weweler" className="w-16 h-16 mb-3" />
          <h1 className="text-sm font-semibold text-gray-800">Nora Weweler</h1>
          <p className="text-xs text-gray-400">Ernährungsberatung · Kurse</p>
        </div>

        {forgotMode ? (
          forgotSent ? (
            <div className="bg-white rounded-2xl shadow-sm p-8 text-center space-y-4">
              <div className="text-green-600 text-sm font-medium">
                Falls ein Konto mit dieser E-Mail existiert, wurde ein Link zum Zurücksetzen gesendet.
              </div>
              <p className="text-xs text-gray-400">Prüfe auch deinen Spam-Ordner.</p>
              <button
                onClick={() => { setForgotMode(false); setForgotSent(false); setForgotEmail(''); }}
                className="text-sm text-[var(--nora-pink)] hover:underline"
              >
                Zurück zum Login
              </button>
            </div>
          ) : (
            <form onSubmit={handleForgot} className="bg-white rounded-2xl shadow-sm p-8 space-y-5">
              <h2 className="text-base font-semibold text-gray-800 text-center">Passwort vergessen?</h2>
              <p className="text-sm text-gray-500 text-center">
                Gib deine E-Mail-Adresse ein und wir senden dir einen Link zum Zurücksetzen.
              </p>

              {error && (
                <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
                <input
                  type="email"
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
                  placeholder="deine@email.de"
                />
              </div>

              <button
                type="submit"
                disabled={forgotLoading}
                className="w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {forgotLoading ? 'Wird gesendet...' : 'Link senden'}
              </button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => { setForgotMode(false); setError(''); }}
                  className="text-sm text-[var(--nora-pink)] hover:underline"
                >
                  Zurück zum Login
                </button>
              </div>
            </form>
          )
        ) : (
          <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm p-8 space-y-5">
            {error && (
              <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
                placeholder="deine@email.de"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Passwort</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent transition-all"
                placeholder="Dein Passwort"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {loading ? 'Wird geladen...' : 'Anmelden'}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={() => { setForgotMode(true); setError(''); }}
                className="text-sm text-gray-400 hover:text-[var(--nora-pink)] transition-colors"
              >
                Passwort vergessen?
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
