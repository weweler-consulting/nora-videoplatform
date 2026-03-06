import { useEffect, useState } from 'react';
import { api, type UserWithEnrollments, type CourseListItem, type UserCourseProgress } from '../../lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { X, UserPlus, Trash2, ShieldCheck, ShieldOff, Copy, Check } from 'lucide-react';

export default function AdminUsers() {
  const [users, setUsers] = useState<UserWithEnrollments[]>([]);
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [invEmail, setInvEmail] = useState('');
  const [invName, setInvName] = useState('');
  const [invPassword, setInvPassword] = useState('');
  const [invCourseId, setInvCourseId] = useState('');
  const [invError, setInvError] = useState('');
  const [invSendEmail, setInvSendEmail] = useState(false);
  const [inviteResult, setInviteResult] = useState<{ name: string; email: string; password: string; courseTitle: string; emailSent: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const [filterCourseId, setFilterCourseId] = useState('');

  // Sheet state
  const [selectedUser, setSelectedUser] = useState<UserWithEnrollments | null>(null);
  const [userProgress, setUserProgress] = useState<UserCourseProgress[]>([]);
  const [progressLoading, setProgressLoading] = useState(false);

  const load = () => {
    Promise.all([api.getUsers(), api.getAllCourses()])
      .then(([u, c]) => { setUsers(u); setCourses(c); })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openUserSheet = async (user: UserWithEnrollments) => {
    setSelectedUser(user);
    setProgressLoading(true);
    try {
      const progress = await api.getUserProgress(user.id);
      setUserProgress(progress);
    } catch {
      setUserProgress([]);
    } finally {
      setProgressLoading(false);
    }
  };

  const closeSheet = () => {
    setSelectedUser(null);
    setUserProgress([]);
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInvError('');
    if (!invEmail.trim() || !invName.trim() || !invCourseId) {
      setInvError('Bitte alle Felder ausfüllen.');
      return;
    }
    const password = invPassword || 'changeme123';
    const courseTitle = courses.find((c) => c.id === invCourseId)?.title || '';
    try {
      const result = await api.inviteUser({
        email: invEmail, name: invName, course_id: invCourseId,
        password: invPassword || undefined, send_email: invSendEmail,
      });
      setInviteResult({ name: invName, email: invEmail, password, courseTitle, emailSent: result.email_sent });
      setCopied(false);
      setInvEmail(''); setInvName(''); setInvPassword(''); setInvCourseId('');
      setInvSendEmail(false); setShowInvite(false);
      load();
    } catch (err: any) {
      setInvError(err.message || 'Fehler beim Einladen.');
    }
  };

  const handleEnrollUser = async (userId: string, courseId: string) => {
    try {
      await api.enrollUser(userId, courseId);
      load();
      // Refresh sheet if open
      if (selectedUser?.id === userId) {
        const updated = await api.getUsers();
        const refreshed = updated.find(u => u.id === userId);
        if (refreshed) setSelectedUser(refreshed);
        const progress = await api.getUserProgress(userId);
        setUserProgress(progress);
      }
    } catch (err: any) { alert(err.message || 'Fehler beim Zuordnen.'); }
  };

  const handleRemoveEnrollment = async (enrollmentId: string, userName: string, courseTitle: string) => {
    if (!confirm(`${userName} aus "${courseTitle}" entfernen?`)) return;
    await api.removeEnrollment(enrollmentId);
    load();
    if (selectedUser) {
      const updated = await api.getUsers();
      const refreshed = updated.find(u => u.id === selectedUser.id);
      if (refreshed) setSelectedUser(refreshed);
      const progress = await api.getUserProgress(selectedUser.id);
      setUserProgress(progress);
    }
  };

  const handleToggleActive = async (userId: string) => {
    try {
      await api.toggleUserActive(userId);
      load();
      if (selectedUser?.id === userId) {
        const updated = await api.getUsers();
        const refreshed = updated.find(u => u.id === userId);
        if (refreshed) setSelectedUser(refreshed);
      }
    } catch (err: any) { alert(err.message || 'Fehler.'); }
  };

  const handleDeleteUser = async (userId: string, name: string) => {
    if (!confirm(`Nutzer "${name}" wirklich löschen? Alle Daten gehen verloren.`)) return;
    try {
      await api.deleteUser(userId);
      closeSheet();
      load();
    } catch (err: any) { alert(err.message || 'Fehler beim Löschen.'); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-muted border-t-foreground" />
      </div>
    );
  }

  const filteredUsers = filterCourseId
    ? users.filter((u) => u.enrollments.some((e) => e.course_id === filterCourseId))
    : users;

  return (
    <div className="p-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-bold">Teilnehmer</h2>
          <p className="text-sm text-muted-foreground">{users.filter(u => !u.is_admin).length} Mitglieder verwalten</p>
        </div>
        <Button onClick={() => setShowInvite(!showInvite)} size="sm">
          <UserPlus className="h-4 w-4" />
          Einladen
        </Button>
      </div>

      {/* Invite Form */}
      {showInvite && (
        <Card className="mb-5">
          <CardHeader className="pb-4">
            <CardTitle className="text-sm">Neue Teilnehmerin einladen</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleInvite} className="space-y-3">
              {invError && (
                <div className="bg-destructive/10 text-destructive text-sm px-3 py-2 rounded-md">{invError}</div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Name</label>
                  <Input value={invName} onChange={(e) => setInvName(e.target.value)} placeholder="Vorname Nachname" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">E-Mail</label>
                  <Input type="email" value={invEmail} onChange={(e) => setInvEmail(e.target.value)} placeholder="nutzer@email.de" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Passwort</label>
                  <Input value={invPassword} onChange={(e) => setInvPassword(e.target.value)} placeholder="Standard: changeme123" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Kurs</label>
                  <select
                    value={invCourseId}
                    onChange={(e) => setInvCourseId(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="">Kurs wählen...</option>
                    {courses.map((c) => (
                      <option key={c.id} value={c.id}>{c.title}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
                  <input
                    type="checkbox"
                    checked={invSendEmail}
                    onChange={(e) => setInvSendEmail(e.target.checked)}
                    className="h-4 w-4 rounded border-input"
                  />
                  Einladung per E-Mail senden
                </label>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setShowInvite(false)}>
                    Abbrechen
                  </Button>
                  <Button type="submit" size="sm">Einladen</Button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Invite Result */}
      {inviteResult && (
        <Card className="mb-5 border-green-200 bg-green-50/50">
          <CardContent className="pt-5">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Badge variant="success">Einladung erstellt</Badge>
                {inviteResult.emailSent && <Badge variant="success">E-Mail gesendet</Badge>}
              </div>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setInviteResult(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="bg-white rounded-md p-3 text-sm text-muted-foreground whitespace-pre-line font-mono leading-relaxed border">
              {`Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\nLink: ${window.location.origin}/login\nE-Mail: ${inviteResult.email}\nPasswort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => {
                const text = `Hallo ${inviteResult.name},\n\ndu hast Zugang zum Kurs "${inviteResult.courseTitle}" erhalten!\n\nHier sind deine Zugangsdaten:\n\nLink: ${window.location.origin}/login\nE-Mail: ${inviteResult.email}\nPasswort: ${inviteResult.password}\n\nBitte ändere dein Passwort nach dem ersten Login.\n\nLiebe Grüße\nNora`;
                navigator.clipboard.writeText(text.replace(/\\n/g, '\n'));
                setCopied(true);
              }}
            >
              {copied ? <><Check className="h-3.5 w-3.5" /> Kopiert!</> : <><Copy className="h-3.5 w-3.5" /> Nachricht kopieren</>}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      <Card>
        <CardContent className="p-0">
          {/* Filter */}
          <div className="flex items-center gap-3 px-4 py-3 border-b">
            <select
              value={filterCourseId}
              onChange={(e) => setFilterCourseId(e.target.value)}
              className="flex h-8 rounded-md border border-input bg-transparent px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">Alle Kurse</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">
              {filteredUsers.filter(u => !u.is_admin).length} Teilnehmer
            </span>
          </div>

          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs">Name</TableHead>
                <TableHead className="text-xs">E-Mail</TableHead>
                <TableHead className="text-xs">Kurse</TableHead>
                <TableHead className="text-xs">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-12">
                    {filterCourseId ? 'Keine Nutzer in diesem Kurs.' : 'Noch keine Nutzer vorhanden.'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredUsers.map((user) => (
                  <TableRow
                    key={user.id}
                    className="cursor-pointer"
                    onClick={() => openUserSheet(user)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium shrink-0">
                          {user.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="text-sm font-medium">{user.name}</span>
                        {user.is_admin && <Badge variant="warning">Admin</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1">
                        {user.enrollments.map((enr) => (
                          <Badge key={enr.enrollment_id} variant="secondary">
                            {enr.course_title}
                          </Badge>
                        ))}
                        {user.enrollments.length === 0 && (
                          <span className="text-xs text-muted-foreground">Kein Kurs</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {!user.is_admin && (
                        <Badge variant={user.is_active ? "success" : "muted"} className="gap-1.5">
                          <span className={`h-1.5 w-1.5 rounded-full ${user.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                          {user.is_active ? 'aktiv' : 'inaktiv'}
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* User Detail Sheet */}
      <Sheet open={!!selectedUser} onOpenChange={(open) => !open && closeSheet()}>
        <SheetContent>
          {selectedUser && (
            <div className="flex flex-col h-full">
              {/* Header */}
              <SheetHeader>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold shrink-0">
                    {selectedUser.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <SheetTitle>{selectedUser.name}</SheetTitle>
                    <SheetDescription>{selectedUser.email}</SheetDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  {selectedUser.is_admin && <Badge variant="warning">Admin</Badge>}
                  {!selectedUser.is_admin && (
                    <Badge variant={selectedUser.is_active ? "success" : "muted"} className="gap-1.5">
                      <span className={`h-1.5 w-1.5 rounded-full ${selectedUser.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                      {selectedUser.is_active ? 'aktiv' : 'inaktiv'}
                    </Badge>
                  )}
                </div>
              </SheetHeader>

              {/* Content */}
              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
                {/* Kurse & Fortschritt */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold">Kurse & Fortschritt</h3>
                    <select
                      className="h-7 text-xs border border-input rounded px-2 bg-transparent focus:outline-none focus:ring-1 focus:ring-ring"
                      value=""
                      onChange={(e) => {
                        if (e.target.value) handleEnrollUser(selectedUser.id, e.target.value);
                        e.target.value = '';
                      }}
                    >
                      <option value="">+ Kurs zuordnen</option>
                      {courses
                        .filter((c) => !selectedUser.enrollments.some((enr) => enr.course_id === c.id))
                        .map((c) => (
                          <option key={c.id} value={c.id}>{c.title}</option>
                        ))}
                    </select>
                  </div>

                  {progressLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-muted border-t-foreground" />
                    </div>
                  ) : userProgress.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">Noch keinem Kurs zugeordnet.</p>
                  ) : (
                    <div className="space-y-4">
                      {userProgress.map((cp) => {
                        const enrollment = selectedUser.enrollments.find(e => e.course_id === cp.course_id);
                        return (
                          <div key={cp.course_id} className="rounded-lg border p-4">
                            <div className="flex items-center justify-between mb-2">
                              <h4 className="text-sm font-medium">{cp.title}</h4>
                              {enrollment && (
                                <button
                                  onClick={() => handleRemoveEnrollment(enrollment.enrollment_id, selectedUser.name, cp.title)}
                                  className="text-muted-foreground hover:text-destructive transition-colors"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>

                            {/* Overall progress bar */}
                            <div className="flex items-center gap-3 mb-3">
                              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-primary rounded-full transition-all"
                                  style={{ width: `${cp.progress_percent}%` }}
                                />
                              </div>
                              <span className="text-xs font-medium text-muted-foreground w-16 text-right">
                                {cp.completed_lessons}/{cp.total_lessons}
                              </span>
                              <span className="text-xs font-semibold w-10 text-right">
                                {cp.progress_percent}%
                              </span>
                            </div>

                            {/* Module breakdown */}
                            <div className="space-y-1.5">
                              {cp.modules.map((mod) => {
                                const modPercent = mod.total_lessons > 0
                                  ? Math.round((mod.completed_lessons / mod.total_lessons) * 100)
                                  : 0;
                                return (
                                  <div key={mod.module_id} className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground truncate flex-1">{mod.title}</span>
                                    <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden shrink-0">
                                      <div
                                        className="h-full bg-primary/60 rounded-full"
                                        style={{ width: `${modPercent}%` }}
                                      />
                                    </div>
                                    <span className="text-[10px] text-muted-foreground w-8 text-right shrink-0">
                                      {mod.completed_lessons}/{mod.total_lessons}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>

                            {cp.enrolled_at && (
                              <p className="text-[10px] text-muted-foreground mt-2">
                                Eingeschrieben seit {new Date(cp.enrolled_at).toLocaleDateString('de-DE')}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Footer actions */}
              {!selectedUser.is_admin && (
                <div className="border-t px-6 py-4 flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => handleToggleActive(selectedUser.id)}
                  >
                    {selectedUser.is_active ? <ShieldOff className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                    {selectedUser.is_active ? 'Deaktivieren' : 'Aktivieren'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => handleDeleteUser(selectedUser.id, selectedUser.name)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Löschen
                  </Button>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
