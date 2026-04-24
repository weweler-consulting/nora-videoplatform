import type { HeroVariant } from '../../../lib/api/hub';

const GRADIENTS: Record<HeroVariant, string> = {
  berry: 'var(--gradient-berry)',
  dark: 'var(--gradient-dark)',
  pale: 'var(--gradient-pale)',
};

export default function HubHero({
  variant, eyebrow, titleHtml, body,
  contactName, contactRole, contactPhotoUrl,
}: {
  variant: HeroVariant;
  eyebrow: string;
  titleHtml: string;
  body: string;
  contactName: string;
  contactRole: string;
  contactPhotoUrl: string;
}) {
  const dark = variant !== 'pale';
  return (
    <div style={{
      background: GRADIENTS[variant],
      borderRadius: 'var(--radius-xl)',
      padding: '32px 36px',
      marginBottom: 36,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 20,
    }}>
      <div style={{ maxWidth: 520 }}>
        {eyebrow && (
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '3px',
            textTransform: 'uppercase',
            color: dark ? 'rgba(255,255,255,0.65)' : 'var(--berry)',
            marginBottom: 10,
          }}>{eyebrow}</div>
        )}
        {titleHtml && (
          <h2
            style={{
              fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 'clamp(18px,2.5vw,28px)',
              textTransform: 'uppercase', letterSpacing: '-0.3px',
              color: dark ? '#fff' : 'var(--soy)',
              lineHeight: 1.15, marginBottom: 12,
            }}
            // Safe: backend _sanitize_html bleach-cleans hero_title_html on save (Task 9)
            dangerouslySetInnerHTML={{ __html: titleHtml }}
          />
        )}
        {body && (
          <p style={{
            fontSize: 14, lineHeight: 1.65,
            color: dark ? 'rgba(255,255,255,0.8)' : 'var(--color-text-secondary)',
          }}>{body}</p>
        )}
      </div>
      {(contactName || contactPhotoUrl) && (
        <div style={{
          flexShrink: 0,
          background: dark ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.6)',
          borderRadius: 14, padding: '18px 22px', textAlign: 'center',
          border: `1px solid ${dark ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.9)'}`,
        }}>
          {contactPhotoUrl && (
            <img src={contactPhotoUrl} alt={contactName} style={{
              width: 56, height: 56, borderRadius: '50%', objectFit: 'cover',
            }} />
          )}
          <div style={{
            marginTop: 10, fontWeight: 800, fontSize: 13,
            textTransform: 'uppercase',
            color: dark ? '#fff' : 'var(--soy)',
          }}>{contactName}</div>
          {contactRole && (
            <div style={{
              fontSize: 11, marginTop: 3,
              color: dark ? 'rgba(255,255,255,0.65)' : 'rgba(48,48,48,0.55)',
            }}>{contactRole}</div>
          )}
        </div>
      )}
    </div>
  );
}
