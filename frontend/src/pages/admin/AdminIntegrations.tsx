import { useEffect, useState } from 'react';
import { api, type ServiceTokenInfo } from '../../lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Copy, Check, Trash2, Plus } from 'lucide-react';

export default function AdminIntegrations() {
  const [tokens, setTokens] = useState<ServiceTokenInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [createError, setCreateError] = useState('');
  const [justCreated, setJustCreated] = useState<(ServiceTokenInfo & { token: string }) | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => {
    api.listServiceTokens()
      .then(setTokens)
      .catch(() => setTokens([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    if (!newName.trim()) {
      setCreateError('Name erforderlich.');
      return;
    }
    try {
      const created = await api.createServiceToken(newName.trim());
      setJustCreated(created);
      setNewName('');
      setShowCreate(false);
      setCopied(false);
      load();
    } catch (err: any) {
      setCreateError(err?.message || 'Fehler beim Erstellen.');
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Token "${name}" wirklich löschen? Alle Systeme, die ihn nutzen, verlieren den Zugang.`)) return;
    try {
      await api.deleteServiceToken(id);
      load();
    } catch (err: any) {
      alert(err?.message || 'Fehler beim Löschen.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-muted border-t-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-bold">Integrationen</h2>
          <p className="text-sm text-muted-foreground">
            Service-Tokens für externe Systeme (z.B. CRM), die Einladungen auslösen dürfen.
          </p>
        </div>
        <Button onClick={() => { setShowCreate(!showCreate); setCreateError(''); }} size="sm">
          <Plus className="h-4 w-4" />
          Token erzeugen
        </Button>
      </div>

      {showCreate && (
        <Card className="mb-5">
          <CardHeader className="pb-4">
            <CardTitle className="text-sm">Neuer Service-Token</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-3">
              {createError && (
                <div className="bg-destructive/10 text-destructive text-sm px-3 py-2 rounded-md">{createError}</div>
              )}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Name / Zweck</label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="z.B. Nora CRM"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowCreate(false)}>
                  Abbrechen
                </Button>
                <Button type="submit" size="sm">Erzeugen</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {justCreated && (
        <Card className="mb-5 border-green-200 bg-green-50/50">
          <CardContent className="pt-5">
            <p className="text-sm font-medium mb-2">
              Token "{justCreated.name}" erzeugt. <strong>Jetzt kopieren — er wird nie wieder angezeigt.</strong>
            </p>
            <div className="bg-white rounded-md p-3 text-xs text-muted-foreground font-mono leading-relaxed border break-all">
              {justCreated.token}
            </div>
            <div className="flex gap-2 mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(justCreated.token);
                  setCopied(true);
                }}
              >
                {copied ? <><Check className="h-3.5 w-3.5" /> Kopiert!</> : <><Copy className="h-3.5 w-3.5" /> Kopieren</>}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setJustCreated(null)}>
                Schließen
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs">Name</TableHead>
                <TableHead className="text-xs">Erzeugt</TableHead>
                <TableHead className="text-xs">Zuletzt genutzt</TableHead>
                <TableHead className="text-xs w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tokens.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-10">
                    Noch keine Tokens erzeugt.
                  </TableCell>
                </TableRow>
              ) : (
                tokens.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium text-sm">{t.name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(t.created_at).toLocaleDateString('de-DE')}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {t.last_used_at
                        ? new Date(t.last_used_at).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDelete(t.id, t.name)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
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
