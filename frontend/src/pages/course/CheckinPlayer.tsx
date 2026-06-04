import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardList, Check, Pencil } from 'lucide-react';
import { api, type CheckinStep } from '../../lib/api';

type AnswerValue = string | number | string[];
type Answers = Record<string, AnswerValue>;

function isAnswered(step: CheckinStep, value: AnswerValue | undefined): boolean {
  if (step.typ === 'mehrfachauswahl') return Array.isArray(value) && value.length > 0;
  if (step.typ === 'intro' || step.typ === 'bestaetigung') return true;
  return value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0);
}

export default function CheckinPlayer({
  lessonId,
  nextHref,
  onCompleted,
}: {
  lessonId: string;
  nextHref?: string | null;
  onCompleted: () => void;
}) {
  const [steps, setSteps] = useState<CheckinStep[] | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [idx, setIdx] = useState(0);
  const [mode, setMode] = useState<'loading' | 'form' | 'review' | 'done'>('loading');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.getCheckinLesson(lessonId), api.getCheckinResponse(lessonId)])
      .then(([lesson, resp]) => {
        if (!active) return;
        setSteps(lesson.steps);
        if (resp.submitted) {
          setAnswers(resp.answers as Answers);
          setMode('review');
        } else {
          setMode('form');
        }
      })
      .catch(() => active && setError('Konnte nicht geladen werden.'));
    return () => { active = false; };
  }, [lessonId]);

  const answerableSteps = useMemo(
    () => (steps ?? []).filter((s) => s.typ !== 'intro' && s.typ !== 'bestaetigung'),
    [steps],
  );

  if (mode === 'loading' || !steps) {
    return (
      <div className="bg-white rounded-2xl shadow-sm flex items-center justify-center min-h-[420px] mb-4 md:mb-6">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (error) {
    return <div className="bg-white rounded-2xl shadow-sm p-8 text-center text-gray-500 mb-4 md:mb-6">{error}</div>;
  }

  const setAnswer = (key: string, value: AnswerValue) => setAnswers((a) => ({ ...a, [key]: value }));

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.submitCheckin(lessonId, answers);
      setMode('done');
      onCompleted();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Speichern fehlgeschlagen.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // --- Bestätigungs-/Done-Screen ---
  if (mode === 'done') {
    const bestaetigung = steps.find((s) => s.typ === 'bestaetigung');
    return (
      <div className="bg-white rounded-2xl shadow-sm flex flex-col items-center justify-center text-center min-h-[420px] p-8 mb-4 md:mb-6">
        <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4">
          <Check className="text-green-600" size={28} />
        </div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">Geschafft – danke dir!</h3>
        <p className="text-gray-500 max-w-md">{bestaetigung?.frage || 'Deine Antworten sind gespeichert.'}</p>
        <div className="flex gap-3 mt-6">
          <button
            onClick={() => setMode('review')}
            className="px-5 py-2.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Antworten ansehen
          </button>
          {nextHref && (
            <Link
              to={nextHref}
              className="px-5 py-2.5 rounded-lg bg-[var(--nora-pink)] text-white font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
            >
              Weiter
            </Link>
          )}
        </div>
      </div>
    );
  }

  // --- Read-only Review beim Wiederöffnen ---
  if (mode === 'review') {
    return (
      <div className="bg-white rounded-2xl shadow-sm p-6 md:p-8 mb-4 md:mb-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2 text-[var(--nora-pink-dark)]">
            <ClipboardList size={18} />
            <span className="font-semibold">Deine Antworten</span>
          </div>
          <button
            onClick={() => { setIdx(0); setMode('form'); }}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-[var(--nora-pink-dark)] transition-colors"
          >
            <Pencil size={14} /> Bearbeiten
          </button>
        </div>
        <div className="space-y-4">
          {answerableSteps.map((s) => {
            const v = answers[s.key];
            const display = Array.isArray(v) ? v.join(', ') : (v === undefined || v === '' ? '—' : String(v));
            return (
              <div key={s.key} className="border-b border-gray-100 pb-3 last:border-0">
                <p className="text-sm text-gray-500">{s.frage}</p>
                <p className="text-gray-800 mt-0.5">{display}</p>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // --- Form-Modus: eine Frage pro Screen ---
  const step = steps[idx];
  const total = steps.length;
  const value = answers[step.key];
  const required = step.pflichtfeld && step.typ !== 'intro' && step.typ !== 'bestaetigung';
  const canAdvance = !required || isAnswered(step, value);
  const isLast = idx === total - 1;

  return (
    <div className="bg-white rounded-2xl shadow-sm flex flex-col min-h-[420px] md:min-h-[460px] mb-4 md:mb-6">
      {/* Fortschritt */}
      <div className="px-6 md:px-8 pt-6">
        <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
          <span className="flex items-center gap-1.5">
            <ClipboardList size={14} /> Check-in
          </span>
          <span>Schritt {idx + 1} von {total}</span>
        </div>
        <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--nora-pink)] transition-all"
            style={{ width: `${((idx + 1) / total) * 100}%` }}
          />
        </div>
      </div>

      {/* Frage-Bereich */}
      <div className="flex-1 overflow-auto px-6 md:px-8 py-6 flex flex-col justify-center">
        <StepBody step={step} value={value} onChange={(v) => setAnswer(step.key, v)} />
        {error && <p className="text-red-500 text-sm mt-4">{error}</p>}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between gap-3 px-6 md:px-8 py-4 border-t border-gray-100">
        <button
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
          className="px-4 py-2.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-40"
        >
          Zurück
        </button>
        {isLast ? (
          <button
            onClick={handleSubmit}
            disabled={submitting || !canAdvance}
            className="px-6 py-2.5 rounded-lg bg-[var(--nora-pink)] text-white font-medium hover:bg-[var(--nora-pink-dark)] transition-colors disabled:opacity-50"
          >
            {submitting ? 'Speichern…' : 'Abschicken'}
          </button>
        ) : (
          <button
            onClick={() => setIdx((i) => Math.min(total - 1, i + 1))}
            disabled={!canAdvance}
            className="px-6 py-2.5 rounded-lg bg-[var(--nora-pink)] text-white font-medium hover:bg-[var(--nora-pink-dark)] transition-colors disabled:opacity-50"
            title={!canAdvance ? 'Bitte zuerst beantworten' : undefined}
          >
            Weiter
          </button>
        )}
      </div>
    </div>
  );
}

function StepBody({
  step,
  value,
  onChange,
}: {
  step: CheckinStep;
  value: string | number | string[] | undefined;
  onChange: (v: string | number | string[]) => void;
}) {
  if (step.typ === 'intro' || step.typ === 'bestaetigung') {
    return (
      <div className="text-center max-w-xl mx-auto">
        <div className="w-12 h-12 rounded-full bg-[var(--nora-pink-light)] flex items-center justify-center mx-auto mb-4">
          <ClipboardList className="text-[var(--nora-pink-dark)]" size={22} />
        </div>
        <p className="text-lg text-gray-700 leading-relaxed">{step.frage}</p>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto w-full">
      <h3 className="text-lg md:text-xl font-semibold text-gray-800 mb-1">{step.frage}</h3>
      {step.hilfetext && <p className="text-sm text-gray-400 mb-4">{step.hilfetext}</p>}
      {!step.hilfetext && <div className="mb-4" />}

      {step.typ === 'skala' && (
        <div>
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: (step.skala_max ?? 10) - (step.skala_min ?? 1) + 1 }, (_, i) => (step.skala_min ?? 1) + i).map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => onChange(n)}
                className={`w-11 h-11 rounded-lg text-sm font-medium border transition-colors ${value === n ? 'bg-[var(--nora-pink)] text-white border-transparent' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                {n}
              </button>
            ))}
          </div>
          {(step.skala_labels?.min || step.skala_labels?.max) && (
            <div className="flex justify-between text-xs text-gray-400 mt-2">
              <span>{step.skala_labels?.min}</span>
              <span>{step.skala_labels?.max}</span>
            </div>
          )}
        </div>
      )}

      {step.typ === 'einfachauswahl' && (
        <div className="space-y-2">
          {(step.optionen ?? []).map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${value === opt ? 'bg-[var(--nora-pink-light)] border-[var(--nora-pink)] text-[var(--nora-pink-dark)]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {step.typ === 'mehrfachauswahl' && (
        <div className="space-y-2">
          {(step.optionen ?? []).map((opt) => {
            const arr = Array.isArray(value) ? value : [];
            const checked = arr.includes(opt);
            return (
              <button
                key={opt}
                type="button"
                onClick={() => onChange(checked ? arr.filter((x) => x !== opt) : [...arr, opt])}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors flex items-center gap-3 ${checked ? 'bg-[var(--nora-pink-light)] border-[var(--nora-pink)] text-[var(--nora-pink-dark)]' : 'border-gray-200 text-gray-700 hover:bg-gray-50'}`}
              >
                <span className={`w-5 h-5 rounded border flex items-center justify-center shrink-0 ${checked ? 'bg-[var(--nora-pink)] border-transparent' : 'border-gray-300'}`}>
                  {checked && <Check size={14} className="text-white" />}
                </span>
                {opt}
              </button>
            );
          })}
        </div>
      )}

      {step.typ === 'kurztext' && (
        <input
          type="text"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          placeholder="Deine Antwort…"
          autoFocus
        />
      )}

      {step.typ === 'langtext' && (
        <textarea
          rows={4}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent resize-none"
          placeholder="Schreib so viel oder wenig du magst…"
          autoFocus
        />
      )}
    </div>
  );
}
