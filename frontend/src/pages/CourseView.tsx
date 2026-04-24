import { useSearchParams, useParams } from 'react-router-dom';
import CourseLessons from './course/CourseLessons';
import HubView from './course/hub/HubView';

export default function CourseView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { courseId } = useParams();
  const tab = searchParams.get('tab') === 'lessons' ? 'lessons' : 'hub';

  const setTab = (t: 'hub' | 'lessons') => {
    const next = new URLSearchParams(searchParams);
    if (t === 'hub') next.delete('tab'); else next.set('tab', t);
    setSearchParams(next, { replace: false });
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 8,
          borderBottom: '1px solid var(--coco)',
          marginBottom: 24,
        }}
      >
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
        <CourseLessons />
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
      style={{
        padding: '12px 20px',
        background: 'transparent',
        border: 'none',
        borderBottom: `2px solid ${active ? 'var(--berry)' : 'transparent'}`,
        color: active ? 'var(--berry)' : 'var(--color-text-secondary)',
        fontFamily: 'var(--font-sans)',
        fontSize: 14,
        fontWeight: 700,
        letterSpacing: '0.3px',
        cursor: 'pointer',
        textTransform: 'uppercase',
      }}
    >
      {children}
    </button>
  );
}
