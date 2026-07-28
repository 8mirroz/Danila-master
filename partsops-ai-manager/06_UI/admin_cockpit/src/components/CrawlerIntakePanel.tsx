import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Icon, InlineAlert, SectionCard } from './Primitives';
import { apiJson, createCrawlerContract } from '../lib/api';
import type { ContractPositionDraft } from '../lib/api';
import type { SupplierRecord } from './supplierTypes';
import { SupplierEditorModal } from './SupplierEditorModal';

type Props = {
  onCreated: (result: { requestId: string; positions: ContractPositionDraft[] }) => void;
};

const FALLBACK_SUPPLIERS: SupplierRecord[] = [
  {
    supplier_id: 'sup_1',
    name: 'ООО «АвтоАльянс»',
    contact_person: 'Иванов Алексей',
    phone: '+7-495-123-4567',
    email: 'sales@autoalliance.ru',
    city: 'Москва',
    specialization: 'BMW, Audi, Mercedes',
    reliability_score: 0.92,
    avg_delivery_days: 2,
    status: 'active',
    rating_manual: 4.8,
    rating_auto: 4.7,
    account_owner: 'Ops North',
    payment_terms: 'Net 14',
    delivery_terms: 'EXW Moscow',
    currency_default: 'RUB',
    notes_internal: '',
    last_feed_at: '2026-07-28T10:00:00Z',
    last_sync_status: 'synced',
    categories: ['brake', 'engine'],
    table_count: 1,
    active_table_count: 1,
    last_activity_at: '2026-07-28T10:00:00Z',
  },
  {
    supplier_id: 'sup_2',
    name: 'ИП Смирнов А.В.',
    contact_person: 'Смирнов Андрей',
    phone: '+7-812-987-6543',
    email: 'smirnov@spbparts.ru',
    city: 'Санкт-Петербург',
    specialization: 'VAG, Toyota, Nissan',
    reliability_score: 0.85,
    avg_delivery_days: 3,
    status: 'active',
    rating_manual: 4.5,
    rating_auto: 4.3,
    account_owner: 'Ops West',
    payment_terms: 'Net 30',
    delivery_terms: 'DDP',
    currency_default: 'RUB',
    notes_internal: '',
    last_feed_at: '2026-07-28T09:30:00Z',
    last_sync_status: 'synced',
    categories: ['filters', 'suspension'],
    table_count: 2,
    active_table_count: 1,
    last_activity_at: '2026-07-28T09:30:00Z',
  },
  {
    supplier_id: 'sup_3',
    name: 'ЕвроПартс Трейдинг',
    contact_person: 'Петров Дмитрий',
    phone: '+7-843-555-0199',
    email: 'info@europartskzn.ru',
    city: 'Казань',
    specialization: 'Volvo, Renault, DAF',
    reliability_score: 0.96,
    avg_delivery_days: 1,
    status: 'active',
    rating_manual: 4.9,
    rating_auto: 4.8,
    account_owner: 'Ops East',
    payment_terms: 'Prepaid',
    delivery_terms: 'FOB',
    currency_default: 'RUB',
    notes_internal: '',
    last_feed_at: '2026-07-28T11:15:00Z',
    last_sync_status: 'synced',
    categories: ['electrics', 'spark_plugs'],
    table_count: 1,
    active_table_count: 1,
    last_activity_at: '2026-07-28T11:15:00Z',
  },
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
  const [activeStep, setActiveStep] = useState<number>(0);

  // Suppliers Management State
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>(FALLBACK_SUPPLIERS);
  const [activeSupplierIds, setActiveSupplierIds] = useState<Set<string>>(
    () => new Set(FALLBACK_SUPPLIERS.map((s) => s.supplier_id))
  );
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<SupplierRecord | null>(null);

  const fetchSuppliersList = useCallback(async () => {
    try {
      const data = await apiJson<SupplierRecord[]>('/api/suppliers');
      if (data && data.length > 0) {
        setSuppliers(data);
        setActiveSupplierIds(new Set(data.map((s) => s.supplier_id)));
      }
    } catch {
      // Keep fallback suppliers if API is unavailable
    }
  }, []);

  useEffect(() => {
    void fetchSuppliersList();
  }, [fetchSuppliersList]);

  const preview = useMemo(() => parsePayload(rawText), [rawText]);

  const refreshPreview = () => {
    setError(null);
    setPositions(preview);
    if (!preview.length) {
      setError('Не удалось найти артикулы. Укажите по одному артикулу на строку или загрузите CSV/JSON.');
    } else {
      setActiveStep(2); // Jump to validation step
    }
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
    setActiveStep(1);
  };

  const toggleSupplierActive = (supplierId: string) => {
    setActiveSupplierIds((prev) => {
      const next = new Set(prev);
      if (next.has(supplierId)) {
        next.delete(supplierId);
      } else {
        next.add(supplierId);
      }
      return next;
    });
  };

  const handleOpenEditSupplier = (s: SupplierRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSupplier(s);
    setEditorOpen(true);
  };

  const handleOpenCreateSupplier = () => {
    setEditingSupplier(null);
    setEditorOpen(true);
  };

  const handleSupplierSaved = (saved: SupplierRecord) => {
    setSuppliers((prev) => {
      const idx = prev.findIndex((item) => item.supplier_id === saved.supplier_id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setActiveSupplierIds((prev) => new Set([...Array.from(prev), saved.supplier_id]));
    setMessage(`Поставщик «${saved.name}» успешно сохранен.`);
  };

  const createPackage = async () => {
    if (!positions.length) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createCrawlerContract(positions);
      setMessage(`Пакет ${result.request_id} создан: ${result.positions} позиций готовы к сбору.`);
      setActiveStep(3);
      onCreated({ requestId: result.request_id, positions });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать пакет сбора.');
    } finally {
      setBusy(false);
    }
  };

  const stepperItems = [
    { title: '1. Ввод запроса', sub: 'Текст или CSV файл' },
    { title: '2. Источники данных', sub: `${activeSupplierIds.size} поставщиков` },
    { title: '3. Валидация позиций', sub: `${positions.length} артикулов` },
    { title: '4. Запуск сбора', sub: 'ИИ-пайплайн' },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">
      {/* 1. Chevron Stepper Header */}
      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {stepperItems.map((st, idx) => {
            const isActive = activeStep === idx;
            const isCompleted = activeStep > idx;
            return (
              <button
                key={st.title}
                onClick={() => setActiveStep(idx)}
                className={`relative flex flex-col justify-between p-3.5 rounded-2xl text-left transition-all duration-300 select-none ${
                  isActive
                    ? 'bg-[var(--accent-primary)] text-white shadow-md scale-[1.01]'
                    : isCompleted
                    ? 'bg-emerald-50 border border-emerald-200 text-emerald-900 hover:bg-emerald-100/70'
                    : 'bg-slate-50 border border-slate-200/80 text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className={`text-[10px] font-black uppercase tracking-[0.16em] ${isActive ? 'text-white/80' : isCompleted ? 'text-emerald-700' : 'text-slate-400'}`}>
                    Шаг 0{idx + 1}
                  </span>
                  {isCompleted && (
                    <span className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">
                      ✓
                    </span>
                  )}
                </div>
                <div className={`text-xs font-black truncate ${isActive ? 'text-white' : ''}`}>
                  {st.title}
                </div>
                <div className={`text-[10px] font-medium truncate mt-0.5 ${isActive ? 'text-white/80' : isCompleted ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {st.sub}
                </div>
              </button>
            );
          })}
        </div>

        {/* Step Guide Hint */}
        <div className="mt-4 flex items-center gap-2 rounded-2xl bg-blue-50/60 border border-blue-100 px-4 py-2.5 text-xs text-blue-900 font-semibold">
          <Icon name="circle-info" size={16} className="text-[var(--accent-primary)] shrink-0" />
          <span>
            {activeStep === 0 && 'Шаг 1: Укажите артикулы списком в текстовом поле или загрузите готовый файл CSV / JSON.'}
            {activeStep === 1 && 'Шаг 2: Выберите активных поставщиков для сбора цен или отредактируйте параметры договоров.'}
            {activeStep === 2 && 'Шаг 3: Проверьте распознанные артикулы, наименования и количества перед отправкой на сбор.'}
            {activeStep === 3 && 'Шаг 4: Сформируйте пакет сбора и запустите мультиагентную обработку прайсов.'}
          </span>
        </div>
      </div>

      {/* 2. Main Intake & Sources Section */}
      <SectionCard title="1. Вход запроса и Подключение источников" icon="cloud-arrow-up">
        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Left Column: Text & File Upload */}
          <div>
            <label className="mb-2 block text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
              Артикулы и контекст
            </label>
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              rows={7}
              aria-label="Артикулы и контекст запроса"
              placeholder="OC90; масляный фильтр; 2&#10;W6103, воздушный фильтр"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 p-3.5 font-mono text-xs text-slate-800 outline-none transition focus:border-[var(--accent-primary)] focus:bg-white focus:ring-2 focus:ring-[var(--accent-primary)]/15"
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-50 hover:border-slate-300 shadow-sm">
                <Icon name="paperclip" size={14} className="text-[var(--accent-primary)]" />
                Загрузить CSV / TXT / JSON
                <input
                  className="hidden"
                  type="file"
                  accept=".csv,.txt,.json"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void handleFile(file);
                  }}
                />
              </label>
              <button
                onClick={refreshPreview}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-50 hover:border-slate-300 shadow-sm"
              >
                <Icon name="rotate" size={14} className="text-[var(--accent-primary)]" />
                Распознать позиции
              </button>
            </div>
            <p className="mt-2.5 text-[11px] leading-relaxed text-slate-400">
              Поддерживаются текстовые строки, CSV и JSON. Вы можете проверить позицию и количество до запуска.
            </p>
          </div>

          {/* Right Column: Real Supplier Sources Panel */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 flex flex-col justify-between">
            <div>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                    Источники поставщиков
                  </span>
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 shadow-xs">
                    {activeSupplierIds.size} подключены
                  </span>
                </div>
                <button
                  onClick={handleOpenCreateSupplier}
                  className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 shadow-xs"
                >
                  <Icon name="plus" size={10} />
                  Карточка
                </button>
              </div>

              <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1">
                {suppliers.map((supplier) => {
                  const isActive = activeSupplierIds.has(supplier.supplier_id);
                  const initials = supplier.name
                    .replace(/^(ООО|ИП|АО|ЗАО|ИП|ооо|ип|ао|зао)\s+["«]?/i, '')
                    .replace(/["»]/g, '')
                    .trim()
                    .slice(0, 2);

                  return (
                    <div
                      key={supplier.supplier_id}
                      onClick={() => toggleSupplierActive(supplier.supplier_id)}
                      className={`group relative flex cursor-pointer items-center justify-between rounded-2xl border p-3.5 transition-all duration-300 select-none ${
                        isActive
                          ? 'border-[rgba(37,99,235,0.3)] bg-white ring-1 ring-[rgba(37,99,235,0.18)] shadow-sm scale-[1.005]'
                          : 'border-slate-200/80 bg-white/70 hover:border-slate-300 hover:bg-white'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {/* Minimal LED status indicator */}
                        {isActive ? (
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)] animate-pulse shrink-0" />
                        ) : (
                          <span className="w-2.5 h-2.5 rounded-full bg-slate-300 shrink-0" />
                        )}

                        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-[10px] text-slate-600 shrink-0 uppercase">
                          {initials || 'П'}
                        </div>

                        <div className="min-w-0">
                          <div className="text-xs font-extrabold text-slate-900 truncate">
                            {supplier.name}
                          </div>
                          <div className="text-[10px] font-semibold text-slate-400 truncate">
                            {supplier.city || '—'} • {supplier.specialization || 'Запчасти'}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        <span className="text-[10px] font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                          SLA {supplier.avg_delivery_days}дн.
                        </span>
                        <button
                          onClick={(e) => handleOpenEditSupplier(supplier, e)}
                          className="w-7 h-7 rounded-xl bg-slate-100/80 hover:bg-slate-200/80 text-slate-500 hover:text-slate-800 flex items-center justify-center transition-colors"
                          title="Редактировать карточку поставщика"
                        >
                          <Icon name="pencil" size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </SectionCard>

      {message && <InlineAlert type="success" message={message} />}
      {error && <InlineAlert type="warning" message={error} />}

      {/* 3. Positions Validation Section */}
      <SectionCard title={`2. Проверка позиций · ${positions.length}`} icon="list">
        {positions.length ? (
          <div className="space-y-3">
            {positions.map((item, index) => (
              <div
                key={`${item.part_number}-${index}`}
                className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 md:grid-cols-[0.8fr_1.4fr_100px]"
              >
                <div>
                  <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Артикул</label>
                  <input
                    value={item.part_number}
                    onChange={(event) => updatePosition(index, 'part_number', event.target.value)}
                    aria-label={`Артикул ${index + 1}`}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
                  />
                </div>
                <div>
                  <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Наименование / параметры</label>
                  <input
                    value={item.description ?? ''}
                    onChange={(event) => updatePosition(index, 'description', event.target.value)}
                    placeholder="Наименование / параметры"
                    aria-label={`Наименование ${index + 1}`}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
                  />
                </div>
                <div>
                  <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Кол-во</label>
                  <input
                    type="number"
                    min="1"
                    value={item.quantity}
                    onChange={(event) => updatePosition(index, 'quantity', event.target.value)}
                    aria-label={`Количество ${index + 1}`}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
                  />
                </div>
              </div>
            ))}
            <div className="flex justify-end border-t border-slate-100 pt-4">
              <button
                disabled={busy}
                onClick={() => void createPackage()}
                className="rounded-2xl bg-[var(--accent-primary)] px-6 py-3 text-xs font-bold text-white transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 flex items-center gap-2 shadow-sm"
              >
                {busy && <Icon name="spinner" size={14} className="animate-spin" />}
                {busy ? 'Создаём пакет…' : 'Создать пакет и подготовить сбор'}
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-xs text-slate-500">
            После распознавания здесь появятся позиции для проверки.
          </div>
        )}
      </SectionCard>

      {/* Supplier Modal Editor */}
      <SupplierEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        supplier={editingSupplier}
        onSaved={handleSupplierSaved}
      />
    </div>
  );
};
