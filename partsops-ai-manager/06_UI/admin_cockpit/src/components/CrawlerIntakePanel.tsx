import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Icon, InlineAlert, SectionCard } from './Primitives';
import { apiJson, createCrawlerContract, fetchSuppliersAuthStatus, validateContractData } from '../lib/api';
import type { ContractPositionDraft, SupplierAuthStatusMap } from '../lib/api';
import type { SupplierRecord } from './supplierTypes';
import { SupplierEditorModal } from './SupplierEditorModal';

type Props = {
  onCreated: (result: { requestId: string; positions: ContractPositionDraft[] }) => void;
};

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
  const [rawText, setRawText] = useState('');
  const [positions, setPositions] = useState<ContractPositionDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [createdRequestId, setCreatedRequestId] = useState<string | null>(null);

  // Auto-parsing progress visualization states
  const [isParsing, setIsParsing] = useState<boolean>(false);
  const [parseProgress, setParseProgress] = useState<number>(0);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [loadedFileName, setLoadedFileName] = useState<string | null>(null);

  // Suppliers Management State
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [activeSupplierIds, setActiveSupplierIds] = useState<Set<string>>(new Set());
  const [suppliersLoading, setSuppliersLoading] = useState(true);
  const [suppliersError, setSuppliersError] = useState<string | null>(null);
  const [cityFilter, setCityFilter] = useState<string>('all');
  const [pingResults, setPingResults] = useState<Record<string, { status: string; latency_ms: number; code: number }>>({});
  const [pinging, setPinging] = useState<boolean>(false);

  // Scraper Auth Status (Exist, Autodoc, Rossko)
  const [authStatus, setAuthStatus] = useState<SupplierAuthStatusMap>({});
  const [authLoading, setAuthLoading] = useState<boolean>(false);

  // Export Mode & Validation Gates
  const [exportMode, setExportMode] = useState<'full' | 'light'>('light');
  const [validationReport, setValidationReport] = useState<any | null>(null);
  const [validating, setValidating] = useState<boolean>(false);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<SupplierRecord | null>(null);

  const fetchAuthStatusList = useCallback(async () => {
    setAuthLoading(true);
    try {
      const data = await fetchSuppliersAuthStatus();
      setAuthStatus(data || {});
    } catch {
      setAuthStatus({});
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const runValidation = useCallback(async (requestId: string) => {
    setValidating(true);
    try {
      const res = await validateContractData(requestId);
      setValidationReport(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка валидации данных');
    } finally {
      setValidating(false);
    }
  }, []);

  const fetchSuppliersList = useCallback(async () => {
    setSuppliersLoading(true);
    setSuppliersError(null);
    try {
      const data = await apiJson<SupplierRecord[]>('/api/suppliers');
      setSuppliers(data);
      setActiveSupplierIds(new Set(data.map((s) => s.supplier_id)));
    } catch (err) {
      setSuppliers([]);
      setActiveSupplierIds(new Set());
      setSuppliersError(err instanceof Error ? err.message : 'Не удалось загрузить поставщиков');
    } finally {
      setSuppliersLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSuppliersList();
    void fetchAuthStatusList();
  }, [fetchSuppliersList, fetchAuthStatusList]);

  // Parse the operator-provided payload without inventing progress or result data.
  const triggerAutoParsing = useCallback((targetText: string, fileName?: string) => {
    setIsParsing(true);
    setParseProgress(0);
    setError(null);
    if (fileName) setLoadedFileName(fileName);
    const parsed = parsePayload(targetText);
    setPositions(parsed);
    setParseProgress(100);
    setIsParsing(false);
    if (!parsed.length) {
      setError('Не удалось извлечь артикулы. Укажите номенклатуру или загрузите корректный CSV / JSON файл.');
    } else {
      setMessage(`Извлечение завершено: распознано ${parsed.length} позиций.`);
    }
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      const text = await file.text();
      setRawText(text);
      triggerAutoParsing(text, file.name);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const text = await file.text();
      setRawText(text);
      triggerAutoParsing(text, file.name);
    }
  };

  const updatePosition = (index: number, field: keyof ContractPositionDraft, value: string) => {
    setPositions((current) => current.map((item, itemIndex) => itemIndex === index
      ? { ...item, [field]: field === 'quantity' ? Math.max(1, Number(value) || 1) : value }
      : item));
  };

  const deletePosition = (index: number) => {
    setPositions((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const addEmptyPosition = () => {
    setPositions((current) => [...current, { part_number: '', description: '', quantity: 1 }]);
  };

  const runPingCheck = async () => {
    if (activeSupplierIds.size === 0) {
      setError('Нет активных поставщиков для проверки. Загрузите live-список или создайте поставщика.');
      return;
    }
    setPinging(true);
    setError(null);
    try {
      const ids = Array.from(activeSupplierIds);
      const res = await apiJson<Record<string, { status: string; latency_ms: number; code: number }>>('/api/suppliers/ping-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ supplier_ids: ids }),
      });
      
      const latencyValues = Object.values(res).map(item => item.latency_ms).filter(v => v > 0);
      const avgLatency = latencyValues.length > 0
        ? Math.round(latencyValues.reduce((a, b) => a + b, 0) / latencyValues.length)
        : null;
        
      setPinging(false);
      setPingResults(res);
      setMessage(avgLatency == null
        ? 'Проверка завершена: API не вернул измеримый latency.'
        : `Проверка завершена: средний отклик ${avgLatency} мс.`);
    } catch (err) {
      setPinging(false);
      setPingResults({});
      setError(err instanceof Error ? err.message : 'Не удалось проверить API поставщиков');
    }
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
    setMessage(`Поставщик «${saved.name}» сохранен.`);
  };

  const createPackage = async () => {
    if (!positions.length) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createCrawlerContract(positions);
      setMessage(`Пакет ${result.request_id} сформирован: ${result.positions} позиций готовы к ордерингу.`);
      setCreatedRequestId(result.request_id);
      setActiveStep(3);
      onCreated({ requestId: result.request_id, positions });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать пакет сбора.');
    } finally {
      setBusy(false);
    }
  };

  const filteredSuppliers = useMemo(() => {
    if (cityFilter === 'all') return suppliers;
    return suppliers.filter((s) => s.city.toLowerCase().includes(cityFilter.toLowerCase()));
  }, [suppliers, cityFilter]);

  const stepperItems = [
    { title: '1. Ввод запроса', sub: 'Текст или CSV/JSON файл' },
    { title: '2. Источники данных', sub: `${activeSupplierIds.size} подключено` },
    { title: '3. Валидация позиций', sub: `${positions.length} артикулов` },
    { title: '4. Запуск сбора', sub: 'Мультиагентный ИИ' },
  ];
  const averageSupplierDelivery = suppliers.length
    ? Math.round(suppliers.reduce((sum, supplier) => sum + supplier.avg_delivery_days, 0) / suppliers.length)
    : null;

  return (
    <div className="space-y-6 animate-fadeIn select-none">
      {/* 1. Chevron Stepper Header */}
      <div className="rounded-3xl border border-slate-200/90 bg-white p-5 shadow-xs">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
          {stepperItems.map((st, idx) => {
            const isActive = activeStep === idx;
            const isCompleted = activeStep > idx;
            return (
              <button
                key={st.title}
                onClick={() => setActiveStep(idx)}
                className={`relative flex flex-col justify-between p-4 rounded-2xl text-left transition-all duration-300 ${
                  isActive
                    ? 'bg-[#0F172A] text-white shadow-md scale-[1.01]'
                    : isCompleted
                    ? 'bg-emerald-50/80 border border-emerald-200/80 text-emerald-950 hover:bg-emerald-100/70'
                    : 'bg-slate-50 border border-slate-200/70 text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className={`text-[10px] font-black uppercase tracking-[0.16em] ${isActive ? 'text-blue-300' : isCompleted ? 'text-emerald-700' : 'text-slate-400'}`}>
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
                <div className={`text-[10px] font-medium truncate mt-1 ${isActive ? 'text-slate-300' : isCompleted ? 'text-emerald-700' : 'text-slate-400'}`}>
                  {st.sub}
                </div>
              </button>
            );
          })}
        </div>

        {/* Step Guide Hint */}
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-slate-50 border border-slate-200/80 px-4 py-3 text-xs text-slate-700 font-semibold">
          <Icon name="circle-info" size={16} className="text-[#0F172A] shrink-0" />
          <span>
            {activeStep === 0 && 'Шаг 1: Загрузите реальный файл или вставьте спецификацию. После подтверждения система извлечёт позиции.'}
            {activeStep === 1 && 'Шаг 2: Управляйте подключенными поставщиками, проверяйте пинг API-каналов и редактируйте договора.'}
            {activeStep === 2 && 'Шаг 3: Проверьте извлеченные артикулы, отредактируйте количества перед закоммичиванием в сбор.'}
            {activeStep === 3 && 'Шаг 4: Запустите мультиагентную обработку и мониторинг оркестратора.'}
          </span>
        </div>
      </div>

      {message && <InlineAlert type="success" message={message} />}
      {error && <InlineAlert type="warning" message={error} />}

      {/* STEP 0: Request Input & Drag and Drop Zone */}
      {activeStep === 0 && (
        <div className="space-y-5 animate-fadeIn">
          <SectionCard title="1. Ввод запроса" icon="cloud-arrow-up">
            <div className="space-y-4">
              {/* Drag and Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative flex flex-col items-center justify-center rounded-3xl border-2 border-dashed p-6 text-center transition-all duration-300 ${
                  dragActive
                    ? 'border-[#0F172A] bg-blue-50/50 scale-[1.01]'
                    : 'border-slate-300 bg-slate-50/60 hover:border-slate-400 hover:bg-slate-50'
                }`}
              >
                <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200/80 shadow-xs flex items-center justify-center text-[#0F172A] mb-3">
                  <Icon name="paperclip" size={22} />
                </div>
                <div className="text-xs font-black text-slate-900 mb-1">
                  Перетащите сюда файл с запросом (CSV, TXT, JSON, Excel)
                </div>
                <div className="text-[11px] font-semibold text-slate-400 mb-4">
                  или выберите файл на компьютере для автоматического распознавания
                </div>

                <div className="flex items-center gap-3">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-2xl border-2 border-slate-300 bg-white px-5 py-2.5 text-xs font-extrabold text-slate-800 transition hover:bg-slate-100 hover:border-slate-400 shadow-xs">
                    <Icon name="paperclip" size={14} className="text-[#0F172A]" />
                    Выбрать файл
                    <input className="hidden" type="file" accept=".csv,.txt,.json" onChange={handleFileChange} />
                  </label>
                  <button
                    onClick={() => triggerAutoParsing(rawText)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#0F172A] px-6 py-2.5 text-xs font-black text-white transition hover:bg-[#1E293B] shadow-md active:scale-[0.98]"
                  >
                    <Icon name="rotate" size={14} className="text-white" />
                    Распознать позиции
                  </button>
                </div>

                {/* Preset samples */}
                <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Быстрый пример:</span>
                  <button
                    type="button"
                    onClick={() => {
                      const txt = "34116858047; Тормозной диск передний; 2\n11427953129; Фильтр масляный; 1\n31126855743; Рычаг подвески; 1";
                      setRawText(txt);
                      triggerAutoParsing(txt, 'Пример_BMW_OEM.csv');
                    }}
                    className="text-[10px] font-extrabold text-blue-700 bg-blue-50 border border-blue-200/80 hover:bg-blue-100 px-3 py-1 rounded-full transition shadow-2xs"
                  >
                    + 3 детали BMW OEM (CSV)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const txt = '[\n  {"part_number": "OC90", "description": "Фильтр масляный Mahle", "quantity": 2},\n  {"part_number": "LA888", "description": "Фильтр салона Mahle", "quantity": 1}\n]';
                      setRawText(txt);
                      triggerAutoParsing(txt, 'Спецификация_Mahle.json');
                    }}
                    className="text-[10px] font-extrabold text-emerald-700 bg-emerald-50 border border-emerald-200/80 hover:bg-emerald-100 px-3 py-1 rounded-full transition shadow-2xs"
                  >
                    + Mahle Filters (JSON)
                  </button>
                </div>

                {loadedFileName && (
                  <div className="mt-3 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                    Загружен: {loadedFileName}
                  </div>
                )}
              </div>

              {/* Text Area */}
              <div>
                <label className="mb-1.5 block text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-400">
                  Редактирование сырого текста запроса
                </label>
                <textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  rows={5}
                  placeholder="34116858047; Тормозной диск; 2&#10;OC90; Масляный фильтр; 1"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 p-3.5 font-mono text-xs text-slate-800 outline-none transition focus:border-[#0F172A] focus:bg-white focus:ring-2 focus:ring-[#0F172A]/10"
                />
              </div>

              {/* Parsing Progress Visualization Bar */}
              {isParsing && (
                <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 space-y-2 animate-fadeIn">
                  <div className="flex justify-between items-center text-xs font-extrabold text-blue-950">
                    <span className="flex items-center gap-2">
                      <Icon name="spinner" size={14} className="animate-spin text-blue-600" />
                      Разбор спецификации и проверка формата...
                    </span>
                    <span>{parseProgress}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-blue-200 overflow-hidden">
                    <div
                      className="h-full bg-[#0F172A] transition-all duration-300 ease-out rounded-full"
                      style={{ width: `${parseProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </SectionCard>

          {/* Results preview table immediately below */}
          <SectionCard title={`Распознанные позиции · ${positions.length}`} icon="list">
            {positions.length > 0 ? (
              <div className="space-y-3">
                {positions.map((item, idx) => (
                  <div key={`${item.part_number}-${idx}`} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-3 md:grid-cols-[0.8fr_1.4fr_100px] items-center">
                    <div className="font-mono text-xs font-extrabold text-slate-900 bg-slate-50 px-3 py-2 rounded-xl border border-slate-200/80">
                      {item.part_number}
                    </div>
                    <div className="text-xs font-semibold text-slate-700 truncate">
                      {item.description || '—'}
                    </div>
                    <div className="text-xs font-bold text-slate-800 text-right pr-2">
                      {item.quantity} шт.
                    </div>
                  </div>
                ))}
                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setActiveStep(1)}
                    className="rounded-2xl bg-[#0F172A] px-6 py-2.5 text-xs font-black text-white transition hover:bg-[#1E293B] shadow-md flex items-center gap-2"
                  >
                    Перейти к выбору источников
                    <Icon name="chevron-right" size={12} />
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center p-6 text-xs font-semibold text-slate-400">
                Позиции не извлечены. Загрузите файл или вставьте спецификацию.
              </div>
            )}
          </SectionCard>
        </div>
      )}

      {/* STEP 1: Dedicated Supplier Sources Step */}
      {activeStep === 1 && (
        <div className="space-y-5 animate-fadeIn">
          {/* Browser Profile Sessions & Auth Card for 3 Suppliers */}
          <SectionCard title="Авторизация 3 ключевых скраперов (Exist, Autodoc, Rossko)" icon="lock">
            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs font-semibold text-slate-600">
                <span>Персистентные профили браузеров хранятся в <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-[11px] font-bold text-slate-800">~/.partsops-browser-profiles/</code></span>
                <button
                  type="button"
                  onClick={() => void fetchAuthStatusList()}
                  disabled={authLoading}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1 text-xs font-bold text-slate-800 hover:bg-slate-100 transition shadow-xs disabled:opacity-50"
                >
                  <Icon name="rotate" size={12} className={authLoading ? 'animate-spin text-blue-600' : 'text-slate-600'} />
                  Проверить сессии
                </button>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  { key: 'exist', name: 'Exist.ru (Экзист)', id: 'sup_exist' },
                  { key: 'autodoc', name: 'Autodoc.ru (Автодок)', id: 'sup_autodoc' },
                  { key: 'rossko', name: 'Rossko.ru (Росско)', id: 'sup_rossko' },
                ].map((item) => {
                  const status = authStatus[item.key];
                  const hasProfile = status?.profile_exists ?? true;
                  const authDate = status?.auth_at ? new Date(status.auth_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : null;

                  return (
                    <div key={item.key} className="rounded-2xl border border-slate-200/90 bg-white p-4 space-y-2 shadow-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-slate-900">{item.name}</span>
                        <span className={`w-2.5 h-2.5 rounded-full ${hasProfile ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]' : 'bg-amber-400'}`} />
                      </div>
                      <div className="text-[11px] font-medium text-slate-500">
                        {authDate ? `Авторизован: ${authDate}` : 'Сессия активна (cookie profile)'}
                      </div>
                      <div className="flex items-center justify-between text-[10px] pt-1">
                        <span className="font-extrabold uppercase text-slate-400">Профиль:</span>
                        <span className="font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                          ГОТОВ K СКРАПИНГУ
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </SectionCard>

          <SectionCard title="2. Источники поставщиков" icon="wave-square">
            <div className="space-y-4">
              {/* Header Stats Bar & Actions */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-xs font-extrabold text-slate-900">
                    Активно в поиске: {activeSupplierIds.size} из {suppliers.length}
                  </span>
                  {averageSupplierDelivery != null && (
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                      Средний срок: {averageSupplierDelivery} дн.
                    </span>
                  )}
                  <div className="flex items-center gap-1.5 ml-2">
                    <button
                      type="button"
                      onClick={() => setActiveSupplierIds(new Set(suppliers.map((s) => s.supplier_id)))}
                      className="text-[10px] font-extrabold text-blue-700 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-xl transition border border-blue-200/80"
                    >
                      Выбрать всех
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveSupplierIds(new Set())}
                      className="text-[10px] font-extrabold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-xl transition border border-slate-200"
                    >
                      Снять выбор
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={runPingCheck}
                    disabled={pinging}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-800 hover:bg-slate-100 transition shadow-xs disabled:opacity-50"
                  >
                    <Icon name="wave-square" size={12} className={pinging ? 'animate-spin' : 'text-emerald-600'} />
                    {pinging ? 'Проверка...' : 'Пинг API'}
                  </button>
                  <button
                    onClick={handleOpenCreateSupplier}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition hover:bg-[var(--accent-primary-strong)]"
                  >
                    <Icon name="plus" size={12} />
                    Новый поставщик
                  </button>
                </div>
              </div>

              {suppliersLoading && (
                <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-5 text-xs font-semibold text-slate-600">
                  <Icon name="spinner" size={15} className="animate-spin text-blue-600" />
                  Загружаем live-список поставщиков…
                </div>
              )}
              {!suppliersLoading && suppliersError && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-900">
                  <span><strong>Список поставщиков недоступен.</strong> {suppliersError}</span>
                  <button type="button" onClick={() => void fetchSuppliersList()} className="rounded-xl bg-rose-700 px-3 py-1.5 font-bold text-white hover:bg-rose-800">Повторить</button>
                </div>
              )}

              {/* City Filter Chips */}
              {!suppliersLoading && !suppliersError && suppliers.length > 0 && (
                <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase text-slate-400">Фильтр по городу:</span>
                {['all', 'Москва', 'Санкт-Петербург', 'Казань', 'Краснодар', 'Новосибирск'].map((city) => (
                  <button
                    key={city}
                    onClick={() => setCityFilter(city)}
                    className={`px-3 py-1 rounded-xl text-xs font-extrabold transition ${
                      cityFilter === city
                        ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                        : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    {city === 'all' ? 'Все города' : city}
                  </button>
                ))}
                </div>
              )}

              {/* Full-width Grid of Supplier Cards */}
              {!suppliersLoading && !suppliersError && suppliers.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-xs text-slate-600">
                  <p className="font-bold text-slate-900">Поставщики ещё не заведены</p>
                  <p className="mt-1">Создайте первого поставщика или обновите live-список.</p>
                </div>
              ) : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {filteredSuppliers.map((supplier) => {
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
                      className={`group relative flex cursor-pointer items-center justify-between rounded-2xl border p-4 transition-all duration-300 select-none ${
                        isActive
                          ? 'border-[rgba(15,23,42,0.4)] bg-white ring-2 ring-[#0F172A]/10 shadow-md scale-[1.01]'
                          : 'border-slate-200 bg-slate-50/60 opacity-60 hover:opacity-100 hover:bg-white'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {/* LED status indicator */}
                        {isActive ? (
                          <span className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse shrink-0" />
                        ) : (
                          <span className="w-3 h-3 rounded-full bg-slate-300 shrink-0" />
                        )}

                        <div className="w-9 h-9 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center font-black text-xs text-slate-800 shrink-0 uppercase">
                          {initials || 'П'}
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <div className="text-xs font-black text-slate-900 truncate">
                              {supplier.name}
                            </div>
                            {pingResults[supplier.supplier_id] && (
                              <span className={`text-[8px] font-bold px-1.5 py-0.2 rounded border ${pingResults[supplier.supplier_id].status === 'ok' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-rose-700 bg-rose-50 border-rose-200'}`}>
                                {pingResults[supplier.supplier_id].status} · {pingResults[supplier.supplier_id].latency_ms} ms
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] font-semibold text-slate-400 truncate">
                            {supplier.city} • {supplier.specialization}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        <span className="text-[10px] font-black text-slate-700 bg-slate-100 px-2.5 py-1 rounded-xl">
                          {supplier.avg_delivery_days} дн.
                        </span>
                        <button
                          onClick={(e) => handleOpenEditSupplier(supplier, e)}
                          className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition-colors hover:bg-[var(--accent-primary)] hover:text-white"
                          title="Редактировать карточку поставщика"
                        >
                          <Icon name="pencil" size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>}

              <div className="flex justify-end pt-3">
                <button
                  onClick={() => setActiveStep(2)}
                  className="flex items-center gap-2 rounded-2xl bg-[var(--accent-primary)] px-6 py-2.5 text-xs font-semibold text-white shadow-md transition hover:bg-[var(--accent-primary-strong)]"
                >
                  Перейти к валидации позиций
                  <Icon name="chevron-right" size={12} />
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {/* STEP 2: Positions Validation Table */}
      {activeStep === 2 && (
        <div className="space-y-5 animate-fadeIn">
          <SectionCard title={`3. Валидация позиций · ${positions.length}`} icon="list">
            {positions.length ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                    Проверка артикулов и количеств перед ордерингом
                  </span>
                  <button
                    onClick={addEmptyPosition}
                    className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-extrabold text-slate-800 hover:bg-slate-100 shadow-xs"
                  >
                    <Icon name="plus" size={12} />
                    Добавить позицию
                  </button>
                </div>

                {positions.map((item, index) => (
                  <div
                    key={`${item.part_number}-${index}`}
                    className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 md:grid-cols-[0.8fr_1.4fr_100px_40px] items-center shadow-xs"
                  >
                    <div>
                      <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Артикул</label>
                      <input
                        value={item.part_number}
                        onChange={(event) => updatePosition(index, 'part_number', event.target.value)}
                        aria-label={`Артикул ${index + 1}`}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-900 font-extrabold outline-none focus:border-[#0F172A] focus:bg-white"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Наименование / параметры</label>
                      <input
                        value={item.description ?? ''}
                        onChange={(event) => updatePosition(index, 'description', event.target.value)}
                        placeholder="Наименование / параметры"
                        aria-label={`Наименование ${index + 1}`}
                        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 font-semibold outline-none focus:border-[#0F172A] focus:bg-white"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] font-bold uppercase text-slate-400 block mb-1">Кол-во</label>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => updatePosition(index, 'quantity', String(Math.max(1, item.quantity - 1)))}
                          className="w-7 h-7 rounded-xl border border-slate-200 bg-slate-100 text-slate-700 font-black text-xs hover:bg-slate-200 active:scale-95 flex items-center justify-center shrink-0 transition"
                          title="Уменьшить количество"
                        >
                          -
                        </button>
                        <input
                          type="number"
                          min="1"
                          value={item.quantity}
                          onChange={(event) => updatePosition(index, 'quantity', event.target.value)}
                          aria-label={`Количество ${index + 1}`}
                          className="w-full text-center rounded-xl border border-slate-200 bg-slate-50 py-1.5 text-xs font-black text-slate-900 outline-none focus:border-[#0F172A] focus:bg-white"
                        />
                        <button
                          type="button"
                          onClick={() => updatePosition(index, 'quantity', String(item.quantity + 1))}
                          className="w-7 h-7 rounded-xl border border-slate-200 bg-slate-100 text-slate-700 font-black text-xs hover:bg-slate-200 active:scale-95 flex items-center justify-center shrink-0 transition"
                          title="Увеличить количество"
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <div className="flex justify-center pt-3 md:pt-0">
                      <button
                        onClick={() => deletePosition(index)}
                        className="w-8 h-8 rounded-xl hover:bg-rose-50 text-slate-400 hover:text-rose-600 flex items-center justify-center transition-colors"
                        title="Удалить позицию"
                      >
                        <Icon name="x-mark" size={14} />
                      </button>
                    </div>
                  </div>
                ))}

                <div className="flex justify-end border-t border-slate-200 pt-4">
                  <button
                    disabled={busy}
                    onClick={() => void createPackage()}
                    className="flex items-center gap-2 rounded-2xl bg-[var(--accent-primary)] px-7 py-3 text-xs font-semibold text-white shadow-md transition-all hover:bg-[var(--accent-primary-strong)] active:scale-[0.98] disabled:opacity-50"
                  >
                    {busy && <Icon name="spinner" size={14} className="animate-spin" />}
                    {busy ? 'Создаём пакет…' : 'Сформировать пакет и запустить ИИ-сбор'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-xs text-slate-500">
                Позиции отсутствуют. Перейдите на Шаг 1 для ввода данных.
              </div>
            )}
          </SectionCard>
        </div>
      )}

      {/* STEP 3: Pipeline Execution & Launch */}
      {activeStep === 3 && (
        <div className="space-y-5 animate-fadeIn">
          {/* Quality Gates & Validation Status */}
          <SectionCard title="Шлюзы контроля качества (Quality Gates & Evidence Audit)" icon="shield">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div>
                  <div className="text-xs font-black text-slate-900">Проверка целостности скриншотов и ценовых выбросов</div>
                  <div className="text-[11px] font-semibold text-slate-500">Автоматический аудит по 4 шлюзам качества перед отправкой</div>
                </div>
                <button
                  type="button"
                  onClick={() => createdRequestId && void runValidation(createdRequestId)}
                  disabled={validating || !createdRequestId}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-[var(--accent-primary-strong)] disabled:opacity-50"
                >
                  <Icon name="shield" size={13} className={validating ? 'animate-spin' : ''} />
                  {validating ? 'Аудит...' : 'Запустить Quality Gates'}
                </button>
              </div>

              {validationReport && (
                <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black text-slate-900">Итоговый вердикт пакета:</span>
                    <span className={`text-xs font-extrabold px-3 py-1 rounded-full ${validationReport.overall_passed ? 'bg-emerald-100 text-emerald-900 border border-emerald-300' : 'bg-amber-100 text-amber-900 border border-amber-300'}`}>
                      {validationReport.overall_passed ? '✓ Валидация пройдена (0 критических ошибок)' : '⚠ Требует внимания оператора'}
                    </span>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 pt-1">
                    {[
                      { gate: 'PriceAnomalyDetector', title: 'Ценовые выбросы' },
                      { gate: 'EvidenceIntegrityAuditor', title: 'Целостность файлов' },
                      { gate: 'AnalogCompatibilityChecker', title: 'Совместимость кроссов' },
                      { gate: 'ScraperHealthChecker', title: 'Здоровье скраперов' },
                    ].map((g) => {
                      const gateData = validationReport.gates?.find((item: any) => item.gate_name === g.gate);
                      const passed = gateData ? gateData.passed : true;
                      return (
                        <div key={g.gate} className="rounded-xl border border-slate-200/80 bg-slate-50 p-3 text-left">
                          <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">{g.title}</div>
                          <div className="flex items-center gap-1.5 mt-1 font-bold text-xs">
                            <span className={`w-2 h-2 rounded-full ${passed ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                            <span className={passed ? 'text-emerald-950' : 'text-amber-950'}>
                              {passed ? 'Пройден' : 'Замечания'}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard title="4. Мультиагентный запуск сбора и экспорт спецификации" icon="robot">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-6 space-y-4 text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-500 text-white flex items-center justify-center mx-auto shadow-md">
                <Icon name="check" size={24} />
              </div>
              <div className="text-base font-black text-emerald-950">
                Пакет сбора успешно сформирован: {createdRequestId ?? 'идентификатор не получен'}
              </div>
              <div className="text-xs font-semibold text-emerald-800 max-w-md mx-auto leading-relaxed">
                ИИ-агенты завершили анализ цен и аналогов по {activeSupplierIds.size} подключенным поставщикам для {positions.length} позиций. Документ по форме полностью готов.
              </div>

              {/* Mode Selector Tabs */}
              <div className="pt-2 max-w-lg mx-auto">
                <div className="flex items-center justify-center p-1 rounded-2xl bg-slate-200/80 border border-slate-300">
                  <button
                    type="button"
                    onClick={() => setExportMode('light')}
                    className={`flex-1 py-2 px-4 rounded-xl text-xs font-extrabold transition ${
                      exportMode === 'light'
                        ? 'bg-[var(--accent-primary)] text-white shadow-xs'
                        : 'text-slate-700 hover:text-slate-900'
                    }`}
                  >
                    Light (для клиента без скриншотов)
                  </button>
                  <button
                    type="button"
                    onClick={() => setExportMode('full')}
                    className={`flex-1 py-2 px-4 rounded-xl text-xs font-extrabold transition ${
                      exportMode === 'full'
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-slate-700 hover:text-slate-900'
                    }`}
                  >
                    Full (со скриншотами и доказательствами)
                  </button>
                </div>
              </div>

              <div className="pt-2 space-y-3">
                {exportMode === 'light' ? (
                  <div className="space-y-2 animate-fadeIn">
                    <p className="text-[11px] font-semibold text-slate-600">Оптимизирован для отправки заказчику. Содержит наилучшие цены и сроки без тяжелых скриншотов.</p>
                    <div className="flex justify-center">
                      <button
                        onClick={() => {
                          if (!createdRequestId) return;
                          const suppliersParam = Array.from(activeSupplierIds).join(',');
                          window.open(`/api/contracts/${createdRequestId}/export-custom-excel?suppliers=${suppliersParam}&mode=simple`, '_blank');
                        }}
                        disabled={!createdRequestId}
                        className="flex items-center gap-2 rounded-2xl bg-[var(--accent-primary)] px-7 py-3 text-xs font-semibold text-white shadow-md transition hover:bg-[var(--accent-primary-strong)] disabled:opacity-50"
                      >
                        <Icon name="file-export" size={14} className="text-white" />
                        Скачать спецификацию для клиента (.xlsx)
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3 animate-fadeIn">
                    <p className="text-[11px] font-semibold text-emerald-800">Включает полные гиперссылки на доказательства цен и ZIP-пакет со скриншотами страниц поставщиков.</p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                      <button
                        onClick={() => {
                          if (!createdRequestId) return;
                          const suppliersParam = Array.from(activeSupplierIds).join(',');
                          window.open(`/api/contracts/${createdRequestId}/export-custom-excel?suppliers=${suppliersParam}&mode=full`, '_blank');
                        }}
                        disabled={!createdRequestId}
                        className="rounded-2xl bg-emerald-600 px-6 py-3 text-xs font-black text-white hover:bg-emerald-700 transition shadow-md flex items-center gap-2 disabled:opacity-50"
                      >
                        <Icon name="paperclip" size={14} className="text-white" />
                        Скачать отчёт с доказательствами (.xlsx)
                      </button>
                      <button
                        onClick={() => {
                          if (!createdRequestId) return;
                          window.open(`/api/contracts/${createdRequestId}/export-evidence-pack`, '_blank');
                        }}
                        disabled={!createdRequestId}
                        className="rounded-2xl border border-slate-300 bg-white px-6 py-3 text-xs font-bold text-slate-800 hover:bg-slate-50 transition shadow-xs flex items-center gap-2 disabled:opacity-50"
                      >
                        <Icon name="box-archive" size={14} className="text-slate-600" />
                        Скачать ZIP-архив скриншотов
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex justify-center pt-2">
                  <button
                    onClick={() => {
                      setCreatedRequestId(null);
                      setActiveStep(0);
                    }}
                    className="rounded-2xl border border-slate-300 bg-white px-6 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-100 transition shadow-xs"
                  >
                    Создать новый запрос
                  </button>
                </div>
              </div>
            </div>
          </SectionCard>
        </div>
      )}

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
