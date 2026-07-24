import React, { useMemo, useState } from 'react';
import { ActionButton, InlineAlert, SectionCard } from './Primitives';
import { createCrawlerContract } from '../lib/api';
import type { ContractPositionDraft } from '../lib/api';

type Props = {
  onCreated: (result: { requestId: string; positions: ContractPositionDraft[] }) => void;
};

const SOURCES = [
  { name: 'Exist.ru', detail: 'оригиналы, аналоги, цена, доставка' },
  { name: 'Autodoc.ru', detail: 'JS-поиск, карточки, наличие' },
  { name: 'Rossko.ru', detail: 'бренд, артикул, цена, доставка' },
];

function parseQuantity(value: string): number {
  const match = value.match(/(?:^|\s|[xх*])([1-9]\d*)\s*$/i);
  return match ? Number(match[1]) : 1;
}

function parseLine(line: string): ContractPositionDraft | null {
  const value = line.trim().replace(/^[-*•]+\s*/, '');
  if (!value || value.startsWith('#')) return null;

  const columns = value.split(/[;,\t]/).map((column) => column.trim()).filter(Boolean);
  const fields = columns.length > 1 ? columns : value.split(/\s+/);
  const partNumber = fields.shift()?.replace(/^['"]|['"]$/g, '');
  if (!partNumber || !/[A-Za-zА-Яа-я0-9]/.test(partNumber)) return null;

  const quantityField = fields.at(-1) ?? '';
  const quantity = parseQuantity(quantityField);
  if (/^(?:x|х)?[1-9]\d*$/i.test(quantityField.trim())) fields.pop();
  const description = fields.join(' ').trim();
  return {
    part_number: partNumber,
    description: description || undefined,
    quantity,
  };
}

function parsePayload(text: string): ContractPositionDraft[] {
  try {
    const parsed = JSON.parse(text) as unknown;
    const rows = Array.isArray(parsed)
      ? parsed
      : parsed && typeof parsed === 'object'
        ? ((parsed as { positions?: unknown[]; articles?: unknown[] }).positions
          ?? (parsed as { articles?: unknown[] }).articles
          ?? [])
        : [];
    return rows.flatMap((row) => {
      if (typeof row === 'string') return parseLine(row) ? [parseLine(row)!] : [];
      if (!row || typeof row !== 'object') return [];
      const item = row as Record<string, unknown>;
      const partNumber = String(item.part_number ?? item.article ?? item.oem ?? item.OEM ?? '').trim();
      if (!partNumber) return [];
      return [{
        part_number: partNumber,
        description: String(item.description ?? item.name ?? item.part_name ?? '').trim() || undefined,
        quantity: Math.max(1, Number(item.quantity ?? item.qty ?? 1) || 1),
      }];
    });
  } catch {
    return text.split(/\r?\n/).flatMap((line) => {
      const parsed = parseLine(line);
      return parsed ? [parsed] : [];
    });
  }
}

export const CrawlerIntakePanel: React.FC<Props> = ({ onCreated }) => {
  const [rawText, setRawText] = useState('OC90\tмасляный фильтр\t2\nW6103\tвоздушный фильтр\t1\n04E115561H\tсвеча зажигания\t4');
  const [positions, setPositions] = useState<ContractPositionDraft[]>(() => parsePayload(rawText));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const preview = useMemo(() => parsePayload(rawText), [rawText]);

  const refreshPreview = () => {
    setError(null);
    setPositions(preview);
    if (!preview.length) setError('Не удалось найти артикулы. Укажите по одному артикулу на строку или загрузите CSV/JSON.');
  };

  const updatePosition = (index: number, field: keyof ContractPositionDraft, value: string) => {
    setPositions((current) => current.map((item, itemIndex) => itemIndex === index
      ? { ...item, [field]: field === 'quantity' ? Math.max(1, Number(value) || 1) : value }
      : item));
  };

  const handleFile = async (file: File) => {
    setRawText(await file.text());
    setMessage(`Файл «${file.name}» загружен. Проверьте распознанные позиции.`);
    setError(null);
  };

  const createPackage = async () => {
    if (!positions.length) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createCrawlerContract(positions);
      setMessage(`Пакет ${result.request_id} создан: ${result.positions} позиций готовы к сбору.`);
      onCreated({ requestId: result.request_id, positions });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать пакет сбора.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <SectionCard title="1. Вход запроса" icon="fa-inbox">
        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <label className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              Артикулы и контекст
            </label>
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              rows={8}
              aria-label="Артикулы и контекст запроса"
              placeholder="OC90; масляный фильтр; 2\nW6103, воздушный фильтр"
              className="w-full rounded-xl border border-[var(--border-default)] bg-[var(--surface-1)] p-3 font-mono text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/15"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--surface-1)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-2)]">
                <i className="fas fa-paperclip text-[var(--accent-primary)]" />
                Загрузить CSV / TXT / JSON
                <input className="hidden" type="file" accept=".csv,.txt,.json" onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleFile(file);
                }} />
              </label>
              <ActionButton variant="secondary" icon="fa-wand-magic-sparkles" onClick={refreshPreview}>
                Распознать позиции
              </ActionButton>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-muted)]">
              Поддерживаются строки, CSV и JSON. Артикул, наименование и количество можно проверить до запуска.
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-2)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[var(--text-muted)]">Источники</span>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">3 подключены</span>
            </div>
            <div className="space-y-2">
              {SOURCES.map((source) => (
                <div key={source.name} className="flex items-start gap-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-1)] p-3">
                  <i className="fas fa-circle-check mt-0.5 text-emerald-600" />
                  <div>
                    <div className="text-xs font-bold text-[var(--text-primary)]">{source.name}</div>
                    <div className="mt-0.5 text-[10px] text-[var(--text-muted)]">{source.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </SectionCard>

      {message && <InlineAlert type="success" message={message} />}
      {error && <InlineAlert type="warning" message={error} />}

      <SectionCard title={`2. Проверка позиций · ${positions.length}`} icon="fa-list-check">
        {positions.length ? (
          <div className="space-y-2">
            {positions.map((item, index) => (
              <div key={`${item.part_number}-${index}`} className="grid gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-1)] p-3 md:grid-cols-[0.7fr_1.3fr_90px]">
                <input value={item.part_number} onChange={(event) => updatePosition(index, 'part_number', event.target.value)} aria-label={`Артикул ${index + 1}`} className="rounded-md border border-[var(--border-default)] bg-[var(--surface-2)] px-2 py-2 font-mono text-xs" />
                <input value={item.description ?? ''} onChange={(event) => updatePosition(index, 'description', event.target.value)} placeholder="Наименование / параметры" aria-label={`Наименование ${index + 1}`} className="rounded-md border border-[var(--border-default)] bg-[var(--surface-2)] px-2 py-2 text-xs" />
                <input type="number" min="1" value={item.quantity} onChange={(event) => updatePosition(index, 'quantity', event.target.value)} aria-label={`Количество ${index + 1}`} className="rounded-md border border-[var(--border-default)] bg-[var(--surface-2)] px-2 py-2 text-xs" />
              </div>
            ))}
            <div className="flex justify-end border-t border-[var(--border-subtle)] pt-4">
              <ActionButton variant="primary" icon="fa-play" disabled={busy} onClick={() => void createPackage()}>
                {busy ? 'Создаём пакет…' : 'Создать пакет и подготовить сбор'}
              </ActionButton>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[var(--border-strong)] p-6 text-center text-xs text-[var(--text-muted)]">После распознавания здесь появятся позиции для проверки.</div>
        )}
      </SectionCard>
    </div>
  );
};
