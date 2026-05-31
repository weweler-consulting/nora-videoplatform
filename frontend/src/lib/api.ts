const API_BASE = '/api/v1';

function getToken(): string | null {
  return localStorage.getItem('token');
}

export function setToken(token: string) {
  localStorage.setItem('token', token);
}

export function clearToken() {
  localStorage.removeItem('token');
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    if (path !== '/auth/login') {
      clearToken();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    const err = new Error(body.detail || 'Unauthorized') as ApiError;
    err.status = 401;
    err.detail = body.detail;
    throw err;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `HTTP ${res.status}`) as ApiError;
    err.status = res.status;
    err.detail = body.detail;
    throw err;
  }

  return res.json();
}

export interface ApiError extends Error {
  status: number;
  detail?: string;
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<{ id: string; email: string; name: string; is_admin: boolean }>('/auth/me'),

  changePassword: (currentPassword: string, newPassword: string) =>
    request('/auth/password', {
      method: 'PUT',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  forgotPassword: (email: string) =>
    request<{ ok: boolean }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    request<{ ok: boolean }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  getInvite: (token: string) =>
    request<{ email: string; name: string; course_titles: string[] }>(`/auth/invite/${token}`),

  acceptInvite: (token: string, password: string, acceptTerms: boolean) =>
    request<{ access_token: string }>('/auth/invite/accept', {
      method: 'POST',
      body: JSON.stringify({ token, password, accept_terms: acceptTerms }),
    }),

  updateProfile: (data: { name?: string; email?: string }) =>
    request<{
      id: string; email: string; name: string; is_admin: boolean;
      email_change_pending: boolean; pending_email: string | null;
    }>('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  confirmEmailChange: (token: string) =>
    request<{ ok: boolean; email: string }>('/auth/confirm-email-change', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  // Courses (student)
  getMyCourses: () =>
    request<CourseListItem[]>('/courses/'),

  getCourse: (id: string) =>
    request<CourseDetail>(`/courses/${id}`),

  // Progress
  completeLesson: (lessonId: string) =>
    request('/progress/' + lessonId + '/complete', { method: 'POST' }),

  uncompleteLesson: (lessonId: string) =>
    request('/progress/' + lessonId + '/uncomplete', { method: 'POST' }),

  // Admin
  getAllCourses: () => request<CourseListItem[]>('/courses/admin/all'),
  getAdminCourse: (id: string) => request<CourseDetail>(`/courses/admin/${id}`),
  createCourse: (data: { title: string; description?: string; image_url?: string }) =>
    request<{ id: string }>('/courses/', { method: 'POST', body: JSON.stringify(data) }),
  updateCourse: (id: string, data: Record<string, unknown>) =>
    request<{ id: string }>(`/courses/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCourse: (id: string) =>
    request(`/courses/${id}`, { method: 'DELETE' }),
  copyHubFrom: (courseId: string, sourceCourseId: string) =>
    request<unknown>(`/admin/courses/${courseId}/hub/copy-from/${sourceCourseId}`, {
      method: 'POST',
    }),

  createModule: (data: { course_id: string; title: string; sort_order?: number }) =>
    request<{ id: string }>('/modules/', { method: 'POST', body: JSON.stringify(data) }),
  updateModule: (id: string, data: Record<string, unknown>) =>
    request<{ id: string }>(`/modules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteModule: (id: string) =>
    request(`/modules/${id}`, { method: 'DELETE' }),

  createSection: (data: { module_id: string; title: string; sort_order?: number }) =>
    request<{ id: string }>('/sections/', { method: 'POST', body: JSON.stringify(data) }),
  deleteSection: (id: string) =>
    request(`/sections/${id}`, { method: 'DELETE' }),

  createLesson: (data: { section_id: string; title: string; description?: string; video_url?: string; duration_minutes?: number; sort_order?: number }) =>
    request<{ id: string }>('/lessons/', { method: 'POST', body: JSON.stringify(data) }),
  updateLesson: (id: string, data: Record<string, unknown>) =>
    request<{ id: string }>(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteLesson: (id: string) =>
    request(`/lessons/${id}`, { method: 'DELETE' }),

  getUsers: () => request<UserWithEnrollments[]>('/users/'),
  inviteUser: (data: { email: string; name: string; course_id: string; send_email?: boolean }) =>
    request<{ user_id: string; email_sent: boolean; invite_url: string | null; pending_invite: boolean }>('/users/invite', { method: 'POST', body: JSON.stringify(data) }),
  toggleUserActive: (userId: string) =>
    request<{ is_active: boolean }>('/users/' + userId + '/toggle-active', { method: 'PUT' }),
  enrollUser: (userId: string, courseId: string) =>
    request('/users/' + userId + '/enroll', { method: 'POST', body: JSON.stringify({ course_id: courseId }) }),
  removeEnrollment: (enrollmentId: string) =>
    request(`/users/enrollment/${enrollmentId}`, { method: 'DELETE' }),
  createVideoUpload: (title: string, libraryId?: string) =>
    request<{
      video_id: string;
      library_id: string;
      tus_endpoint: string;
      auth_signature: string;
      auth_expiration: number;
      embed_url: string;
    }>('/upload/create-video', {
      method: 'POST',
      body: JSON.stringify({ title, library_id: libraryId }),
    }),
  getUserProgress: (userId: string) =>
    request<UserCourseProgress[]>(`/users/${userId}/progress`),
  deleteUser: (userId: string) =>
    request(`/users/${userId}`, { method: 'DELETE' }),
  unlockModule: (moduleId: string, userId: string) =>
    request<{ ok: boolean }>(`/modules/${moduleId}/unlock/${userId}`, { method: 'POST' }),
  lockModule: (moduleId: string, userId: string) =>
    request<{ ok: boolean }>(`/modules/${moduleId}/unlock/${userId}`, { method: 'DELETE' }),
  uploadAttachment: (lessonId: string, file: File) => {
    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);
    return fetch(`${API_BASE}/lessons/${lessonId}/attachments`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      return res.json() as Promise<AttachmentItem>;
    });
  },
  getAttachments: (lessonId: string) =>
    request<AttachmentItem[]>(`/lessons/${lessonId}/attachments`),
  deleteAttachment: (attachmentId: string) =>
    request<{ ok: boolean }>(`/attachments/${attachmentId}`, { method: 'DELETE' }),
  getDashboardStats: () =>
    request<{
      total_users: number;
      active_users_7d: number;
      new_users_30d: number;
      total_completed_courses: number;
      courses: { course_id: string; title: string; enrolled: number; total_lessons: number; avg_progress: number; completed_count: number }[];
      inactive_users: { id: string; name: string; email: string; last_active: string | null; completed_lessons: number; total_lessons: number; progress_percent: number }[];
    }>('/dashboard/stats'),
  deleteVideo: (embedUrl: string) =>
    request<{ ok: boolean }>('/upload/delete-video', {
      method: 'POST',
      body: JSON.stringify({ embed_url: embedUrl }),
    }),

  // Announcements (admin)
  listAnnouncements: (courseId: string) =>
    request<{ announcements: AnnouncementItem[] }>(`/admin/courses/${courseId}/announcements`)
      .then((r) => r.announcements),
  previewAnnouncement: (courseId: string, targetType: AnnouncementTargetType, targetId: string) => {
    const params = new URLSearchParams({ target_type: targetType, target_id: targetId });
    return request<AnnouncementPreview>(
      `/admin/courses/${courseId}/announcements/preview?${params.toString()}`,
    );
  },
  createAnnouncement: (courseId: string, input: AnnouncementCreateInput) =>
    request<AnnouncementCreateResult>(`/admin/courses/${courseId}/announcements`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  // Integrations (service tokens)
  listServiceTokens: () =>
    request<ServiceTokenInfo[]>('/integrations/tokens'),
  createServiceToken: (name: string) =>
    request<ServiceTokenInfo & { token: string }>('/integrations/tokens', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  deleteServiceToken: (id: string) =>
    request<{ ok: boolean }>(`/integrations/tokens/${id}`, { method: 'DELETE' }),
};

export interface ServiceTokenInfo {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
}

export type AnnouncementTargetType = 'module' | 'lesson';

export interface AnnouncementItem {
  id: string;
  course_id: string;
  target_type: AnnouncementTargetType;
  target_id: string;
  target_title: string | null;
  target_module_title: string | null;
  subject: string;
  body: string;
  recipient_count: number;
  sent_at: string;
  created_by: { id: string; name: string } | null;
}

export interface AnnouncementPreview {
  suggested_subject: string;
  suggested_body: string;
  recipient_count: number;
  target_title: string;
  target_module_title: string | null;
}

export interface AnnouncementCreateInput {
  target_type: AnnouncementTargetType;
  target_id: string;
  subject: string;
  body: string;
}

export interface AnnouncementCreateResult {
  announcement: AnnouncementItem;
  delivery_summary: { sent: number; failed: number };
}

// Types
export interface UserEnrollment {
  enrollment_id: string;
  course_id: string;
  course_title: string;
}

export interface UserWithEnrollments {
  id: string;
  email: string;
  name: string;
  is_admin: boolean;
  is_active: boolean;
  enrollments: UserEnrollment[];
}

export interface UserModuleProgress {
  module_id: string;
  title: string;
  total_lessons: number;
  completed_lessons: number;
  is_locked: boolean;
  manually_unlocked: boolean;
  unlock_after_days: number;
}

export interface UserCourseProgress {
  course_id: string;
  title: string;
  enrolled_at: string | null;
  total_lessons: number;
  completed_lessons: number;
  progress_percent: number;
  modules: UserModuleProgress[];
}

export interface CourseListItem {
  id: string;
  title: string;
  description: string | null;
  image_url: string | null;
  total_lessons: number;
  completed_lessons: number;
  progress_percent: number;
}

export interface AttachmentItem {
  id: string;
  original_filename: string;
  file_size: number;
}

export interface LessonItem {
  id: string;
  title: string;
  description: string | null;
  video_url: string | null;
  duration_minutes: number;
  sort_order: number;
  completed: boolean;
}

export interface SectionItem {
  id: string;
  title: string;
  sort_order: number;
  lessons: LessonItem[];
}

export interface ModuleItem {
  id: string;
  title: string;
  description: string | null;
  image_url: string | null;
  sort_order: number;
  unlock_after_days: number;
  is_locked: boolean;
  unlocks_at: string | null;
  sections: SectionItem[];
  total_lessons: number;
  completed_lessons: number;
  total_duration: number;
}

export interface CourseDetail {
  id: string;
  title: string;
  description: string | null;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
  stripe_product_id: string | null;
  hub_enabled: boolean;
  created_at: string;
  modules: ModuleItem[];
  total_lessons: number;
  completed_lessons: number;
  progress_percent: number;
}
