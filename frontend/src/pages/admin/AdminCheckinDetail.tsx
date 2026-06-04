import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ClipboardList, ArrowLeft } from 'lucide-react';
import { api, type CheckinLesson, type CheckinStep } from '../../lib/api';

const TYP_LABEL: Record<string, string> = {
  intro: 'Intro',
  skala: 'Skala 1–10',
  einfachauswahl: 'Einfachauswahl',
  mehrfachauswahl: 'Mehrfachauswahl',
  kurztext: 'Kurztext',
  langtext: 'Langtext',
  bestaetigung: 'Bestätigung',
};

function isChoice(step: CheckinStep): boolean {
  return step.typ === 'einfachauswahl' || step.typ === 'mehrfachauswahl';
}

export default function AdminCheckinDetail() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState<CheckinLesson | null>(null);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState('');
  const [week, setWeek] = useState<number | ''>('');
  const [frageDraft, setFrageDraft] = useState<Record<string, string>>({});
  const [optDraft, setOptDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = () => {
    if (!lessonId) return;
    api.getCheckinLesson(lessonId).then((l) => {
      setLesson(l);
      setTitle(l.title);
      setWeek(l.week_index ?? '');
      const fd: Record<string, string> = {};
      const od: Record<string, string> = {};
      for (const s of l.steps) {
        fd[s.key] = s.frage ?? '';
        od[s.key] = (s.optionen ?? []).join('\n');
      }
      setFrageDraft(fd);
      setOptDraft(od);
    }).finally(() => setLoading(false));
  };

  useEffect(load, [lessonId]);

  const handleSave = async () => {
    if (!lesson || !lessonId) return;
    setSaving(true);
    // Nur tatsächlich geänderte Schritte als Overrides senden (stabile Keys
    // bleiben unangetastet → Wochen vergleichbar). Leeren = zurück zum Standard.
    const stepOverrides: Record<string, { frage?: string; optionen?: string[] }> = {};
    for (const s of lesson.steps) {
      const ov: { frage?: string; optionen?: string[] } = {};
      const newFrage = frageDraft[s.key] ?? '';
      if (newFrage !== (s.frage ?? '')) ov.frage = newFrage;
      if (isChoice(s)) {
        const newOpt = (optDraft[s.key] ?? '').split('\n').map((x) => x.trim()).filter(Boolean);
        const origOpt = s.optionen ?? [];
        if (JSON.stringify(newOpt) !== JSON.stringify(origOpt)) ov.optionen = newOpt;
      }
      if (ov.frage !== undefined || ov.optionen !== undefined) stepOverrides[s.key] = ov;
    }

    const payload: { title?: string; week_index?: number; step_overrides?: typeof stepOverrides } = {};
    if (title.trim() && title.trim() !== lesson.title) payload.title = title.trim();
    if (week !== '' && Number(week) !== lesson.week_index) payload.week_index = Number(week);
    if (Object.keys(stepOverrides).length > 0) payload.step_overrides = stepOverrides;

    try {
      if (Object.keys(payload).length > 0) {
        await api.updateCheckinLesson(lessonId, payload);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      load();
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }
  if (!lesson) {
    return <div className="p-8 text-gray-500">Check-in nicht gefunden.</div>;
  }

  return (
    <div className="p-8 max-w-3xl">
      <button
        onClick={() => navigate(`/admin/course/${courseId}`)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-[var(--nora-pink-dark)] transition-colors mb-6"
      >
        <ArrowLeft size={15} /> Zurück zum Kurs
      </button>

      <div className="flex items-center gap-3 mb-1">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white shrink-0 bg-gradient-to-br from-[var(--berry)] to-[var(--nora-pink-dark)]">
          <ClipboardList size={18} />
        </div>
        <div>
          <span className="text-xs font-medium text-[var(--nora-pink-dark)] bg-[var(--nora-pink-light)] px-2 py-0.5 rounded-full">
            {lesson.template_typ === 'start' ? 'Bestandsaufnahme' : lesson.template_typ === 'laufend' ? 'Wöchentlicher Check-in' : 'Abschluss'}
          </span>
        </div>
      </div>

      <div className="bg-white rounded-2xl p-6 shadow-sm mt-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Titel (in der Modulliste)</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          />
        </div>
        {lesson.template_typ === 'laufend' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Woche</label>
            <input
              type="number"
              min={1}
              max={12}
              value={week}
              onChange={(e) => setWeek(e.target.value ? parseInt(e.target.value) : '')}
              className="w-32 px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              placeholder="z.B. 1"
            />
          </div>
        )}
      </div>

      <h3 className="font-semibold text-gray-800 mt-8 mb-3">Fragen</h3>
      <p className="text-sm text-gray-500 mb-4">
        Texte und Optionen gelten nur für dieses Formular. Die internen Keys bleiben
        stabil, damit Wochen später vergleichbar sind. Feld leeren = Standard wiederherstellen.
      </p>

      <div className="space-y-3">
        {lesson.steps.map((step) => (
          <div key={step.key} className="bg-white rounded-2xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                {TYP_LABEL[step.typ] ?? step.typ}
              </span>
              <span className="text-xs text-gray-400 font-mono">{step.key}</span>
              {step.pflichtfeld && <span className="text-xs text-amber-600">Pflicht</span>}
              {step.overridden && (
                <span className="text-xs text-[var(--nora-pink-dark)] bg-[var(--nora-pink-light)] px-1.5 py-0.5 rounded">angepasst</span>
              )}
            </div>
            <input
              type="text"
              value={frageDraft[step.key] ?? ''}
              onChange={(e) => setFrageDraft({ ...frageDraft, [step.key]: e.target.value })}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              placeholder={step.typ === 'bestaetigung' ? 'Bestätigungstext…' : step.typ === 'intro' ? 'Einleitungstext…' : 'Frage…'}
            />
            {isChoice(step) && (
              <div className="mt-2">
                <label className="block text-xs text-gray-500 mb-1">Optionen (eine pro Zeile)</label>
                <textarea
                  rows={Math.max(2, (optDraft[step.key] ?? '').split('\n').length)}
                  value={optDraft[step.key] ?? ''}
                  onChange={(e) => setOptDraft({ ...optDraft, [step.key]: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
                />
              </div>
            )}
            {step.typ === 'skala' && (
              <p className="text-xs text-gray-400 mt-2">
                Skala {step.skala_min}–{step.skala_max}
                {step.skala_labels?.min ? ` · ${step.skala_labels.min}` : ''}
                {step.skala_labels?.max ? ` → ${step.skala_labels.max}` : ''}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 mt-6 sticky bottom-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2.5 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors disabled:opacity-60 shadow-sm"
        >
          {saving ? 'Speichern…' : 'Speichern'}
        </button>
        {saved && <span className="text-green-600 text-sm">Gespeichert ✓</span>}
        <Link
          to={`/admin/course/${courseId}`}
          className="px-5 py-2.5 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Fertig
        </Link>
      </div>
    </div>
  );
}
