import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import * as tus from 'tus-js-client';
import { api, type CourseDetail, type LessonItem, type AttachmentItem } from '../../lib/api';

export default function AdminModuleDetail() {
  const { courseId, moduleId } = useParams<{ courseId: string; moduleId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formVideoUrl, setFormVideoUrl] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formDuration, setFormDuration] = useState(0);

  const load = () => {
    if (courseId) {
      api.getAdminCourse(courseId).then(setCourse).finally(() => setLoading(false));
    }
  };

  useEffect(load, [courseId]);

  const module = course?.modules.find((m) => m.id === moduleId);

  // Flatten lessons from all sections (admin sees flat list)
  const allLessons: (LessonItem & { sectionId: string })[] = [];
  if (module) {
    for (const section of module.sections) {
      for (const lesson of section.lessons) {
        allLessons.push({ ...lesson, sectionId: section.id });
      }
    }
  }

  // Get default section id (first section)
  const defaultSectionId = module?.sections[0]?.id;

  const resetForm = () => {
    setFormTitle('');
    setFormVideoUrl('');
    setFormDescription('');
    setFormDuration(0);
    setShowCreate(false);
    setEditingId(null);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim() || !defaultSectionId) return;
    await api.createLesson({
      section_id: defaultSectionId,
      title: formTitle,
      description: formDescription || undefined,
      video_url: formVideoUrl || undefined,
      duration_minutes: formDuration,
      sort_order: allLessons.length,
    });
    resetForm();
    load();
  };

  const handleStartEdit = (lesson: LessonItem) => {
    setEditingId(lesson.id);
    setFormTitle(lesson.title);
    setFormVideoUrl(lesson.video_url || '');
    setFormDescription(lesson.description || '');
    setFormDuration(lesson.duration_minutes);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId || !formTitle.trim()) return;
    await api.updateLesson(editingId, {
      title: formTitle,
      video_url: formVideoUrl || null,
      description: formDescription || null,
      duration_minutes: formDuration,
    });
    resetForm();
    load();
  };

  const handleDelete = async (lessonId: string, title: string) => {
    if (!confirm(`Lektion "${title}" wirklich löschen?`)) return;
    await api.deleteLesson(lessonId);
    load();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--nora-pink)]" />
      </div>
    );
  }

  if (!course || !module) {
    return <div className="p-8 text-gray-500">Modul nicht gefunden.</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link to="/admin/courses" className="hover:text-[var(--nora-pink-dark)] transition-colors">
          Kurse
        </Link>
        <span>/</span>
        <Link to={`/admin/course/${courseId}`} className="hover:text-[var(--nora-pink-dark)] transition-colors">
          {course.title}
        </Link>
        <span>/</span>
        <span className="text-gray-700">{module.title}</span>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">{module.title}</h2>
        <button
          onClick={() => { resetForm(); setShowCreate(true); }}
          className="px-4 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors"
        >
          + Neue Lektion
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <LessonForm
          title={formTitle}
          videoUrl={formVideoUrl}
          description={formDescription}
          duration={formDuration}
          onTitleChange={setFormTitle}
          onVideoUrlChange={setFormVideoUrl}
          onDescriptionChange={setFormDescription}
          onDurationChange={setFormDuration}
          onSubmit={handleCreate}
          onCancel={resetForm}
          submitLabel="Erstellen"
        />
      )}

      {/* Lessons list */}
      {allLessons.length === 0 && !showCreate ? (
        <div className="bg-white rounded-2xl p-8 text-center text-gray-500">
          Noch keine Lektionen. Erstelle deine erste Lektion.
        </div>
      ) : (
        <div className="space-y-3">
          {allLessons.map((lesson, idx) => (
            <div key={lesson.id}>
              {editingId === lesson.id ? (
                <LessonForm
                  lessonId={lesson.id}
                  title={formTitle}
                  videoUrl={formVideoUrl}
                  description={formDescription}
                  duration={formDuration}
                  onTitleChange={setFormTitle}
                  onVideoUrlChange={setFormVideoUrl}
                  onDescriptionChange={setFormDescription}
                  onDurationChange={setFormDuration}
                  onSubmit={handleSaveEdit}
                  onCancel={resetForm}
                  submitLabel="Speichern"
                />
              ) : (
                <div className="bg-white rounded-2xl p-5 shadow-sm group">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-sm font-medium text-gray-500 shrink-0">
                        {idx + 1}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-medium text-gray-800">{lesson.title}</h3>
                        <div className="flex items-center gap-3 mt-1">
                          {lesson.video_url && (
                            <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                              </svg>
                              Video
                            </span>
                          )}
                          {lesson.description && (
                            <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                              Text
                            </span>
                          )}
                          {lesson.duration_minutes > 0 && <span className="text-xs text-gray-400">{lesson.duration_minutes} Min.</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      <button
                        onClick={() => handleStartEdit(lesson)}
                        className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
                      >
                        Bearbeiten
                      </button>
                      <button
                        onClick={() => handleDelete(lesson.id, lesson.title)}
                        className="px-3 py-1.5 text-sm border border-red-200 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                      >
                        Löschen
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LessonForm({
  lessonId, title, videoUrl, description, duration,
  onTitleChange, onVideoUrlChange, onDescriptionChange, onDurationChange,
  onSubmit, onCancel, submitLabel,
}: {
  lessonId?: string;
  title: string;
  videoUrl: string;
  description: string;
  duration: number;
  onTitleChange: (v: string) => void;
  onVideoUrlChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onDurationChange: (v: number) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [attachUploading, setAttachUploading] = useState(false);

  useEffect(() => {
    if (lessonId) {
      api.getAttachments(lessonId).then(setAttachments).catch(console.error);
    }
  }, [lessonId]);

  const handleFileUpload = async (file: File) => {
    const videoTitle = title || file.name.replace(/\.[^/.]+$/, '');
    setUploading(true);
    setUploadProgress(0);
    setUploadError('');

    try {
      const uploadInfo = await api.createVideoUpload(videoTitle);

      const upload = new tus.Upload(file, {
        endpoint: uploadInfo.tus_endpoint,
        retryDelays: [0, 3000, 5000, 10000],
        metadata: {
          filetype: file.type,
          title: videoTitle,
        },
        headers: {
          AuthorizationSignature: uploadInfo.auth_signature,
          AuthorizationExpire: String(uploadInfo.auth_expiration),
          VideoId: uploadInfo.video_id,
          LibraryId: uploadInfo.library_id,
        },
        onError: (error) => {
          setUploadError(error.message || 'Upload fehlgeschlagen');
          setUploading(false);
        },
        onProgress: (bytesUploaded, bytesTotal) => {
          setUploadProgress(Math.round((bytesUploaded / bytesTotal) * 100));
        },
        onSuccess: () => {
          onVideoUrlChange(uploadInfo.embed_url);
          setUploading(false);
          setUploadProgress(100);
        },
      });

      upload.start();
    } catch (err: any) {
      setUploadError(err.message || 'Fehler beim Erstellen des Uploads');
      setUploading(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="bg-white rounded-2xl p-6 mb-3 shadow-sm space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Titel</label>
        <input
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          placeholder="z.B. Willkommen zum Kurs"
          autoFocus
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Video</label>
        {/* Upload area */}
        {!videoUrl && !uploading && (
          <div
            className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center cursor-pointer hover:border-[var(--nora-pink)] hover:bg-[var(--nora-pink-light)]/20 transition-colors"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              const file = e.dataTransfer.files[0];
              if (file?.type.startsWith('video/')) handleFileUpload(file);
            }}
          >
            <svg className="w-8 h-8 mx-auto text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-gray-500">Video hierher ziehen oder klicken</p>
            <p className="text-xs text-gray-400 mt-1">MP4, MOV, MKV — wird auf Bunny.net gespeichert</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
            />
          </div>
        )}

        {/* Upload progress */}
        {uploading && (
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Video wird hochgeladen...</span>
              <span className="text-sm font-medium">{uploadProgress}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--nora-pink)] rounded-full transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload error */}
        {uploadError && (
          <div className="bg-red-50 text-red-600 text-sm px-3 py-2 rounded-lg mt-2">{uploadError}</div>
        )}

        {/* Video URL (shown after upload or for manual entry) */}
        {(videoUrl || (!uploading && !uploadError)) && (
          <div className={videoUrl ? 'mt-2' : 'mt-3'}>
            {videoUrl && (
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                  </svg>
                  Video verknüpft
                </span>
                <button
                  type="button"
                  onClick={async () => {
                    if (videoUrl && confirm('Video auch bei Bunny.net löschen?')) {
                      try {
                        await api.deleteVideo(videoUrl);
                      } catch (e) {
                        console.error('Failed to delete video from Bunny:', e);
                      }
                    }
                    onVideoUrlChange('');
                  }}
                  className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                >
                  Entfernen
                </button>
              </div>
            )}
            <input
              type="url"
              value={videoUrl}
              onChange={(e) => onVideoUrlChange(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent text-sm"
              placeholder="Oder Embed-URL manuell eingeben..."
            />
          </div>
        )}
      </div>
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="block text-sm font-medium text-gray-700">Text unterhalb des Videos</label>
          <span className="text-xs text-gray-400">Markdown wird unterstützt</span>
        </div>
        <textarea
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent font-mono text-sm"
          rows={6}
          placeholder="Markdown: **fett**, *kursiv*, ## Überschrift, - Liste, [Link](url)..."
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Dauer in Minuten (optional)</label>
        <input
          type="number"
          value={duration || ''}
          onChange={(e) => onDurationChange(parseInt(e.target.value) || 0)}
          className="w-32 px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--nora-pink)] focus:border-transparent"
          min={0}
          placeholder="—"
        />
      </div>
      {/* Attachments (only when editing) */}
      {lessonId && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Dateien / Downloads</label>
          {attachments.length > 0 && (
            <div className="space-y-2 mb-3">
              {attachments.map((a) => (
                <div key={a.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span className="text-sm text-gray-700 truncate">{a.original_filename}</span>
                    <span className="text-xs text-gray-400 shrink-0">{(a.file_size / 1024).toFixed(0)} KB</span>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      if (!confirm(`"${a.original_filename}" löschen?`)) return;
                      await api.deleteAttachment(a.id);
                      setAttachments(prev => prev.filter(x => x.id !== a.id));
                    }}
                    className="text-xs text-gray-400 hover:text-red-500 transition-colors ml-2 shrink-0"
                  >
                    Entfernen
                  </button>
                </div>
              ))}
            </div>
          )}
          <button
            type="button"
            disabled={attachUploading}
            onClick={() => attachInputRef.current?.click()}
            className="text-sm text-[var(--nora-pink-dark)] hover:text-[var(--nora-pink)] transition-colors disabled:opacity-50"
          >
            {attachUploading ? 'Wird hochgeladen...' : '+ Datei hinzufügen'}
          </button>
          <input
            ref={attachInputRef}
            type="file"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file || !lessonId) return;
              setAttachUploading(true);
              try {
                const att = await api.uploadAttachment(lessonId, file);
                setAttachments(prev => [...prev, att]);
              } catch (err) {
                console.error('Attachment upload failed:', err);
              }
              setAttachUploading(false);
              e.target.value = '';
            }}
          />
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={uploading}
          className="px-5 py-2 bg-[var(--nora-pink)] text-white rounded-lg font-medium hover:bg-[var(--nora-pink-dark)] transition-colors disabled:opacity-50"
        >
          {submitLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Abbrechen
        </button>
      </div>
    </form>
  );
}
