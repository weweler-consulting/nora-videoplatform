import { useEffect, useState } from 'react';
import { api } from '../../lib/api';

export default function AdminSettings() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [profileMsg, setProfileMsg] = useState('');
  const [profileError, setProfileError] = useState('');

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [pwError, setPwError] = useState('');

  useEffect(() => {
    api.me().then((u) => {
      setName(u.name);
      setEmail(u.email);
    });
  }, []);

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileMsg('');
    setProfileError('');
    try {
      const updated = await api.updateProfile({ name, email });
      setName(updated.name);
      setEmail(updated.email);
      setProfileMsg('Profil gespeichert.');
    } catch (err: any) {
      setProfileError(err.message);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwMsg('');
    setPwError('');
    if (newPw !== confirmPw) {
      setPwError('Passworter stimmen nicht uberein.');
      return;
    }
    if (newPw.length < 6) {
      setPwError('Passwort muss mindestens 6 Zeichen haben.');
      return;
    }
    try {
      await api.changePassword(currentPw, newPw);
      setPwMsg('Passwort geandert.');
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err: any) {
      setPwError(err.message);
    }
  };

  return (
    <div className="p-8 max-w-2xl">
      <h2 className="text-xl font-semibold mb-6">Einstellungen</h2>

      {/* Profile */}
      <form onSubmit={handleProfileSave} className="bg-white rounded-2xl p-6 shadow-sm mb-6">
        <h3 className="font-semibold text-gray-800 mb-4">Profil</h3>

        {profileMsg && (
          <div className="bg-green-50 text-green-600 text-sm px-4 py-3 rounded-lg mb-4">{profileMsg}</div>
        )}
        {profileError && (
          <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">{profileError}</div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            />
          </div>
        </div>

        <button
          type="submit"
          className="mt-4 px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          Speichern
        </button>
      </form>

      {/* Password */}
      <form onSubmit={handlePasswordChange} className="bg-white rounded-2xl p-6 shadow-sm">
        <h3 className="font-semibold text-gray-800 mb-4">Passwort andern</h3>

        {pwMsg && (
          <div className="bg-green-50 text-green-600 text-sm px-4 py-3 rounded-lg mb-4">{pwMsg}</div>
        )}
        {pwError && (
          <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">{pwError}</div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Aktuelles Passwort</label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Neues Passwort</label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Neues Passwort bestatigen</label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
            />
          </div>
        </div>

        <button
          type="submit"
          className="mt-4 px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          Passwort andern
        </button>
      </form>
    </div>
  );
}
