export default function HubContact({
  name, role, email, whatsappUrl, photoUrl,
}: {
  name: string; role: string; email: string; whatsappUrl: string; photoUrl: string;
}) {
  if (!name && !email && !whatsappUrl) return null;
  return (
    <section style={{ marginBottom: 36 }}>
      <div style={{
        fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '3px', color: 'var(--berry)', marginBottom: 18,
      }}>Deine Ansprechpartnerin</div>
      <div style={{
        background: 'var(--white)', border: '1px solid var(--coco)',
        borderRadius: 'var(--radius-lg)', padding: '20px 22px',
        display: 'flex', alignItems: 'center', gap: 16, maxWidth: 440,
      }}>
        {photoUrl
          ? <img src={photoUrl} alt={name}
                 style={{ width: 50, height: 50, borderRadius: '50%', objectFit: 'cover' }} />
          : <div style={{
              width: 50, height: 50, borderRadius: '50%', background: 'var(--berry)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 800,
            }}>{(name || '?').slice(0, 2).toUpperCase()}</div>}
        <div style={{ flex: 1 }}>
          {name && <div style={{
            fontWeight: 800, fontSize: 14, textTransform: 'uppercase',
            color: 'var(--soy)',
          }}>{name}</div>}
          {role && <div style={{
            fontSize: 12, color: 'rgba(48,48,48,0.55)', marginTop: 3, marginBottom: 12,
          }}>{role}</div>}
          <div style={{ display: 'flex', gap: 8 }}>
            {email && <a href={`mailto:${email}`} style={pillStyle}>E-Mail</a>}
            {whatsappUrl && <a href={whatsappUrl} target="_blank" rel="noopener" style={pillStyle}>
              WhatsApp
            </a>}
          </div>
        </div>
      </div>
    </section>
  );
}

const pillStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 16px', borderRadius: 'var(--radius-pill)',
  background: 'transparent', color: 'var(--berry)',
  border: '1px solid var(--berry-pale)',
  fontSize: 12, fontWeight: 700, textDecoration: 'none',
} as const;
