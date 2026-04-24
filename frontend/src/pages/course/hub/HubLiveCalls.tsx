import { HubLiveCall } from '../../../lib/api/hub';

export default function HubLiveCalls({ calls }: { calls: HubLiveCall[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Live Calls</div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {calls.map(call => (
          <div key={call.id || call.title} style={{
            background: 'var(--white)', border: '1px solid var(--coco)',
            borderTop: '3px solid var(--berry)',
            borderRadius: 'var(--radius-lg)', padding: '20px 22px',
            flex: '1 1 260px',
          }}>
            {call.tag && <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '2.5px',
              color: 'var(--berry)', textTransform: 'uppercase', marginBottom: 8,
            }}>{call.tag}</div>}
            <div style={{ fontWeight: 700, fontSize: 14.5, color: 'var(--soy)', marginBottom: 8 }}>
              {call.title}
            </div>
            {call.body && <div style={{
              fontSize: 13, color: 'rgba(48,48,48,0.65)', lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
            }}>{call.body}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}
