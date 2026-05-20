import { useEffect, useMemo, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Users } from 'lucide-react';
import {
  api,
  type AnnouncementCreateResult,
  type AnnouncementTargetType,
  type CourseDetail,
} from '../lib/api';

type Props = {
  courseId: string;
  course: CourseDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSent?: (result: AnnouncementCreateResult) => void;
  preselectTarget?: { type: AnnouncementTargetType; id: string } | null;
};

type FlatTarget =
  | { type: 'module'; id: string; label: string }
  | { type: 'lesson'; id: string; label: string; moduleTitle: string };

function flattenTargets(course: CourseDetail): FlatTarget[] {
  const out: FlatTarget[] = [];
  for (const m of course.modules) {
    out.push({ type: 'module', id: m.id, label: `Modul: ${m.title}` });
    for (const s of m.sections ?? []) {
      for (const l of s.lessons ?? []) {
        out.push({
          type: 'lesson',
          id: l.id,
          label: `   ↳ ${l.title}`,
          moduleTitle: m.title,
        });
      }
    }
  }
  return out;
}

export default function AnnouncementComposeModal({
  courseId,
  course,
  open,
  onOpenChange,
  onSent,
  preselectTarget,
}: Props) {
  const targets = useMemo(() => flattenTargets(course), [course]);

  const [targetKey, setTargetKey] = useState<string>('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [recipientCount, setRecipientCount] = useState<number | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset / preselect on open
  useEffect(() => {
    if (!open) return;
    const key = preselectTarget ? `${preselectTarget.type}:${preselectTarget.id}` : '';
    setTargetKey(key);
    setSubject('');
    setBody('');
    setRecipientCount(null);
    setError(null);
  }, [open, preselectTarget]);

  // Fetch preview when targetKey changes
  useEffect(() => {
    if (!open || !targetKey) return;
    const [type, id] = targetKey.split(':') as [AnnouncementTargetType, string];
    setLoadingPreview(true);
    setError(null);
    api
      .previewAnnouncement(courseId, type, id)
      .then((p) => {
        setSubject(p.suggested_subject);
        setBody(p.suggested_body);
        setRecipientCount(p.recipient_count);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Vorschau fehlgeschlagen');
      })
      .finally(() => setLoadingPreview(false));
  }, [open, targetKey, courseId]);

  const canSend =
    !!targetKey &&
    subject.trim().length > 0 &&
    body.trim().length > 0 &&
    !sending &&
    (recipientCount ?? 0) > 0;

  const handleSend = async () => {
    if (!canSend) return;
    const [type, id] = targetKey.split(':') as [AnnouncementTargetType, string];
    setSending(true);
    setError(null);
    try {
      const result = await api.createAnnouncement(courseId, {
        target_type: type,
        target_id: id,
        subject: subject.trim(),
        body: body.trim(),
      });
      onSent?.(result);
      onOpenChange(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Versand fehlgeschlagen');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-5 border-b">
            <Dialog.Title className="text-lg font-semibold">
              Klientinnen informieren
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              Sende eine E-Mail an alle Teilnehmerinnen dieses Kurses.
            </Dialog.Description>
            <Dialog.Close className="text-gray-400 hover:text-gray-600" aria-label="Schliessen">
              <X size={20} />
            </Dialog.Close>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Worueber informieren?
              </label>
              <select
                value={targetKey}
                onChange={(e) => setTargetKey(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              >
                <option value="">- bitte waehlen -</option>
                {targets.map((t) => (
                  <option key={`${t.type}:${t.id}`} value={`${t.type}:${t.id}`}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Betreff</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={200}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
                disabled={loadingPreview}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Nachricht</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                maxLength={5000}
                rows={8}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent font-sans text-sm"
                disabled={loadingPreview}
              />
              <p className="text-xs text-gray-500 mt-1">
                Klientinnen werden automatisch mit &bdquo;Hallo [Name]&ldquo; angesprochen,
                am Ende kommt die Grussformel. Du schreibst nur den Mittelteil.
              </p>
            </div>

            {recipientCount !== null && (
              <p className="text-sm text-gray-600 flex items-center gap-2">
                <Users size={14} />
                Wird an <strong>{recipientCount}</strong>{' '}
                {recipientCount === 1 ? 'Teilnehmerin' : 'Teilnehmerinnen'} gesendet.
              </p>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>

          <div className="flex justify-end gap-2 p-5 border-t bg-gray-50">
            <Dialog.Close className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50">
              Abbrechen
            </Dialog.Close>
            <button
              onClick={handleSend}
              disabled={!canSend}
              className="px-4 py-2 rounded-lg bg-[var(--nora-pink)] text-white text-sm font-medium hover:bg-[var(--nora-pink-dark)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {sending ? 'Wird gesendet...' : 'Jetzt senden'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
