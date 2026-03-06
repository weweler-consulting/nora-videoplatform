import { useEffect, useState } from 'react';
import { api, type UserWithEnrollments, type CourseListItem } from '../../lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, X, UserPlus, Trash2, ShieldCheck, ShieldOff, Copy, Check } from 'lucide-react';

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
  const [enrollingUserId, setEnrollingUserId] = useState<string | null>(null);
  const [inviteResult, setInviteResult] = useState<{ name: string; email: string; password: string; courseTitle: string; emailSent: boolean } | null>(null);
  const [copied, setCopied] = useState(false);
  const [filterCourseId, setFilterCourseId] = useState('');

  const load = () => {
    Promise.all([api.getUsers(), api.getAllCourses()])
      .then(([u, c]) => { setUsers(u); setCourses(c); })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

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
    try { await api.enrollUser(userId, courseId); setEnrollingUserId(null); load(); }
    catch (err: any) { alert(err.message || 'Fehler beim Zuordnen.'); }
  };

  const handleRemoveEnrollment = async (enrollmentId: string, userName: string, courseTitle: string) => {
    if (!confirm(`${userName} aus "${courseTitle}" entfernen?`)) return;
    await api.removeEnrollment(enrollmentId); load();
  };

  const handleToggleActive = async (userId: string) => {
    try { await api.toggleUserActive(userId); load(); }
    catch (err: any) { alert(err.message || 'Fehler.'); }
  };

  const handleDeleteUser = async (userId: string, name: string) => {
    if (!confirm(`Nutzer "${name}" wirklich löschen? Alle Daten gehen verloren.`)) return;
    try { await api.deleteUser(userId); load(); }
    catch (err: any) { alert(err.message || 'Fehler beim Löschen.'); }
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
                <TableHead className="text-xs text-right">Aktionen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-12">
                    {filterCourseId ? 'Keine Nutzer in diesem Kurs.' : 'Noch keine Nutzer vorhanden.'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{user.name}</span>
                        {user.is_admin && <Badge variant="warning">Admin</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1">
                        {user.enrollments.map((enr) => (
                          <Badge key={enr.enrollment_id} variant="secondary" className="gap-1 pr-1">
                            {enr.course_title}
                            <button
                              onClick={() => handleRemoveEnrollment(enr.enrollment_id, user.name, enr.course_title)}
                              className="ml-0.5 rounded-full hover:bg-foreground/10 p-0.5"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                        {!user.is_admin && (
                          enrollingUserId === user.id ? (
                            <select
                              autoFocus
                              className="h-6 text-xs border border-input rounded px-1 bg-transparent focus:outline-none focus:ring-1 focus:ring-ring"
                              value=""
                              onChange={(e) => handleEnrollUser(user.id, e.target.value)}
                              onBlur={() => setEnrollingUserId(null)}
                            >
                              <option value="">+Kurs...</option>
                              {courses
                                .filter((c) => !user.enrollments.some((enr) => enr.course_id === c.id))
                                .map((c) => (
                                  <option key={c.id} value={c.id}>{c.title}</option>
                                ))}
                            </select>
                          ) : (
                            <button
                              onClick={() => setEnrollingUserId(user.id)}
                              className="inline-flex items-center justify-center h-5 w-5 rounded-full border border-dashed border-muted-foreground/30 text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                            >
                              <Plus className="h-3 w-3" />
                            </button>
                          )
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
                    <TableCell className="text-right">
                      {!user.is_admin && (
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-muted-foreground"
                            onClick={() => handleToggleActive(user.id)}
                          >
                            {user.is_active ? <ShieldOff className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                            {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            onClick={() => handleDeleteUser(user.id, user.name)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
