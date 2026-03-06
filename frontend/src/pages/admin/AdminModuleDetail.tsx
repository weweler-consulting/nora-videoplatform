import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type CourseDetail, type LessonItem } from '../../lib/api';

export default function AdminModuleDetail() {
  const { courseId, moduleId } = useParams<{ courseId: string; moduleId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formVideoUrl, setFormVideoUrl] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formDuration, setFormDuration] = useState(0);

  const load = () => {
    if (courseId) {
      api.getAdminCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  };

  useEffect(load, [courseId]);

  const module = course?.modules.find((m) => m.id === moduleId);

  // Flatten lessons from all sections (admin sees flat list)
  const allLessons: (LessonItem & { sectionId: string })[] = [];
  if (module) {
    for (const section of module.sections) {
      for (const lesson of section.lessons) {
        allLessons.push({ ...lesson, sectionId: section.id });
      }
    }
  }

  // Get default section id (first section)
  const defaultSectionId = module?.sections[0]?.id;

  const resetForm = () => {
    setFormTitle('');
    setFormVideoUrl('');
    setFormDescription('');
    setFormDuration(0);
    setShowCreate(false);
    setEditingId(null);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim() || !defaultSectionId) return;
    await api.createLesson({
      section_id: defaultSectionId,
      title: formTitle,
      description: formDescription || undefined,
      video_url: formVideoUrl || undefined,
      duration_minutes: formDuration,
      sort_order: allLessons.length,
    });
    resetForm();
    load();
  };

  const handleStartEdit = (lesson: LessonItem) => {
    setEditingId(lesson.id);
    setFormTitle(lesson.title);
    setFormVideoUrl(lesson.video_url || '');
    setFormDescription(lesson.description || '');
    setFormDuration(lesson.duration_minutes);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId || !formTitle.trim()) return;
    await api.updateLesson(editingId, {
      title: formTitle,
      video_url: formVideoUrl || null,
      description: formDescription || null,
      duration_minutes: formDuration,
    });
    resetForm();
    load();
  };

  const handleDelete = async (lessonId: string, title: string) => {
    if (!confirm(`Lektion "${title}" wirklich loschen?`)) return;
    await api.deleteLesson(lessonId);
    load();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!course || !module) {
    return <div className="p-8 text-gray-500">Modul nicht gefunden.</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/admin" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Kurse
        </Link>
        <span>/</span>
        <Link to={`/admin/course/${courseId}`} className="hover:text-[var(--nora-pink-dark)] transition-colors">
          {course.title}
        </Link>
        <span>/</span>
        <span className="text-gray-700">{module.title}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">{module.title}</h2>
        <button
          onClick={() => { resetForm(); setShowCreate(true); }}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Neue Lektion
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <LessonForm
          title={formTitle}
          videoUrl={formVideoUrl}
          description={formDescription}
          duration={formDuration}
          onTitleChange={setFormTitle}
          onVideoUrlChange={setFormVideoUrl}
          onDescriptionChange={setFormDescription}
          onDurationChange={setFormDuration}
          onSubmit={handleCreate}
          onCancel={resetForm}
          submitLabel="Erstellen"
        />
      )}

      {/* Lessons list */}
      {allLessons.length === 0 && !showCreate ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          Noch keine Lektionen. Erstelle deine erste Lektion.
        </div>
      ) : (
        <div className="space-y-3">
          {allLessons.map((lesson, idx) => (
            <div key={lesson.id}>
              {editingId === lesson.id ? (
                <LessonForm
                  title={formTitle}
                  videoUrl={formVideoUrl}
                  description={formDescription}
                  duration={formDuration}
                  onTitleChange={setFormTitle}
                  onVideoUrlChange={setFormVideoUrl}
                  onDescriptionChange={setFormDescription}
                  onDurationChange={setFormDuration}
                  onSubmit={handleSaveEdit}
                  onCancel={resetForm}
                  submitLabel="Speichern"
                />
              ) : (
                <div className="bg-white rounded-2xl p-5 shadow-sm group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-sm font-medium text-gray-500 shrink-0">
                        {idx + 1}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-medium text-gray-800">{lesson.title}</h3>
                        <div className="flex items-center gap-3 mt-1">
                          {lesson.video_url && (
                            <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                              </svg>
                              Video
                            </span>
                          )}
                          {lesson.description && (
                            <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                              Text
                            </span>
                          )}
                          <span className="text-xs text-gray-400">{lesson.duration_minutes} Min.</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      <button
                        onClick={() => handleStartEdit(lesson)}
                        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                      >
                        Bearbeiten
                      </button>
                      <button
                        onClick={() => handleDelete(lesson.id, lesson.title)}
                        className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                      >
                        Loschen
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LessonForm({
  title, videoUrl, description, duration,
  onTitleChange, onVideoUrlChange, onDescriptionChange, onDurationChange,
  onSubmit, onCancel, submitLabel,
}: {
  title: string;
  videoUrl: string;
  description: string;
  duration: number;
  onTitleChange: (v: string) => void;
  onVideoUrlChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onDurationChange: (v: number) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  return (
    <form onSubmit={onSubmit} className="bg-white rounded-2xl p-6 mb-3 shadow-sm space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Titel</label>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          placeholder="z.B. Willkommen zum Kurs"
          autoFocus
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Video-URL (Embed-Link)</label>
        <input
          type="url"
          value={videoUrl}
          onChange={(e) => onVideoUrlChange(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          placeholder="https://iframe.mediadelivery.net/embed/..."
        />
        <p className="text-xs text-gray-400 mt-1">Bunny.net, Vimeo oder YouTube Embed-URL</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Text unterhalb des Videos</label>
        <textarea
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          rows={4}
          placeholder="Beschreibung, Zusammenfassung oder Notizen zur Lektion..."
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Dauer (Minuten)</label>
        <input
          type="number"
          value={duration}
          onChange={(e) => onDurationChange(parseInt(e.target.value) || 0)}
          className="w-32 px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          min={0}
        />
      </div>
      <div className="flex gap-3">
        <button
          type="submit"
          className="px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          {submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Abbrechen
        </button>
      </div>
    </form>
  );
}
