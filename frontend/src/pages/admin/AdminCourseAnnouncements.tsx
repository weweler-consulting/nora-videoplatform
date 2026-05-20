import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Megaphone } from 'lucide-react';
import { api, type AnnouncementItem, type CourseDetail } from '../../lib/api';
import AnnouncementComposeModal from '../../components/AnnouncementComposeModal';

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'gerade eben';
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `vor ${days} ${days === 1 ? 'Tag' : 'Tagen'}`;
  return new Date(iso).toLocaleDateString('de-DE');
}

export default function AdminCourseAnnouncements() {
  const { courseId } = useParams<{ courseId: string }>();
  const [items, setItems] = useState<AnnouncementItem[]>([]);
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [composeOpen, setComposeOpen] = useState(false);

  const load = () => {
    if (!courseId) return;
    setLoading(true);
    Promise.all([api.listAnnouncements(courseId), api.getAdminCourse(courseId)])
      .then(([list, c]) => {
        setItems(list);
        setCourse(c);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [courseId]);

  if (loading || !course || !courseId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/admin/courses" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Kurse
        </Link>
        <span>/</span>
        <Link
          to={`/admin/course/${courseId}`}
          className="hover:text-[var(--nora-pink-dark)] transition-colors"
        >
          {course.title}
        </Link>
        <span>/</span>
        <span className="text-gray-700">Ankündigungen</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Megaphone size={20} className="text-[var(--nora-pink)]" />
            Ankündigungen
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Informiere Klientinnen per E-Mail über neue Module oder Lektionen.
          </p>
        </div>
        <button
          onClick={() => setComposeOpen(true)}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors shrink-0"
        >
          + Neue Ankündigung
        </button>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-2xl p-12 text-center text-gray-500">
          Noch keine Ankündigungen verschickt.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((a) => (
            <div key={a.id} className="bg-white rounded-2xl p-5 shadow-sm">
              <div className="flex items-start justify-between mb-2 gap-4">
                <div className="font-medium text-gray-800">{a.subject}</div>
                <div className="text-xs text-gray-500 whitespace-nowrap shrink-0">
                  {formatRelative(a.sent_at)}
                </div>
              </div>
              <div className="text-sm text-gray-600 mb-2">
                {a.target_type === 'module'
                  ? `Modul: ${a.target_title ?? '(gelöscht)'}`
                  : `Lektion: ${a.target_module_title ?? '?'} – ${a.target_title ?? '(gelöscht)'}`}
              </div>
              <div className="text-xs text-gray-500">
                Versendet an {a.recipient_count}{' '}
                {a.recipient_count === 1 ? 'Teilnehmerin' : 'Teilnehmerinnen'}
                {a.created_by ? ` · von ${a.created_by.name}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      <AnnouncementComposeModal
        courseId={courseId}
        course={course}
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onSent={() => {
          load();
        }}
      />
    </div>
  );
}
