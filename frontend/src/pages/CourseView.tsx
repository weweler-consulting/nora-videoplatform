import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type CourseDetail, type ModuleItem } from '../lib/api';

function ModuleCard({ module, courseId }: { module: ModuleItem; courseId: string }) {
  const [expanded, setExpanded] = useState(false);
  const percent = module.total_lessons > 0
    ? Math.round((module.completed_lessons / module.total_lessons) * 100)
    : 0;

  return (
    <div className={`bg-white rounded-2xl shadow-sm overflow-hidden ${module.is_locked ? 'opacity-60' : ''}`}>
      {/* Module header */}
      <button
        onClick={() => !module.is_locked && setExpanded(!expanded)}
        className={`w-full text-left p-5 flex items-center gap-5 transition-colors ${module.is_locked ? 'cursor-default' : 'hover:bg-gray-50'}`}
      >
        {module.image_url ? (
          <img src={module.image_url} alt="" className="w-20 h-14 object-cover rounded-lg shrink-0" />
        ) : (
          <div className="w-20 h-14 bg-gradient-to-br from-[var(--nora-pink-light)] to-[var(--nora-pink)] rounded-lg shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-800">{module.title}</h3>
          <p className="text-sm text-gray-500">
            {module.is_locked
              ? `Verfügbar ab ${module.unlocks_at}`
              : <>{module.total_lessons} Lektionen{module.total_duration > 0 ? ` | ${module.total_duration} Min.` : ''}</>
            }
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-3">
          {module.is_locked ? (
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          ) : (
            <>
              <span className="text-sm font-semibold text-[var(--nora-pink-dark)]">{percent}%</span>
              <svg
                className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </>
          )}
        </div>
      </button>

      {/* Expanded sections & lessons */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5">
          {module.sections.map((section) => (
            <div key={section.id} className="mt-4">
              <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                {section.title}
              </h4>
              <div className="space-y-1">
                {section.lessons.map((lesson) => (
                  <Link
                    key={lesson.id}
                    to={`/course/${courseId}/lesson/${lesson.id}`}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[var(--nora-pink-light)] transition-colors group"
                  >
                    {/* Completion indicator */}
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                      lesson.completed
                        ? 'bg-green-100 text-green-600'
                        : 'bg-gray-100 text-gray-400'
                    }`}>
                      {lesson.completed ? (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                        </svg>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-700 group-hover:text-[var(--nora-pink-dark)] transition-colors">
                        {lesson.title}
                      </p>
                    </div>

                    {lesson.duration_minutes > 0 && (
                      <span className="text-xs text-gray-400 shrink-0">
                        {lesson.duration_minutes} Min.
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CourseView() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (courseId) {
      api.getCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  }, [courseId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!course) {
    return <div className="p-8 text-gray-500">Kurs nicht gefunden.</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Meine Kurse
        </Link>
        <span>/</span>
        <span className="text-gray-700">{course.title}</span>
      </div>

      {/* Course header */}
      <div className="bg-gradient-to-r from-[var(--nora-pink)] to-[var(--nora-pink-dark)] rounded-2xl p-8 mb-8 flex items-center justify-between text-white">
        <div>
          <p className="text-sm opacity-80 uppercase tracking-wider">Kurs</p>
          <h2 className="text-2xl font-semibold mt-1">{course.title}</h2>
          {course.description && (
            <p className="mt-2 opacity-90">{course.description}</p>
          )}
        </div>
        <div className="shrink-0">
          <svg width="80" height="80" className="transform -rotate-90">
            <circle cx="40" cy="40" r="34" stroke="rgba(255,255,255,0.3)" strokeWidth="6" fill="none" />
            <circle
              cx="40" cy="40" r="34"
              stroke="white" strokeWidth="6" fill="none"
              strokeDasharray={2 * Math.PI * 34}
              strokeDashoffset={2 * Math.PI * 34 - (course.progress_percent / 100) * 2 * Math.PI * 34}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
            <text
              x="50%" y="50%"
              dominantBaseline="central" textAnchor="middle"
              className="text-lg font-bold fill-white"
              transform="rotate(90, 40, 40)"
            >
              {course.progress_percent}%
            </text>
          </svg>
        </div>
      </div>

      {/* Modules */}
      <h3 className="text-lg font-semibold mb-4">Module</h3>
      <div className="space-y-4">
        {course.modules.map((module) => (
          <ModuleCard key={module.id} module={module} courseId={course.id} />
        ))}
      </div>
    </div>
  );
}
