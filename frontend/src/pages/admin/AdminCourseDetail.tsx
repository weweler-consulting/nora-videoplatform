import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type CourseDetail, type ModuleItem } from '../../lib/api';

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
    if (!confirm(`Modul "${title}" wirklich löschen?`)) return;
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
        <Link to="/admin/courses" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Kurse
        </Link>
        <span>/</span>
        <span className="text-gray-700">{course.title}</span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div className="flex-1 min-w-0 mr-4">
          <EditableCourseField
            courseId={course.id}
            field="title"
            value={course.title}
            onSaved={load}
            renderDisplay={(val) => <h2 className="text-xl font-semibold">{val}</h2>}
            inputClassName="text-xl font-semibold w-full"
          />
          <EditableCourseField
            courseId={course.id}
            field="description"
            value={course.description || ''}
            onSaved={load}
            placeholder="Beschreibung hinzufügen..."
            renderDisplay={(val) => val ? <p className="text-gray-500 mt-1">{val}</p> : <p className="text-gray-400 mt-1 text-sm italic cursor-pointer">Beschreibung hinzufügen...</p>}
            inputClassName="text-gray-500 w-full"
          />
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Neues Modul
        </button>
      </div>

      {/* Stripe Product ID */}
      <StripeProductInput courseId={course.id} initial={course.stripe_product_id} />

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
                      {lessonCount} Lektionen{module.total_duration > 0 ? ` · ${module.total_duration} Min.` : ''}
                      {module.unlock_after_days > 0 && (
                        <span className="ml-2 text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
                          nach {module.unlock_after_days} Tagen
                        </span>
                      )}
                    </p>
                  </div>
                </Link>
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  <UnlockDaysInput module={module} onSave={load} />
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
                    Löschen
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

function StripeProductInput({ courseId, initial }: { courseId: string; initial: string | null }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initial || '');
  const [saved, setSaved] = useState(false);

  const save = async () => {
    await api.updateCourse(courseId, { stripe_product_id: value || null });
    setEditing(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!editing && !value) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 mb-6 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
        Stripe Product ID verknüpfen
      </button>
    );
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
        <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{value}</span>
        <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-gray-600">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
        </button>
        {saved && <span className="text-green-500 text-xs">Gespeichert</span>}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 mb-6">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && save()}
        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[var(--nora-pink)] font-mono w-72"
        placeholder="prod_..."
        autoFocus
      />
      <button onClick={save} className="px-3 py-1.5 text-sm bg-[var(--nora-pink)] text-white rounded-lg hover:bg-[var(--nora-pink-dark)] transition-colors">
        Speichern
      </button>
      <button onClick={() => { setValue(initial || ''); setEditing(false); }} className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-500 hover:bg-gray-50 transition-colors">
        Abbrechen
      </button>
    </div>
  );
}

function EditableCourseField({
  courseId,
  field,
  value,
  onSaved,
  placeholder,
  renderDisplay,
  inputClassName,
}: {
  courseId: string;
  field: 'title' | 'description';
  value: string;
  onSaved: () => void;
  placeholder?: string;
  renderDisplay: (val: string) => React.ReactNode;
  inputClassName?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const save = async () => {
    const trimmed = draft.trim();
    if (field === 'title' && !trimmed) {
      setDraft(value);
      setEditing(false);
      return;
    }
    if (trimmed !== value) {
      await api.updateCourse(courseId, { [field]: trimmed || null });
      onSaved();
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') save();
          if (e.key === 'Escape') { setDraft(value); setEditing(false); }
        }}
        className={`px-2 py-1 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent ${inputClassName || ''}`}
        placeholder={placeholder}
        autoFocus
      />
    );
  }

  return (
    <div
      onClick={() => { setDraft(value); setEditing(true); }}
      className="cursor-pointer group/edit"
      title="Klicken zum Bearbeiten"
    >
      <div className="flex items-center gap-2">
        <div className="flex-1">{renderDisplay(value)}</div>
        <svg className="w-3.5 h-3.5 text-gray-300 group-hover/edit:text-gray-500 transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      </div>
    </div>
  );
}

function UnlockDaysInput({ module, onSave }: { module: ModuleItem; onSave: () => void }) {
  const [editing, setEditing] = useState(false);
  const [days, setDays] = useState(module.unlock_after_days);

  const save = async () => {
    if (days !== module.unlock_after_days) {
      await api.updateModule(module.id, { unlock_after_days: days });
      onSave();
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          value={days || ''}
          onChange={(e) => setDays(parseInt(e.target.value) || 0)}
          onBlur={save}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          autoFocus
          className="w-16 px-2 py-1 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[var(--nora-pink)]"
          placeholder="0"
        />
        <span className="text-xs text-gray-400">Tage</span>
      </div>
    );
  }

  return (
    <button
      onClick={() => { setDays(module.unlock_after_days); setEditing(true); }}
      className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
      title="Verzögerung in Tagen nach Anmeldung"
    >
      {module.unlock_after_days > 0 ? `${module.unlock_after_days}d` : '⏱'}
    </button>
  );
}
