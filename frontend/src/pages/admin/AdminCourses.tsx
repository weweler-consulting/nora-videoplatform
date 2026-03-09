import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type CourseListItem } from '../../lib/api';

export default function AdminCourses() {
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const load = () => {
    api.getAllCourses().then(setCourses).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    await api.createCourse({ title: newTitle, description: newDesc || undefined });
    setNewTitle('');
    setNewDesc('');
    setShowCreate(false);
    load();
  };

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Kurs "${title}" wirklich löschen?`)) return;
    await api.deleteCourse(id);
    load();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Kurse verwalten</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Neuer Kurs
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-white rounded-2xl p-6 mb-6 shadow-sm space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Kursname</label>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              placeholder="z.B. Vibe-Coden"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Beschreibung (optional)</label>
            <textarea
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
              rows={2}
              placeholder="Worum geht es in dem Kurs?"
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

      {courses.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          Noch keine Kurse vorhanden. Erstelle deinen ersten Kurs.
        </div>
      ) : (
        <div className="space-y-3">
          {courses.map((course) => (
            <div
              key={course.id}
              className="bg-white rounded-2xl p-5 shadow-sm flex items-center justify-between group"
            >
              <Link
                to={`/admin/course/${course.id}`}
                className="flex-1 min-w-0"
              >
                <h3 className="font-semibold text-gray-800 group-hover:text-[var(--nora-pink-dark)] transition-colors">
                  {course.title}
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  {course.total_lessons} Lektionen
                  {course.description && ` · ${course.description}`}
                </p>
              </Link>
              <div className="flex items-center gap-2 shrink-0 ml-4">
                <Link
                  to={`/admin/course/${course.id}`}
                  className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Bearbeiten
                </Link>
                <button
                  onClick={() => handleDelete(course.id, course.title)}
                  className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                >
                  Löschen
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
