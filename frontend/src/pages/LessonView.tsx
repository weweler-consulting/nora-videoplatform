import { useEffect, useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api, type CourseDetail, type LessonItem } from '../lib/api';

export default function LessonView() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (courseId) {
      api.getCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  }, [courseId]);

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
    if (currentLesson.completed) {
      await api.uncompleteLesson(currentLesson.id);
    } else {
      await api.completeLesson(currentLesson.id);
    }
    // Refresh course data
    const updated = await api.getCourse(courseId);
    setCourse(updated);
  };

  const handleNext = () => {
    if (nextLesson && courseId) {
      navigate(`/course/${courseId}/lesson/${nextLesson.id}`);
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
    <div className="p-8 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6 flex-wrap">
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

      {/* Module header bar */}
      <div className="bg-gradient-to-r from-[var(--nora-pink)] to-[var(--nora-pink-dark)] rounded-2xl p-5 mb-6 flex items-center justify-between text-white">
        <div>
          <p className="text-xs opacity-80 uppercase tracking-wider">{sectionName}</p>
          <h2 className="text-lg font-semibold">{moduleName}</h2>
        </div>
        <p className="text-sm opacity-80">
          {currentIndex + 1} / {allLessons.length}
        </p>
      </div>

      {/* Lesson title */}
      <h2 className="text-xl font-semibold mb-6">{currentLesson.title}</h2>

      {/* Video player */}
      {currentLesson.video_url ? (
        <div className="aspect-video bg-black rounded-2xl overflow-hidden mb-6">
          <iframe
            src={currentLesson.video_url}
            className="w-full h-full"
            allow="autoplay; fullscreen; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : (
        <div className="aspect-video bg-gray-100 rounded-2xl flex items-center justify-center mb-6 text-gray-400">
          Kein Video vorhanden
        </div>
      )}

      {/* Description */}
      {currentLesson.description && (
        <div className="bg-white rounded-2xl p-6 mb-6">
          <p className="text-gray-700 whitespace-pre-wrap">{currentLesson.description}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleToggleComplete}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-colors ${
            currentLesson.completed
              ? 'bg-green-100 text-green-700 hover:bg-green-200'
              : 'bg-[var(--nora-pink-light)] text-[var(--nora-pink-dark)] hover:bg-[var(--nora-pink)]  hover:text-white'
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

        <div className="flex gap-3">
          {prevLesson && (
            <Link
              to={`/course/${courseId}/lesson/${prevLesson.id}`}
              className="px-4 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
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
              className="px-5 py-2.5 rounded-lg bg-[var(--nora-pink)] text-white font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
            >
              Weiter
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
