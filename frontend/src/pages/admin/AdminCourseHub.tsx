// frontend/src/pages/admin/AdminCourseHub.tsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { hubApi } from '../../lib/api/hub';
import { api, type CourseListItem } from '../../lib/api';
import type {
  HubPayload, HeroVariant,
  HubLink as HubLinkType, HubLiveCall as LiveCallType,
  HubProduct as ProductType, HubDownload as DownloadType,
  IconType,
} from '../../lib/api/hub';

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
  const [otherCourses, setOtherCourses] = useState<CourseListItem[]>([]);
  const [copySource, setCopySource] = useState('');
  const [copying, setCopying] = useState(false);

  useEffect(() => {
    if (!courseId) return;
    hubApi.getAdmin(courseId).then(setHub).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [courseId]);

  useEffect(() => {
    if (!courseId) return;
    api.getAllCourses()
      .then((cs) => setOtherCourses(cs.filter((c) => c.id !== courseId)))
      .catch(() => { /* Vorlagen-Auswahl ist optional; Fehler hier ignorieren */ });
  }, [courseId]);

  const hubIsEmpty =
    hub.links.length === 0 && hub.live_calls.length === 0 && hub.products.length === 0;

  const copyFromCourse = async () => {
    if (!courseId || !copySource) return;
    if (!confirm('Hub aus dem gewählten Kurs übernehmen? Der aktuelle (leere) Hub wird damit befüllt.')) return;
    setCopying(true);
    setError(null);
    try {
      const copied = await hubApi.copyFrom(courseId, copySource);
      setHub(copied);
      setCopySource('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Übernahme fehlgeschlagen');
    } finally {
      setCopying(false);
    }
  };

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

      {hubIsEmpty && otherCourses.length > 0 && (
        <FormSection title="Aus anderem Kurs übernehmen">
          <p style={{ fontSize: 13, color: 'rgba(48,48,48,0.7)', marginBottom: 12 }}>
            Übernimmt Hero-Texte, Kontakt, Links, Live-Calls und Produkt-Texte aus einem
            bestehenden Kurs. Bilder &amp; PDF-Downloads werden nicht kopiert – bitte unten
            neu hochladen. Nur möglich, solange dieser Hub noch leer ist.
          </p>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              value={copySource}
              onChange={(e) => setCopySource(e.target.value)}
              disabled={copying}
              style={{ ...inputBase, marginBottom: 0, width: 'auto', flex: '1 1 240px' }}
            >
              <option value="">Quellkurs wählen …</option>
              {otherCourses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
            <button
              onClick={copyFromCourse}
              disabled={copying || !copySource}
              style={{
                padding: '10px 24px', borderRadius: 'var(--radius-pill)',
                background: 'var(--berry)', color: '#fff', border: 'none',
                cursor: copying || !copySource ? 'default' : 'pointer',
                fontWeight: 700, opacity: copying || !copySource ? 0.5 : 1,
              }}
            >{copying ? 'Übernimmt …' : 'Übernehmen'}</button>
          </div>
        </FormSection>
      )}

      <HeroSection hub={hub} setHub={setHub} />

      <ContactSection hub={hub} setHub={setHub} courseId={courseId!} />
      <LinksSection hub={hub} setHub={setHub} />
      <LiveCallsSection hub={hub} setHub={setHub} />
      <ProductsSection hub={hub} setHub={setHub} courseId={courseId!} />
      <DownloadsSection hub={hub} setHub={setHub} courseId={courseId!} />

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

// --- Shared list-item style constants ---
const smallRmBtn: React.CSSProperties = {
  background: 'transparent', border: 'none', color: 'var(--berry-dark)',
  cursor: 'pointer', fontSize: 12, textDecoration: 'underline',
};
const listItemStyle: React.CSSProperties = {
  border: '1px solid var(--coco)', borderRadius: 'var(--radius-md)',
  padding: '14px 16px', marginBottom: 10, background: 'var(--cream)',
};
const iconBtn: React.CSSProperties = {
  padding: '3px 10px', borderRadius: 8, border: '1px solid var(--coco)',
  background: 'var(--white)', cursor: 'pointer', fontSize: 12,
};
const addBtn: React.CSSProperties = {
  width: '100%', padding: 12, borderRadius: 'var(--radius-md)',
  border: '1.5px dashed var(--berry)', background: 'rgba(212,116,121,0.04)',
  color: 'var(--berry)', fontWeight: 700, cursor: 'pointer',
};

// --- Section components ---

function ContactSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const update = <K extends keyof HubPayload>(k: K, v: HubPayload[K]) =>
    setHub({ ...hub, [k]: v });
  const [uploading, setUploading] = useState(false);

  const handlePhotoUpload = async (file: File) => {
    setUploading(true);
    try {
      const { url } = await hubApi.uploadImage(courseId, 'contact_photo', file);
      update('contact_photo_url', url);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    } finally {
      setUploading(false);
    }
  };

  return (
    <FormSection title="Ansprechpartnerin">
      <Checkbox checked={hub.show_contact} onChange={v => update('show_contact', v)} label="Anzeigen" />
      <Label>Name (Override)</Label>
      <TextInput value={hub.contact_name_override}
                 onChange={v => update('contact_name_override', v)}
                 placeholder="Nora Weweler" />
      <Label>Rolle</Label>
      <TextInput value={hub.contact_role} onChange={v => update('contact_role', v)} />
      <Label>E-Mail (Override)</Label>
      <TextInput value={hub.contact_email_override}
                 onChange={v => update('contact_email_override', v)}
                 placeholder="hallo@noraweweler.de" />
      <Label>WhatsApp-URL</Label>
      <TextInput value={hub.contact_whatsapp_url}
                 onChange={v => update('contact_whatsapp_url', v)}
                 placeholder="https://wa.me/49..." />
      <Label>Foto</Label>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        {hub.contact_photo_url && (
          <img src={hub.contact_photo_url} alt=""
               style={{ width: 60, height: 60, borderRadius: '50%', objectFit: 'cover' }} />
        )}
        <input type="file" accept="image/jpeg,image/png,image/webp"
               disabled={uploading}
               onChange={e => e.target.files?.[0] && handlePhotoUpload(e.target.files[0])} />
        {hub.contact_photo_url && (
          <button onClick={() => update('contact_photo_url', '')} style={smallRmBtn}>entfernen</button>
        )}
      </div>
    </FormSection>
  );
}

function LinksSection({
  hub, setHub,
}: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const update = (idx: number, patch: Partial<HubLinkType>) => {
    const next = hub.links.map((l, i) => i === idx ? { ...l, ...patch } : l);
    setHub({ ...hub, links: next });
  };
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.links.length) return;
    const next = [...hub.links];
    [next[idx], next[t]] = [next[t], next[idx]];
    setHub({ ...hub, links: next.map((l, i) => ({ ...l, sort_order: i })) });
  };
  const add = () => setHub({
    ...hub,
    links: [...hub.links, {
      icon_type: 'link' as IconType, label: 'Neuer Link',
      sublabel: '', url: '', sort_order: hub.links.length,
    }],
  });
  const remove = (idx: number) =>
    setHub({ ...hub, links: hub.links.filter((_, i) => i !== idx) });

  return (
    <FormSection title="Wichtige Links">
      {hub.links.map((link, i) => (
        <div key={link.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Icon</Label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {(['book', 'video', 'wa', 'cal', 'link'] as IconType[]).map(t => (
              <button key={t} onClick={() => update(i, { icon_type: t })} style={{
                padding: '5px 12px', borderRadius: 'var(--radius-pill)',
                border: `1.5px solid ${link.icon_type === t ? 'var(--berry)' : 'var(--coco)'}`,
                background: link.icon_type === t ? 'var(--berry-pale)' : 'transparent',
                color: link.icon_type === t ? 'var(--berry)' : 'var(--soy)',
                cursor: 'pointer', fontWeight: 700, fontSize: 11,
              }}>{t === 'book' ? 'Kurs' : t === 'video' ? 'Live Call' : t === 'wa' ? 'WhatsApp' : t === 'cal' ? 'Kalender' : 'Link'}</button>
            ))}
          </div>
          <Label>Label</Label>
          <TextInput value={link.label} onChange={v => update(i, { label: v })} />
          <Label>Sublabel</Label>
          <TextInput value={link.sublabel} onChange={v => update(i, { sublabel: v })} />
          <Label>URL</Label>
          <TextInput value={link.url} onChange={v => update(i, { url: v })}
                     placeholder="https://..." />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Link hinzufügen</button>
    </FormSection>
  );
}

function LiveCallsSection({ hub, setHub }: { hub: HubPayload; setHub: (h: HubPayload) => void }) {
  const set = (next: LiveCallType[]) => setHub({ ...hub, live_calls: next });
  const update = (idx: number, patch: Partial<LiveCallType>) =>
    set(hub.live_calls.map((c, i) => i === idx ? { ...c, ...patch } : c));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.live_calls.length) return;
    const next = [...hub.live_calls];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((c, i) => ({ ...c, sort_order: i })));
  };
  const add = () => set([...hub.live_calls, {
    tag: '', title: 'Neuer Call', body: '', sort_order: hub.live_calls.length,
  }]);
  const remove = (idx: number) => set(hub.live_calls.filter((_, i) => i !== idx));

  return (
    <FormSection title="Live Calls">
      <Checkbox checked={hub.show_live_calls}
                onChange={v => setHub({ ...hub, show_live_calls: v })} label="Anzeigen" />
      {hub.live_calls.map((c, i) => (
        <div key={c.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Tag (optional)</Label>
          <TextInput value={c.tag} onChange={v => update(i, { tag: v })}
                     placeholder="LIVE CALLS" />
          <Label>Titel</Label>
          <TextInput value={c.title} onChange={v => update(i, { title: v })} />
          <Label>Body</Label>
          <TextArea rows={4} value={c.body} onChange={v => update(i, { body: v })} />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Live Call hinzufügen</button>
    </FormSection>
  );
}

function ProductsSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const set = (next: ProductType[]) => setHub({ ...hub, products: next });
  const update = (idx: number, patch: Partial<ProductType>) =>
    set(hub.products.map((p, i) => i === idx ? { ...p, ...patch } : p));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.products.length) return;
    const next = [...hub.products];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((p, i) => ({ ...p, sort_order: i })));
  };
  const add = () => set([...hub.products, {
    label: '', title: 'Neues Produkt', description: '', cta_text: 'Zum Shop',
    url: '', image_url: '', highlight: false, sort_order: hub.products.length,
  }]);
  const remove = (idx: number) => set(hub.products.filter((_, i) => i !== idx));
  const uploadPhoto = async (idx: number, file: File) => {
    try {
      const { url } = await hubApi.uploadImage(courseId, 'product', file);
      update(idx, { image_url: url });
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    }
  };

  return (
    <FormSection title="Produkte">
      <Checkbox checked={hub.show_products}
                onChange={v => setHub({ ...hub, show_products: v })} label="Anzeigen" />
      {hub.products.map((p, i) => (
        <div key={p.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Label (optional, z.B. Kategorie)</Label>
          <TextInput value={p.label} onChange={v => update(i, { label: v })} />
          <Label>Titel</Label>
          <TextInput value={p.title} onChange={v => update(i, { title: v })} />
          <Label>Beschreibung</Label>
          <TextArea rows={3} value={p.description} onChange={v => update(i, { description: v })} />
          <Label>CTA-Text</Label>
          <TextInput value={p.cta_text} onChange={v => update(i, { cta_text: v })} />
          <Label>URL</Label>
          <TextInput value={p.url} onChange={v => update(i, { url: v })}
                     placeholder="https://..." />
          <Label>Bild</Label>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12 }}>
            {p.image_url && (
              <img src={p.image_url} alt=""
                   style={{ width: 80, height: 60, objectFit: 'cover', borderRadius: 6 }} />
            )}
            <input type="file" accept="image/jpeg,image/png,image/webp"
                   onChange={e => e.target.files?.[0] && uploadPhoto(i, e.target.files[0])} />
            {p.image_url && (
              <button onClick={() => update(i, { image_url: '' })} style={smallRmBtn}>
                entfernen
              </button>
            )}
          </div>
          <Checkbox checked={p.highlight}
                    onChange={v => update(i, { highlight: v })}
                    label="Als Highlight (berry-gradient) anzeigen" />
        </div>
      ))}
      <button onClick={add} style={addBtn}>+ Produkt hinzufügen</button>
    </FormSection>
  );
}

