import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';

type State = 'loading' | 'success' | 'error';

export default function ConfirmEmailChange() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [state, setState] = useState<State>('loading');
  const [message, setMessage] = useState('');
  const [newEmail, setNewEmail] = useState('');

  useEffect(() => {
    if (!token) {
      setState('error');
      setMessage('Kein Bestätigungs-Token in der URL.');
      return;
    }
    api.confirmEmailChange(token)
      .then((res) => {
        setNewEmail(res.email);
        setState('success');
      })
      .catch((err: any) => {
        setMessage(err?.message || 'Bestätigungslink ist ungültig oder abgelaufen.');
        setState('error');
      });
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nora-warm)]">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/nw-logo.webp" alt="Nora Weweler" className="w-16 h-16 mb-3" />
          <h1 className="text-sm font-semibold text-gray-800">Nora Weweler</h1>
          <p className="text-xs text-gray-400">Ernährungsberatung · Kurse</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm p-8 text-center space-y-4">
          {state === 'loading' && (
            <>
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-gray-200 border-t-[var(--nora-pink)] mx-auto" />
              <p className="text-sm text-gray-500">E-Mail-Änderung wird bestätigt ...</p>
            </>
          )}
          {state === 'success' && (
            <>
              <h2 className="text-base font-semibold text-gray-800">E-Mail geändert</h2>
              <p className="text-sm text-gray-600">
                Deine neue E-Mail-Adresse <strong>{newEmail}</strong> ist jetzt aktiv.
                Bitte melde dich ab und mit der neuen Adresse wieder an.
              </p>
              <Link
                to="/login"
                className="inline-block w-full py-2.5 bg-[var(--nora-pink)] hover:bg-[var(--nora-pink-dark)] text-white rounded-lg font-medium transition-colors"
              >
                Zum Login
              </Link>
            </>
          )}
          {state === 'error' && (
            <>
              <p className="text-sm text-red-600">{message}</p>
              <Link to="/login" className="text-sm text-[var(--nora-pink)] hover:underline block">
                Zurück zum Login
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
