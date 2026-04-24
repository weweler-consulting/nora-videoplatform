import { useEffect, useState } from 'react';
import { hubApi, HubPayload } from '../../../lib/api/hub';
import HubHero from './HubHero';
import HubLinks from './HubLinks';
import HubContact from './HubContact';
import HubLiveCalls from './HubLiveCalls';
import HubProducts from './HubProducts';
import HubDownloads from './HubDownloads';

export default function HubView({ courseId }: { courseId: string }) {
  const [hub, setHub] = useState<HubPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    hubApi.getPublic(courseId).then(setHub).catch((e) => setError(e.message));
  }, [courseId]);

  if (error) return <div style={{ padding: 20, color: 'var(--berry-dark)' }}>{error}</div>;
  if (!hub) return <div style={{ padding: 20 }}>Lädt …</div>;

  const isEmpty =
    !hub.hero_eyebrow && !hub.hero_title_html && !hub.hero_body &&
    hub.links.length === 0 && hub.live_calls.length === 0 &&
    hub.products.length === 0 && hub.downloads.length === 0;

  if (isEmpty) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Dieser Mitgliederbereich wird gerade eingerichtet — schau später nochmal vorbei.
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <h1 style={{
        fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 22,
        textTransform: 'uppercase', letterSpacing: '-0.3px',
        color: 'var(--soy)', marginBottom: 28,
      }}>
        Dein Mitgliederbereich
      </h1>
      <HubHero
        variant={hub.hero_variant}
        eyebrow={hub.hero_eyebrow}
        titleHtml={hub.hero_title_html}
        body={hub.hero_body}
        contactName={hub.contact_name_override}
        contactRole={hub.contact_role}
        contactPhotoUrl={hub.contact_photo_url}
      />
      {hub.links.length > 0 && <HubLinks links={hub.links} />}
      {hub.show_contact && <HubContact
        name={hub.contact_name_override} role={hub.contact_role}
        email={hub.contact_email_override} whatsappUrl={hub.contact_whatsapp_url}
        photoUrl={hub.contact_photo_url}
      />}
      {hub.show_live_calls && hub.live_calls.length > 0 && <HubLiveCalls calls={hub.live_calls} />}
      {hub.show_products && hub.products.length > 0 && <HubProducts products={hub.products} />}
      {hub.show_downloads && hub.downloads.length > 0 &&
        <HubDownloads courseId={courseId} downloads={hub.downloads} />}
    </div>
  );
}
