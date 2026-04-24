const API_BASE = '/api/v1';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}`, ...extra } : extra;
}

export type IconType = 'book' | 'video' | 'wa' | 'cal' | 'link';
export type HeroVariant = 'berry' | 'dark' | 'pale';

export interface HubLink {
  id?: string;
  icon_type: IconType;
  label: string;
  sublabel: string;
  url: string;
  sort_order: number;
}

export interface HubLiveCall {
  id?: string;
  tag: string;
  title: string;
  body: string;
  sort_order: number;
}

export interface HubProduct {
  id?: string;
  label: string;
  title: string;
  description: string;
  cta_text: string;
  url: string;
  image_url: string;
  highlight: boolean;
  sort_order: number;
}

export interface HubDownload {
  id?: string;
  title: string;
  description: string;
  file_path: string;
  file_name: string;
  file_size_kb: number;
  sort_order: number;
}

export interface HubPayload {
  hero_variant: HeroVariant;
  hero_eyebrow: string;
  hero_title_html: string;
  hero_body: string;
  contact_user_id: string | null;
  contact_name_override: string;
  contact_role: string;
  contact_email_override: string;
  contact_whatsapp_url: string;
  contact_photo_url: string;
  show_contact: boolean;
  show_live_calls: boolean;
  show_products: boolean;
  show_downloads: boolean;
  links: HubLink[];
  live_calls: HubLiveCall[];
  products: HubProduct[];
  downloads: HubDownload[];
}

async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init.headers as Record<string, string> || {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const hubApi = {
  getPublic: (courseId: string) =>
    jsonRequest<HubPayload>(`/courses/${courseId}/hub`),

  getAdmin: (courseId: string) =>
    jsonRequest<HubPayload>(`/admin/courses/${courseId}/hub`),

  save: (courseId: string, payload: HubPayload) =>
    jsonRequest<HubPayload>(`/admin/courses/${courseId}/hub`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  uploadPdf: async (courseId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/admin/courses/${courseId}/hub/pdf`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json() as Promise<{ file_path: string; file_name: string; file_size_kb: number }>;
  },

  uploadImage: async (courseId: string, kind: 'product' | 'contact_photo', file: File) => {
    const form = new FormData();
    form.append('file', file);
    form.append('kind', kind);
    const res = await fetch(`${API_BASE}/admin/courses/${courseId}/hub/image`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json() as Promise<{ url: string }>;
  },

  downloadUrl: (courseId: string, downloadId: string) =>
    `${API_BASE}/courses/${courseId}/hub/downloads/${downloadId}`,
};

export async function downloadHubFile(courseId: string, downloadId: string, filename: string) {
  const res = await fetch(hubApi.downloadUrl(courseId, downloadId), {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Download fehlgeschlagen: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
