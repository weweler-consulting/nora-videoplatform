import { downloadHubFile } from '../../../lib/api/hub';
import type { HubDownload } from '../../../lib/api/hub';

export default function HubDownloads({
  courseId, downloads,
}: {
  courseId: string; downloads: HubDownload[];
}) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Downloads</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {downloads.map(dl => (
          <div key={dl.id || dl.file_name} style={{
            background: 'var(--white)', border: '1px solid var(--coco)',
            borderRadius: 'var(--radius-lg)',
            display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px',
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: 10,
              background: 'var(--berry-pale)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--berry)', fontWeight: 800, fontSize: 11,
            }}>PDF</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--soy)' }}>{dl.title}</div>
              {dl.description && <div style={{
                fontSize: 12.5, color: 'rgba(48,48,48,0.55)', lineHeight: 1.5,
              }}>{dl.description}</div>}
            </div>
            <button onClick={() => {
              if (dl.id) downloadHubFile(courseId, dl.id, dl.file_name);
            }} style={{
              padding: '7px 16px', borderRadius: 'var(--radius-pill)',
              background: 'transparent', border: '1px solid var(--berry)',
              color: 'var(--berry)', fontWeight: 700, fontSize: 12, cursor: 'pointer',
            }}>Download</button>
          </div>
        ))}
      </div>
    </section>
  );
}