function DownloadsSection({
  hub, setHub, courseId,
}: { hub: HubPayload; setHub: (h: HubPayload) => void; courseId: string }) {
  const set = (next: DownloadType[]) => setHub({ ...hub, downloads: next });
  const update = (idx: number, patch: Partial<DownloadType>) =>
    set(hub.downloads.map((d, i) => i === idx ? { ...d, ...patch } : d));
  const move = (idx: number, dir: -1 | 1) => {
    const t = idx + dir;
    if (t < 0 || t >= hub.downloads.length) return;
    const next = [...hub.downloads];
    [next[idx], next[t]] = [next[t], next[idx]];
    set(next.map((d, i) => ({ ...d, sort_order: i })));
  };
  const remove = (idx: number) => set(hub.downloads.filter((_, i) => i !== idx));
  const uploadPdf = async (file: File) => {
    try {
      const info = await hubApi.uploadPdf(courseId, file);
      set([...hub.downloads, {
        title: info.file_name.replace(/\.pdf$/i, ''),
        description: '',
        file_path: info.file_path,
        file_name: info.file_name,
        file_size_kb: info.file_size_kb,
        sort_order: hub.downloads.length,
      }]);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    }
  };

  return (
    <FormSection title="Downloads">
      <Checkbox checked={hub.show_downloads}
                onChange={v => setHub({ ...hub, show_downloads: v })} label="Anzeigen" />
      {hub.downloads.map((d, i) => (
        <div key={d.id || i} style={listItemStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => move(i, -1)} style={iconBtn}>↑</button>
              <button onClick={() => move(i, 1)} style={iconBtn}>↓</button>
            </div>
            <button onClick={() => remove(i)} style={smallRmBtn}>entfernen</button>
          </div>
          <Label>Titel</Label>
          <TextInput value={d.title} onChange={v => update(i, { title: v })} />
          <Label>Beschreibung</Label>
          <TextInput value={d.description} onChange={v => update(i, { description: v })} />
          <div style={{ fontSize: 12, color: 'rgba(48,48,48,0.5)' }}>
            Datei: {d.file_name} · {d.file_size_kb} KB
          </div>
        </div>
      ))}
      <label style={{ ...addBtn, display: 'block', textAlign: 'center' }}>
        + PDF hochladen
        <input type="file" accept="application/pdf" style={{ display: 'none' }}
               onChange={e => e.target.files?.[0] && uploadPdf(e.target.files[0])} />
      </label>
    </FormSection>
  );
}
