import { useEffect, useState } from 'react';
import { api, type LiveCallImportInfo } from '../../lib/api';

const STATUS_LABEL: Record<string, string> = {
  imported: 'Entwurf · wartet auf Freigabe',
  published: 'Freigegeben',
  dismissed: 'Verworfen',
  new: 'Wird importiert …',
  failed: 'Fehlgeschlagen',
};

export default function AdminLiveCalls() {
  const [imports, setImports] = useState<LiveCallImportInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.listLiveCallImports(showAll ? undefined : 'imported')
      .then(setImports)
      .catch(() => setImports([]))
      .finally(() => setLoading(false));
  };
  useEffect(load, [showAll]);

  const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('de-DE') : '—');

  const approve = async (id: string) => {
    if (!confirm('Freigeben & ankündigen? Die eingeschriebenen Kundinnen bekommen die Ankündigungs-Mail.')) return;
    setBusy(id);
    try { await api.approveLiveCallImport(id); load(); } finally { setBusy(null); }
  };
  const dismiss = async (id: string) => {
    if (!confirm('Verwerfen? Die (versteckte) Lektion und das Video werden gelöscht.')) return;
    setBusy(id);
    try { await api.dismissLiveCallImport(id); load(); } finally { setBusy(null); }
  };

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Live-Call-Importe</h2>
        <label className="flex items-center gap-2 text-sm text-gray-500 select-none">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Alle anzeigen
        </label>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
        </div>
      ) : imports.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          {showAll ? 'Noch keine Live-Call-Importe.' : 'Keine anstehenden Freigaben. 🎉'}
        </div>
      ) : (
        <div className="space-y-3">
          {imports.map((imp) => (
            <div key={imp.id} className="bg-white rounded-2xl p-5 shadow-sm flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="font-semibold text-gray-800">Live-Call {fmtDate(imp.occurrence_at)}</div>
                <div className="text-sm text-gray-500 truncate">
                  {imp.course_title || 'Kurs unbekannt'} ·{' '}
                  <span className={imp.status === 'imported' ? 'text-amber-700' : imp.status === 'published' ? 'text-green-600' : 'text-gray-400'}>
                    {STATUS_LABEL[imp.status] || imp.status}
                  </span>
                </div>
              </div>
              {imp.status === 'imported' && (
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => approve(imp.id)} disabled={busy === imp.id}
                    className="px-3 py-1.5 text-sm bg-[var(--nora-pink)] text-white rounded-lg hover:bg-[var(--nora-pink-dark)] transition-colors disabled:opacity-60">
                    Freigeben
                  </button>
                  <button onClick={() => dismiss(imp.id)} disabled={busy === imp.id}
                    className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors disabled:opacity-60">
                    Verwerfen
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
