import { useState } from 'react';
import { api } from '../lib/api';

// Status-Label pro Modul: Entwurf = nur Admins sehen es, Live = alle Kundinnen.
export function ModuleStatusBadge({ isPublished }: { isPublished: boolean }) {
  return isPublished ? (
    <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
      Live
    </span>
  ) : (
    <span
      className="text-xs font-medium text-gray-600 bg-gray-200 px-2 py-0.5 rounded-full"
      title="Nur für Admins sichtbar — Kundinnen sehen dieses Modul noch nicht"
    >
      Entwurf
    </span>
  );
}

export function ModulePublishButton({
  moduleId,
  title,
  isPublished,
  onChange,
}: {
  moduleId: string;
  title: string;
  isPublished: boolean;
  onChange: () => void;
}) {
  const [saving, setSaving] = useState(false);

  const toggle = async () => {
    const question = isPublished
      ? `Modul "${title}" zurück auf Entwurf setzen? Kundinnen sehen es dann nicht mehr.`
      : `Modul "${title}" live schalten? Alle Kundinnen im Kurs sehen es sofort.`;
    if (!confirm(question)) return;
    setSaving(true);
    try {
      await api.updateModule(moduleId, { is_published: !isPublished });
      onChange();
    } catch (e) {
      alert(`Umschalten fehlgeschlagen: ${e instanceof Error ? e.message : 'unbekannter Fehler'}`);
    } finally {
      setSaving(false);
    }
  };

  return isPublished ? (
    <button
      onClick={toggle}
      disabled={saving}
      className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-60"
    >
      Auf Entwurf
    </button>
  ) : (
    <button
      onClick={toggle}
      disabled={saving}
      className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-60"
    >
      Live schalten
    </button>
  );
}
