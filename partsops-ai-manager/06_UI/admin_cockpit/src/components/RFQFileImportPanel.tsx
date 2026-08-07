import { useEffect, useState } from 'react';
import { Button, Icon, InlineAlert, SectionCard } from './Primitives';
import { apiJson, uploadAttachment } from '../lib/api';

type Mapping = Record<string, string>;
type Preview = { artifact_id: string; headers: string[]; mapping: Mapping; valid_positions: number; invalid_rows: number; sample_positions: Array<{ part_number: string; description: string; quantity: number; brand: string }>; requires_mapping: boolean };
type SavedMapping = { name: string; mapping: Mapping };

export function RFQFileImportPanel({ onImported }: { onImported: (requestId: string) => void }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMappings, setSavedMappings] = useState<SavedMapping[]>([]);
  const [mappingName, setMappingName] = useState('');

  useEffect(() => { void apiJson<SavedMapping[]>('/api/rfq-imports/mappings').then(setSavedMappings).catch(() => setSavedMappings([])); }, []);

  const requestPreview = async (artifactId: string, mapping?: Mapping) => {
    const next = await apiJson<Preview>('/api/rfq-imports/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ artifact_id: artifactId, mapping }) });
    setPreview(next);
  };
  const selectFile = async (file?: File) => {
    if (!file) return;
    setBusy(true); setError(null); setPreview(null);
    try { const upload = await uploadAttachment(file); await requestPreview(upload.artifact_id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось обработать файл'); }
    finally { setBusy(false); }
  };
  const updateMapping = async (field: string, column: string) => {
    if (!preview) return;
    setBusy(true); setError(null);
    try { await requestPreview(preview.artifact_id, { ...preview.mapping, [field]: column }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось обновить preview'); }
    finally { setBusy(false); }
  };
  const commit = async () => {
    if (!preview) return;
    setBusy(true); setError(null);
    try { const result = await apiJson<{ request: { request_id: string } }>('/api/rfq-imports/commit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ artifact_id: preview.artifact_id, mapping: preview.mapping }) }); onImported(result.request.request_id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось создать заявку'); }
    finally { setBusy(false); }
  };
  const saveCurrentMapping = async () => {
    if (!preview || !mappingName.trim()) return;
    setBusy(true); setError(null);
    try { const saved = await apiJson<SavedMapping>('/api/rfq-imports/mappings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: mappingName, mapping: preview.mapping }) }); setSavedMappings((current) => [...current.filter((item) => item.name !== saved.name), saved]); setMappingName(''); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось сохранить mapping'); }
    finally { setBusy(false); }
  };
  const selector = (field: string, label: string, required = false) => <label className="grid gap-1 text-[11px] font-semibold text-ink-secondary">{label}<select aria-label={label} value={preview?.mapping[field] ?? ''} disabled={busy} onChange={(event) => void updateMapping(field, event.target.value)} className="rounded-control border border-line bg-surface-1 px-2 py-1.5 text-xs text-ink-primary"><option value="">{required ? 'Выберите колонку' : 'Не использовать'}</option>{preview?.headers.map((header) => <option key={header} value={header}>{header}</option>)}</select></label>;

  return <section aria-label="Входящие RFQ"><SectionCard title="Входящие RFQ" icon="file-import"><div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-xl text-xs leading-relaxed text-ink-secondary">Загрузите CSV или XLSX. Перед созданием заявки система покажет распознанные позиции.</p><label className="inline-flex cursor-pointer items-center gap-1.5 rounded-control border border-line bg-surface-2 px-3 py-2 text-xs font-semibold text-ink-secondary hover:bg-surface-3"><Icon name="file-arrow-up" size={14} />{busy ? 'Обработка…' : 'Выбрать файл'}<input className="sr-only" type="file" accept=".csv,.xlsx" onChange={(event) => void selectFile(event.target.files?.[0])} disabled={busy} /></label></div>{error && <div className="mt-3"><InlineAlert type="danger" message={error} /></div>}{preview && <div className="mt-4 rounded-control border border-line bg-surface-2 p-4">{preview.requires_mapping && <div className="mb-4 grid gap-3 border-b border-line pb-4 sm:grid-cols-3">{savedMappings.length > 0 && <label className="grid gap-1 text-[11px] font-semibold text-ink-secondary">Сохранённый mapping<select aria-label="Сохранённый mapping" defaultValue="" onChange={(event) => { const found = savedMappings.find((item) => item.name === event.target.value); if (found) void requestPreview(preview.artifact_id, found.mapping); }} className="rounded-control border border-line bg-surface-1 px-2 py-1.5 text-xs"><option value="">Выберите схему</option>{savedMappings.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>}{selector('part_number', 'Артикул', true)}{selector('description', 'Наименование', true)}{selector('quantity', 'Количество')}</div>}<div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs font-bold text-ink-primary">Подтверждено позиций: <span data-numeric>{preview.valid_positions}</span>{preview.invalid_rows ? ` · пропущено строк: ${preview.invalid_rows}` : ''}</p><Button size="sm" variant="primary" icon="plus" disabled={preview.requires_mapping || preview.valid_positions === 0 || busy} onClick={() => void commit()}>Создать заявку</Button></div>{!preview.requires_mapping && <div className="mt-3 flex flex-wrap gap-2"><input aria-label="Название mapping" value={mappingName} onChange={(event) => setMappingName(event.target.value)} placeholder="Название mapping" className="rounded-control border border-line bg-surface-1 px-2 py-1 text-xs" /><Button size="sm" variant="secondary" disabled={!mappingName.trim() || busy} onClick={() => void saveCurrentMapping()}>Сохранить mapping</Button></div>}<div className="mt-3 overflow-x-auto"><table className="w-full text-left text-[11px]"><tbody>{preview.sample_positions.map((part, index) => <tr key={`${part.part_number}-${index}`} className="border-t border-line-subtle text-ink-secondary"><td className="py-2 pr-3 font-mono">{part.part_number || '—'}</td><td className="py-2 pr-3">{part.description || part.brand || '—'}</td><td data-numeric className="py-2 text-right font-mono">{part.quantity}</td></tr>)}</tbody></table></div></div>}</SectionCard></section>;
}
