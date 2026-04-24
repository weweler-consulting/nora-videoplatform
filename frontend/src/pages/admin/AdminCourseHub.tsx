// frontend/src/pages/admin/AdminCourseHub.tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { hubApi, HubPayload, HeroVariant } from '../../lib/api/hub';

const EMPTY: HubPayload = {
  hero_variant: 'berry', hero_eyebrow: '', hero_title_html: '', hero_body: '',
  contact_user_id: null, contact_name_override: '',
  contact_role: 'Kursleitung & Ernährungsberaterin',
  contact_email_override: '', contact_whatsapp_url: '', contact_photo_url: '',
  show_contact: true, show_live_calls: true, show_products: true, show_downloads: true,
  links: [], live_calls: [], products: [], downloads: [],
};

export default function AdminCourseHub() {
  const { courseId } = useParams<{ courseId: string }>();
  const nav = useNavigate();
  const [hub, setHub] = useState<HubPayload>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    if (!courseId) return;
    hubApi.getAdmin(courseId).then(setHub).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [courseId]);

  const save = async () => {
    if (!courseId) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await hubApi.save(courseId, hub);
      setHub(saved);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={{ padding: 20 }}>Lädt …</div>;

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <button onClick={() => nav(`/admin/course/${courseId}`)} style={{
          background: 'transparent', border: 'none', color: 'var(--berry)', cursor: 'pointer',
          fontSize: 13, fontWeight: 700,
        }}>← Zurück zum Kurs</button>
        <h1 style={{ fontSize: 18, textTransform: 'uppercase', letterSpacing: '-0.3px' }}>
          Mitgliederbereich bearbeiten
        </h1>
      </div>

      {error && <div style={{
        padding: 12, background: '#fde7e7', color: '#8b0000',
        borderRadius: 8, marginBottom: 16,
      }}>{error}</div>}

      <HeroSection hub={hub} setHub={setHub} />

      {/* Contact, Links, LiveCalls, Products, Downloads come in Task 15 */}

      <div style={{
        display: 'flex', gap: 12, justifyContent: 'flex-end',
        marginTop: 32, position: 'sticky', bottom: 0,
        background: 'var(--cream)', padding: '16px 0', borderTop: '1px solid var(--coco)',
      }}>
        <button onClick={() => nav(`/admin/course/${courseId}`)} disabled={saving} style={{
          padding: '10px 24px', borderRadius: 'var(--radius-pill)',
          background: 'transparent', border: '1.5px solid var(--coco)',
          color: 'var(--soy)', cursor: 'pointer', fontWeight: 700,
        }}>Verwerfen</button>
        <button onClick={save} disabled={saving} style={{
          padding: '10px 24px', borderRadius: 'var(--radius-pill)',
          background: savedFlash ? 'var(--green)' : 'var(--berry)',
          color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700,
        }}>{saving ? 'Speichert …' : savedFlash ? '✓ Gespeichert' : 'Speichern'}</button>
      </div>
    </div>
  );
}

function HeroSection({
  hub, setHub,
}: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const update = <K extends keyof HubPayload>(k: K, v: HubPayload[K]) =>
    setHub({ ...hub, [k]: v });
  return (
    <FormSection title="Hero">
      <Label>Farbvariante</Label>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['berry', 'dark', 'pale'] as HeroVariant[]).map(v => (
          <button key={v} onClick={() => update('hero_variant', v)} style={{
            padding: '8px 16px', borderRadius: 'var(--radius-pill)',
            border: `1.5px solid ${hub.hero_variant === v ? 'var(--berry)' : 'var(--coco)'}`,
            background: hub.hero_variant === v ? 'var(--berry-pale)' : 'transparent',
            color: hub.hero_variant === v ? 'var(--berry)' : 'var(--soy)',
            cursor: 'pointer', fontWeight: 700, textTransform: 'uppercase', fontSize: 11,
          }}>
            {v === 'berry' ? 'Berry' : v === 'dark' ? 'Dunkel' : 'Rosé'}
          </button>
        ))}
      </div>
      <Label>Eyebrow</Label>
      <TextInput value={hub.hero_eyebrow} onChange={v => update('hero_eyebrow', v)}
                 placeholder="KURS · GLUKOSE BALANCE APRIL 2026" />
      <Label>Titel (HTML: &lt;em&gt;, &lt;br&gt; erlaubt)</Label>
      <TextArea rows={3} value={hub.hero_title_html} onChange={v => update('hero_title_html', v)}
                placeholder="Willkommen in Deinem<br>persönlichen <em>Mitgliederbereich</em>" />
      <Label>Fließtext</Label>
      <TextArea rows={3} value={hub.hero_body} onChange={v => update('hero_body', v)}
                placeholder="Hier findest Du alle relevanten Links …" />
    </FormSection>
  );
}

// --- Shared tiny form primitives (also used by later sections) ---
export function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{
      background: 'var(--white)', borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--coco)', padding: '20px 24px', marginBottom: 20,
    }}>
      <h2 style={{
        fontSize: 14, textTransform: 'uppercase', letterSpacing: '2px',
        color: 'var(--berry)', fontWeight: 700, marginBottom: 16,
      }}>{title}</h2>
      {children}
    </section>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return <div style={{
    fontSize: 11, fontWeight: 700, color: 'rgba(48,48,48,0.6)',
    textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, marginTop: 4,
  }}>{children}</div>;
}

export function TextInput({ value, onChange, placeholder }:
  { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
    style={inputBase} />;
}

export function TextArea({ value, onChange, rows = 3, placeholder }:
  { value: string; onChange: (v: string) => void; rows?: number; placeholder?: string }) {
  return <textarea value={value} onChange={e => onChange(e.target.value)} rows={rows}
    placeholder={placeholder} style={{ ...inputBase, fontFamily: 'inherit', resize: 'vertical' }} />;
}

export function Checkbox({ checked, onChange, label }:
  { checked: boolean; onChange: (b: boolean) => void; label: string }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 12 }}>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span style={{ fontSize: 13 }}>{label}</span>
    </label>
  );
}

const inputBase: React.CSSProperties = {
  width: '100%', padding: '9px 12px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--coco)', fontSize: 14, marginBottom: 12,
  background: 'var(--white)', fontFamily: 'var(--font-sans)',
  outline: 'none',
};
