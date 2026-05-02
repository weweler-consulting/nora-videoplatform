import { useEffect, useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import { api, type CourseDetail, type LessonItem, type AttachmentItem } from '../lib/api';

// Normalise a Bunny Stream embed URL: force the iframe.mediadelivery.net host
// and append params iOS Safari needs to play inline (otherwise the player
// tries to enter native fullscreen from inside the iframe and the frame stays
// black).
function withPlayerParams(rawUrl: string): string {
  const url = rawUrl.replace('player.mediadelivery.net', 'iframe.mediadelivery.net');
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}playsinline=true&preload=true&responsive=true`;
}

export default function LessonView() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (courseId) {
      api.getCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  }, [courseId]);

  useEffect(() => {
    if (lessonId) {
      api.getAttachments(lessonId).then(setAttachments).catch(console.error);
    }
  }, [lessonId]);

  // Find current lesson and compute prev/next
  const { currentLesson, allLessons, currentIndex } = useMemo(() => {
    if (!course) return { currentLesson: null, allLessons: [] as LessonItem[], currentIndex: -1 };
    const all: LessonItem[] = [];
    for (const mod of course.modules) {
      for (const sec of mod.sections) {
        for (const les of sec.lessons) {
          all.push(les);
        }
      }
    }
    const idx = all.findIndex((l) => l.id === lessonId);
    return { currentLesson: idx >= 0 ? all[idx] : null, allLessons: all, currentIndex: idx };
  }, [course, lessonId]);

  const prevLesson = currentIndex > 0 ? allLessons[currentIndex - 1] : null;
  const nextLesson = currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null;

  const handleToggleComplete = async () => {
    if (!currentLesson || !courseId) return;
    try {
      if (currentLesson.completed) {
        await api.uncompleteLesson(currentLesson.id);
      } else {
        await api.completeLesson(currentLesson.id);
      }
      const updated = await api.getCourse(courseId);
      setCourse(updated);
    } catch (err: any) {
      alert(err?.message || 'Fortschritt konnte nicht gespeichert werden.');
    }
  };

  const handleNext = () => {
    if (nextLesson && courseId) {
      navigate(`/course/${courseId}/lesson/${nextLesson.id}`);
    }
  };

  const handleDownloadAttachment = async (attachmentId: string, filename: string) => {
    const token = localStorage.getItem('token');
    try {
      const res = await fetch(`/api/v1/attachments/${attachmentId}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        alert('Download fehlgeschlagen.');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      alert('Download fehlgeschlagen.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!course || !currentLesson) {
    return <div className="p-8 text-gray-500">Lektion nicht gefunden.</div>;
  }

  // Find which module/section this lesson belongs to
  let moduleName = '';
  let sectionName = '';
  for (const mod of course.modules) {
    for (const sec of mod.sections) {
      if (sec.lessons.some((l) => l.id === lessonId)) {
        moduleName = mod.title;
        sectionName = sec.title;
      }
    }
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl">
      {/* Breadcrumb — desktop */}
      <div className="hidden md:flex items-center gap-2 text-sm text-gray-500 mb-6 flex-wrap">
        <Link to="/" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Meine Kurse
        </Link>
        <span>/</span>
        <Link to={`/course/${courseId}`} className="hover:text-[var(--nora-pink-dark)] transition-colors">
          {course.title}
        </Link>
        <span>/</span>
        <span className="text-gray-400">{moduleName}</span>
        <span>/</span>
        <span className="text-gray-700 truncate">{currentLesson.title}</span>
      </div>

      {/* Back link — mobile */}
      <Link
        to={`/course/${courseId}`}
        className="md:hidden inline-flex items-center gap-2 text-sm text-gray-500 mb-4 hover:text-[var(--nora-pink-dark)]"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Zurück zum Kurs
      </Link>

      {/* Module header bar — clickable back to course */}
      <Link
        to={`/course/${courseId}`}
        className="bg-gradient-to-r from-[var(--nora-pink)] to-[var(--nora-pink-dark)] rounded-2xl p-4 md:p-5 mb-4 md:mb-6 flex items-center justify-between text-white group hover:opacity-95 transition-opacity gap-3"
      >
        <div className="flex items-center gap-3 min-w-0">
          <svg className="w-5 h-5 opacity-60 group-hover:opacity-100 transition-opacity shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          <div className="min-w-0">
            <p className="text-xs opacity-80 uppercase tracking-wider truncate">{sectionName}</p>
            <h2 className="text-base md:text-lg font-semibold truncate">{moduleName}</h2>
          </div>
        </div>
        <p className="text-sm opacity-80 shrink-0">
          {currentIndex + 1} / {allLessons.length}
        </p>
      </Link>

      {/* Lesson title */}
      <h2 className="text-lg md:text-xl font-semibold mb-4 md:mb-6">{currentLesson.title}</h2>

      {/* Video player — playsinline=true is required so iOS Safari plays the
          video inline instead of trying to enter native fullscreen, which fails
          inside the iframe and leaves the frame black. */}
      {currentLesson.video_url ? (
        <>
          <div className="aspect-video bg-black rounded-2xl mb-2">
            <iframe
              src={withPlayerParams(currentLesson.video_url)}
              title={currentLesson.title}
              className="w-full h-full block rounded-2xl"
              style={{ border: 0 }}
              allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture; fullscreen"
              allowFullScreen
            />
          </div>
          {/* DEBUG (temp): direct link to the bare Bunny embed URL — used to
              isolate whether iOS playback issues are in our wrapper or in the
              Bunny library config. Remove after diagnosis. */}
          <div className="text-xs text-gray-400 mb-4 md:mb-6 break-all">
            <a
              href={withPlayerParams(currentLesson.video_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-[var(--nora-pink-dark)]"
            >
              Diagnose: Video direkt im Browser öffnen
            </a>
          </div>
        </>
      ) : (
        <div className="aspect-video bg-gray-100 rounded-2xl flex items-center justify-center mb-4 md:mb-6 text-gray-400">
          Kein Video vorhanden
        </div>
      )}

      {/* Description */}
      {currentLesson.description && (
        <div className="bg-white rounded-2xl p-4 md:p-6 mb-4 md:mb-6 prose prose-gray max-w-none prose-headings:text-gray-800 prose-a:text-[var(--nora-pink-dark)] prose-strong:text-gray-800">
          <Markdown>{currentLesson.description}</Markdown>
        </div>
      )}

      {/* Downloads */}
      {attachments.length > 0 && (
        <div className="bg-white rounded-2xl p-4 md:p-6 mb-4 md:mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Downloads
          </h3>
          <div className="space-y-2">
            {attachments.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => handleDownloadAttachment(a.id, a.original_filename)}
                className="w-full text-left flex items-center gap-3 px-4 py-3 bg-gray-50 rounded-lg hover:bg-[var(--nora-pink-light)] transition-colors group"
              >
                <svg className="w-5 h-5 text-gray-400 group-hover:text-[var(--nora-pink-dark)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                <span className="text-sm text-gray-700 group-hover:text-[var(--nora-pink-dark)] flex-1">{a.original_filename}</span>
                <span className="text-xs text-gray-400">{(a.file_size / 1024).toFixed(0)} KB</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <button
          onClick={handleToggleComplete}
          className={`flex items-center justify-center gap-2 px-5 py-3 sm:py-2.5 rounded-lg font-medium transition-colors w-full sm:w-auto ${
            currentLesson.completed
              ? 'bg-green-100 text-green-700 hover:bg-green-200'
              : 'bg-[var(--nora-pink-light)] text-[var(--nora-pink-dark)] hover:bg-[var(--nora-pink)] hover:text-white'
          }`}
        >
          {currentLesson.completed ? (
            <>
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
              Abgeschlossen
            </>
          ) : (
            'Als abgeschlossen markieren'
          )}
        </button>

        <div className="flex gap-3 w-full sm:w-auto">
          {prevLesson && (
            <Link
              to={`/course/${courseId}/lesson/${prevLesson.id}`}
              className="flex-1 sm:flex-none text-center px-4 py-3 sm:py-2.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Vorherige
            </Link>
          )}
          {nextLesson && (
            <button
              onClick={async () => {
                if (!currentLesson.completed) {
                  await api.completeLesson(currentLesson.id);
                }
                handleNext();
              }}
              className="flex-1 sm:flex-none px-5 py-3 sm:py-2.5 rounded-lg bg-[var(--nora-pink)] text-white font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
            >
              Weiter
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
