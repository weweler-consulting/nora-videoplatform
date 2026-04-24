import { HubLink, IconType } from '../../../lib/api/hub';

function Icon({ type }: { type: IconType }) {
  const c = 'var(--berry)';
  const s = 20;
  const common = {
    width: s, height: s, viewBox: '0 0 24 24',
    fill: 'none', stroke: c, strokeWidth: 1.8,
    strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
  };
  if (type === 'book') return (<svg {...common}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>);
  if (type === 'video') return (<svg {...common}><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>);
  if (type === 'cal') return (<svg {...common}><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>);
  if (type === 'wa') return (<svg width={s} height={s} viewBox="0 0 24 24" fill={c}><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>);
  return (<svg {...common}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>);
}

export default function HubLinks({ links }: { links: HubLink[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <SectionLabel>Wichtige Links für Dich</SectionLabel>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {links.map(link => {
          const disabled = !link.url;
          const content = (
            <div style={{
              flex: '1 1 160px', display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: 10, padding: '22px 16px',
              background: 'var(--white)',
              border: '1.5px solid var(--coco)',
              borderRadius: 'var(--radius-lg)',
              textAlign: 'center',
              opacity: disabled ? 0.55 : 1,
              boxShadow: 'var(--shadow-card)',
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'var(--berry-pale)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon type={link.icon_type} />
              </div>
              <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--soy)', lineHeight: 1.3 }}>
                {link.label}
              </div>
              {link.sublabel && (
                <div style={{ fontSize: 11.5, color: 'rgba(48,48,48,0.5)', marginTop: 3 }}>
                  {link.sublabel}
                </div>
              )}
            </div>
          );
          return disabled ? (
            <div key={link.id || link.label} title="Link wird vorbereitet"
                 style={{ flex: '1 1 160px' }}>{content}</div>
          ) : (
            <a key={link.id || link.url} href={link.url} target="_blank" rel="noopener"
               style={{ flex: '1 1 160px', textDecoration: 'none' }}>{content}</a>
          );
        })}
      </div>
    </section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
      letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
    }}>{children}</div>
  );
}
