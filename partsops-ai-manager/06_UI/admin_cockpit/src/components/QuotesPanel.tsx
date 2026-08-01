import { useEffect, useState } from 'react';
import { Button, Icon, InlineAlert } from './Primitives';
import { apiFetch } from '../lib/api';

type Quote = { quote_id: string; request_id: string; status: string; current_version: number; valid_until: string; updated_at: string };

export function QuotesPanel({ selectedRequestId }: { selectedRequestId?: string }) {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [requestId, setRequestId] = useState(selectedRequestId ?? '');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { const response = await apiFetch('/api/quotes'); if (!response.ok) throw new Error('quotes'); setQuotes(await response.json()); }
    catch { setError('Не удалось загрузить список КП. Повторите попытку после восстановления соединения.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (selectedRequestId) setRequestId(selectedRequestId); }, [selectedRequestId]);
  const issue = async () => {
    if (!requestId.trim()) return;
    setError(null);
    const response = await apiFetch('/api/quotes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request_id: requestId.trim() }) });
    if (!response.ok) { setError('КП можно выпустить только после согласования заявки, выбранных офферов и проверки маржи.'); return; }
    await load();
  };
  return <section className="space-y-4" aria-label="Коммерческие предложения">
    <div className="panel-card p-5 flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--accent-primary)]">QuoteOps</p><h2 className="text-lg font-bold text-[var(--text-primary)]">Коммерческие предложения</h2><p className="text-xs text-[var(--text-secondary)]">Каждая версия фиксирует подтверждённые цены и выбранные офферы.</p></div>
      <div className="flex gap-2"><input value={requestId} onChange={(event) => setRequestId(event.target.value)} placeholder="REQ-…" className="h-9 rounded-xl border border-[var(--border-default)] bg-[var(--surface-1)] px-3 text-xs text-[var(--text-primary)]" aria-label="ID согласованной заявки" /><Button size="sm" icon="plus" onClick={() => void issue()}>Выпустить КП</Button></div>
    </div>
    {error && <InlineAlert type="warning" message={error} />}
    <div className="panel-card overflow-hidden"><div className="flex items-center justify-between border-b border-[var(--border-default)] px-5 py-3"><h3 className="text-sm font-bold text-[var(--text-primary)]">Реестр КП</h3><Button size="sm" variant="secondary" icon="rotate" onClick={() => void load()} aria-label="Обновить КП" /></div>
      {loading ? <p className="p-5 text-xs text-[var(--text-secondary)]">Загрузка…</p> : quotes.length === 0 ? <p className="p-5 text-xs text-[var(--text-secondary)]">КП пока нет. Выберите согласованную заявку и выпустите первую версию.</p> : <div className="divide-y divide-[var(--border-default)]">{quotes.map((quote) => <div key={quote.quote_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-xs"><div><p className="font-mono font-semibold text-[var(--text-primary)]">{quote.quote_id} · v{quote.current_version}</p><p className="text-[var(--text-secondary)]">{quote.request_id} · действует до {new Date(quote.valid_until).toLocaleDateString('ru-RU')}</p></div><div className="flex items-center gap-2"><span className="rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-700">{quote.status}</span><a href={`/api/quotes/${quote.quote_id}/export/pdf`} className="rounded-lg border border-[var(--border-default)] px-2 py-1 text-[var(--accent-primary)]"><Icon name="document" size={12} /> PDF</a><a href={`/api/quotes/${quote.quote_id}/export/xlsx`} className="rounded-lg border border-[var(--border-default)] px-2 py-1 text-[var(--accent-primary)]">XLSX</a></div></div>)}</div>}
    </div>
  </section>;
}
