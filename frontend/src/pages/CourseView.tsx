import { useEffect, useState } from 'react';
import { useSearchParams, useParams } from 'react-router-dom';
import { api, type CourseDetail } from '../lib/api';
import CourseLessons from './course/CourseLessons';
import HubView from './course/hub/HubView';

export default function CourseView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { courseId } = useParams();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!courseId) return;
    setLoading(true);
    api.getCourse(courseId)
      .then(setCourse)
      .catch(() => setCourse(null))
      .finally(() => setLoading(false));
  }, [courseId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!course) {
    return <div className="p-4 md:p-8 text-gray-500">Kurs nicht gefunden.</div>;
  }

  if (!course.hub_enabled) {
    return <CourseLessons course={course} />;
  }

  const tab = searchParams.get('tab') === 'lessons' ? 'lessons' : 'hub';

  const setTab = (t: 'hub' | 'lessons') => {
    const next = new URLSearchParams(searchParams);
    if (t === 'hub') next.delete('tab'); else next.set('tab', t);
    setSearchParams(next, { replace: false });
  };

  return (
    <div>
      <div className="flex gap-1 border-b border-[var(--coco)] mb-4 md:mb-6 px-4 md:px-8 overflow-x-auto">
        <TabButton active={tab === 'hub'} onClick={() => setTab('hub')}>
          Mitgliederbereich
        </TabButton>
        <TabButton active={tab === 'lessons'} onClick={() => setTab('lessons')}>
          Inhalte
        </TabButton>
      </div>
      {tab === 'hub' ? (
        <HubView courseId={courseId!} />
      ) : (
        <CourseLessons course={course} />
      )}
    </div>
  );
}

function TabButton({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 md:px-5 py-3 bg-transparent border-0 border-b-2 text-xs md:text-sm font-bold uppercase tracking-wide cursor-pointer whitespace-nowrap transition-colors ${
        active
          ? 'border-[var(--berry)] text-[var(--berry)]'
          : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--berry)]'
      }`}
      style={{ fontFamily: 'var(--font-sans)' }}
    >
      {children}
    </button>
  );
}
