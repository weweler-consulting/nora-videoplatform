import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type CourseDetail } from '../../lib/api';

export default function AdminCourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const load = () => {
    if (courseId) {
      api.getAdminCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  };

  useEffect(load, [courseId]);

  const handleCreateModule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !courseId) return;
    const sortOrder = course ? course.modules.length : 0;

    // Create module
    const { id: moduleId } = await api.createModule({
      course_id: courseId,
      title: newTitle,
      sort_order: sortOrder,
    });

    // Auto-create a default section so lessons can be added directly
    await api.createSection({
      module_id: moduleId,
      title: 'Lektionen',
      sort_order: 0,
    });

    setNewTitle('');
    setShowCreate(false);
    load();
  };

  const handleDeleteModule = async (moduleId: string, title: string) => {
    if (!confirm(`Modul "${title}" wirklich loschen?`)) return;
    await api.deleteModule(moduleId);
    load();
  };

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
        <Link to="/admin" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Kurse
        </Link>
        <span>/</span>
        <span className="text-gray-700">{course.title}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">{course.title}</h2>
          {course.description && (
            <p className="text-gray-500 mt-1">{course.description}</p>
          )}
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Neues Modul
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreateModule} className="bg-white rounded-2xl p-6 mb-6 shadow-sm space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Modulname</label>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              placeholder="z.B. Modul 1 | Einfuhrung"
              autoFocus
            />
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
            >
              Erstellen
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-5 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </form>
      )}

      {course.modules.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          Noch keine Module. Erstelle dein erstes Modul.
        </div>
      ) : (
        <div className="space-y-3">
          {course.modules.map((module, idx) => {
            const lessonCount = module.sections.reduce((sum, s) => sum + s.lessons.length, 0);
            return (
              <div
                key={module.id}
                className="bg-white rounded-2xl p-5 shadow-sm flex items-center justify-between group"
              >
                <Link
                  to={`/admin/course/${courseId}/module/${module.id}`}
                  className="flex-1 min-w-0 flex items-center gap-4"
                >
                  <div className="w-10 h-10 bg-gradient-to-br from-[var(--nora-pink-light)] to-[var(--nora-pink)] rounded-lg flex items-center justify-center text-white font-semibold text-sm shrink-0">
                    {idx + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-800 group-hover:text-[var(--nora-pink-dark)] transition-colors">
                      {module.title}
                    </h3>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {lessonCount} Lektionen · {module.total_duration} Min.
                    </p>
                  </div>
                </Link>
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <Link
                    to={`/admin/course/${courseId}/module/${module.id}`}
                    className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    Bearbeiten
                  </Link>
                  <button
                    onClick={() => handleDeleteModule(module.id, module.title)}
                    className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                  >
                    Loschen
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
