import { HubProduct } from '../../../lib/api/hub';

export default function HubProducts({ products }: { products: HubProduct[] }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Empfehlungen & Zusatzprodukte</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {products.map(p => (
          <div key={p.id || p.title} style={{
            background: p.highlight ? 'var(--gradient-berry)' : 'var(--white)',
            border: `1px solid ${p.highlight ? 'transparent' : 'var(--coco)'}`,
            borderRadius: 'var(--radius-xl)',
            display: 'flex', alignItems: 'stretch', overflow: 'hidden',
          }}>
            <div style={{
              width: 170, flexShrink: 0,
              background: p.highlight ? 'rgba(255,255,255,0.12)' : 'var(--berry-pale)',
              backgroundImage: p.image_url ? `url(${p.image_url})` : 'none',
              backgroundSize: 'cover', backgroundPosition: 'center',
              minHeight: 140,
            }} />
            <div style={{ padding: '22px 28px', flex: 1 }}>
              {p.label && <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '2.5px',
                textTransform: 'uppercase',
                color: p.highlight ? 'rgba(255,255,255,0.75)' : 'var(--berry)',
                marginBottom: 6,
              }}>{p.label}</div>}
              <div style={{
                fontWeight: 800, fontSize: 16, textTransform: 'uppercase',
                color: p.highlight ? '#fff' : 'var(--soy)', marginBottom: 8,
              }}>{p.title}</div>
              {p.description && <div style={{
                fontSize: 13.5, lineHeight: 1.6, marginBottom: 14,
                color: p.highlight ? 'rgba(255,255,255,0.82)' : 'rgba(48,48,48,0.65)',
              }}>{p.description}</div>}
              {p.url && (
                <a href={p.url} target="_blank" rel="noopener" style={{
                  display: 'inline-flex', gap: 6, padding: '7px 16px',
                  borderRadius: 'var(--radius-pill)',
                  background: p.highlight ? 'rgba(255,255,255,0.15)' : 'transparent',
                  color: p.highlight ? '#fff' : 'var(--berry)',
                  border: `1px solid ${p.highlight ? 'rgba(255,255,255,0.3)' : 'var(--berry)'}`,
                  fontSize: 12, fontWeight: 700, textDecoration: 'none',
                }}>{p.cta_text}</a>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
