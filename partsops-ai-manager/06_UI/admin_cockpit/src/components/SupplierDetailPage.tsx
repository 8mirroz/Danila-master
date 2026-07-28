import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiJson } from '../lib/api';
import { Icon } from './Primitives';
import { gsap } from 'gsap';
import type {
  SupplierAnalyticsRecord,
  SupplierLogRecord,
  SupplierRecord,
  SupplierTableRecord,
  SupplierTableRowRecord,
} from './supplierTypes';

type TabType = 'overview' | 'profile' | 'tables' | 'analytics' | 'logs' | 'settings';
type RowDraft = {
  part_name: string;
  oem_number: string;
  brand: string;
  price: string;
  currency: string;
  stock_qty: string;
  delivery_days: string;
  category: string;
};

type BulkDraft = {
  category: string;
  delivery_days: string;
  stock_qty: string;
};

type SettingsDraft = {
  status: string;
  currency_default: string;
  payment_terms: string;
  delivery_terms: string;
  account_owner: string;
  last_sync_status: string;
  notes_internal: string;
};

interface SupplierDetailPageProps {
  supplierId: string;
  initialTab?: TabType;
  onBack: () => void;
  onRefresh: () => void;
  onEditSupplier: (supplier: SupplierRecord) => void;
}

export function SupplierDetailPage({
  supplierId,
  initialTab = 'overview',
  onBack,
  onRefresh,
  onEditSupplier,
}: SupplierDetailPageProps) {
  const [supplier, setSupplier] = useState<SupplierRecord | null>(null);
  const [tables, setTables] = useState<SupplierTableRecord[]>([]);
  const [analytics, setAnalytics] = useState<SupplierAnalyticsRecord | null>(null);
  const [logs, setLogs] = useState<SupplierLogRecord[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [tableRows, setTableRows] = useState<SupplierTableRowRecord[]>([]);
  const [selectedRow, setSelectedRow] = useState<SupplierTableRowRecord | null>(null);
  const [rowQuery, setRowQuery] = useState('');
  const [loadingRows, setLoadingRows] = useState(false);
  const [savingRow, setSavingRow] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [creatingTable, setCreatingTable] = useState(false);
  const [savingTableMeta, setSavingTableMeta] = useState(false);
  const [replacingTable, setReplacingTable] = useState(false);
  const [newTableName, setNewTableName] = useState('');
  const [newTableFile, setNewTableFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [tableEditorName, setTableEditorName] = useState('');
  const [tableEditorStatus, setTableEditorStatus] = useState('active');
  const [replacementVersionName, setReplacementVersionName] = useState('');
  const [replacementFile, setReplacementFile] = useState<File | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [rowDraft, setRowDraft] = useState<RowDraft | null>(null);
  const [bulkDraft, setBulkDraft] = useState<BulkDraft>({ category: '', delivery_days: '', stock_qty: '' });
  const [settingsDraft, setSettingsDraft] = useState<SettingsDraft | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [ratingDraft, setRatingDraft] = useState('4.5');
  const [ratingReason, setRatingReason] = useState('');
  const [savingRating, setSavingRating] = useState(false);
  const [logFilter, setLogFilter] = useState('all');
  const [logQuery, setLogQuery] = useState('');

  const fetchSupplierWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);
    setImportMessage(null);
    try {
      const [supplierData, tableData, analyticsData, logData] = await Promise.all([
        apiJson<SupplierRecord>(`/api/suppliers/${supplierId}`),
        apiJson<SupplierTableRecord[]>(`/api/suppliers/${supplierId}/tables`),
        apiJson<SupplierAnalyticsRecord>(`/api/suppliers/${supplierId}/analytics`),
        apiJson<{ total: number; logs: SupplierLogRecord[] }>(`/api/suppliers/${supplierId}/logs`),
      ]);
      setSupplier(supplierData);
      setTables(tableData);
      setAnalytics(analyticsData);
      setLogs(logData.logs);
      setSelectedTableId((current) => current ?? tableData[0]?.table_id ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось загрузить рабочее пространство поставщика');
    } finally {
      setLoading(false);
    }
  }, [supplierId]);

  const fetchRows = useCallback(async (tableId: string, search = '') => {
    setLoadingRows(true);
    try {
      const params = new URLSearchParams({ page: '1', page_size: '25' });
      if (search.trim()) {
        params.set('q', search.trim());
      }
      const data = await apiJson<{ rows: SupplierTableRowRecord[] }>(
        `/api/suppliers/${supplierId}/tables/${tableId}/rows?${params.toString()}`,
      );
      setTableRows(data.rows);
      setSelectedRow((current) => current && data.rows.some((row) => row.row_key === current.row_key) ? current : data.rows[0] ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось загрузить строки таблицы');
    } finally {
      setLoadingRows(false);
    }
  }, [supplierId]);

  useEffect(() => {
    void fetchSupplierWorkspace();
  }, [fetchSupplierWorkspace]);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (selectedTableId) {
      void fetchRows(selectedTableId, rowQuery);
    } else {
      setTableRows([]);
      setSelectedRow(null);
      setSelectedRowKeys([]);
    }
  }, [fetchRows, rowQuery, selectedTableId]);

  const selectedTable = useMemo(
    () => tables.find((table) => table.table_id === selectedTableId) ?? null,
    [selectedTableId, tables],
  );

  const selectedTableSummary = useMemo(() => {
    const summary = selectedTable?.validation_summary_json ?? {};
    const warnings = Array.isArray(summary.warnings)
      ? summary.warnings.map((warning) => String(warning))
      : [];
    return {
      importedRows: Number(summary.imported_rows ?? selectedTable?.row_count ?? 0),
      totalRows: Number(summary.total_rows ?? selectedTable?.row_count ?? 0),
      skippedRows: Number(summary.skipped_rows ?? 0),
      warnings,
      artifactId: typeof summary.artifact_id === 'string' ? summary.artifact_id : null,
      replacedTableId: typeof summary.replaced_table_id === 'string' ? summary.replaced_table_id : null,
    };
  }, [selectedTable]);

  useEffect(() => {
    if (!selectedTable) {
      setTableEditorName('');
      setTableEditorStatus('active');
      setReplacementVersionName('');
      return;
    }
    setTableEditorName(selectedTable.name);
    setTableEditorStatus(selectedTable.status);
    setReplacementVersionName(`${selectedTable.name} v${selectedTable.version + 1}`);
  }, [selectedTable]);

  useEffect(() => {
    if (!selectedRow) {
      setRowDraft(null);
      return;
    }
    setRowDraft({
      part_name: selectedRow.part_name,
      oem_number: selectedRow.oem_number,
      brand: selectedRow.brand,
      price: String(selectedRow.price),
      currency: selectedRow.currency,
      stock_qty: String(selectedRow.stock_qty),
      delivery_days: String(selectedRow.delivery_days),
      category: selectedRow.category,
    });
  }, [selectedRow]);

  useEffect(() => {
    setSelectedRowKeys((current) => current.filter((rowKey) => tableRows.some((row) => row.row_key === rowKey)));
  }, [tableRows]);

  useEffect(() => {
    if (!supplier) {
      setSettingsDraft(null);
      setRatingDraft('4.5');
      setRatingReason('');
      return;
    }
    setSettingsDraft({
      status: supplier.status,
      currency_default: supplier.currency_default,
      payment_terms: supplier.payment_terms,
      delivery_terms: supplier.delivery_terms,
      account_owner: supplier.account_owner,
      last_sync_status: supplier.last_sync_status,
      notes_internal: supplier.notes_internal,
    });
    setRatingDraft(String(supplier.rating_manual ?? Number((supplier.reliability_score * 5).toFixed(1))));
    setRatingReason('');
  }, [supplier]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setNewTableFile(e.dataTransfer.files[0]);
    }
  };

  const handleCreateTable = async () => {
    if (!newTableName.trim()) {
      return;
    }
    setCreatingTable(true);
    setError(null);
    try {
      await apiJson(`/api/suppliers/${supplierId}/tables`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newTableName.trim(),
          filename: `${newTableName.trim().toLowerCase().replace(/\s+/g, '-')}.xlsx`,
          source_type: 'excel',
          uploaded_by: 'admin',
          validation_summary_json: { valid_rows: 0, warnings: ['new_table'] },
          rows: [],
        }),
      });
      setNewTableName('');
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось создать таблицу');
    } finally {
      setCreatingTable(false);
    }
  };

  const handleImportTable = async () => {
    if (!newTableFile) {
      setError('Выберите CSV, XLSX, TXT или JSON файл для импорта.');
      return;
    }
    setCreatingTable(true);
    setError(null);
    setImportMessage(null);
    try {
      const form = new FormData();
      form.append('file', newTableFile);
      if (newTableName.trim()) {
        form.append('name', newTableName.trim());
      }
      const result = await apiJson<{ import_summary: { imported_rows: number }; table: SupplierTableRecord }>(
        `/api/suppliers/${supplierId}/tables/import`,
        {
          method: 'POST',
          body: form,
        },
      );
      setImportMessage(`Импорт завершен: ${result.import_summary.imported_rows} строк(и) в таблицу ${result.table.name}.`);
      setNewTableName('');
      setNewTableFile(null);
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось импортировать таблицу');
    } finally {
      setCreatingTable(false);
    }
  };

  const handleActivateTable = async (tableId: string) => {
    try {
      await apiJson(`/api/suppliers/${supplierId}/tables/${tableId}/activate`, { method: 'POST' });
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось активировать таблицу');
    }
  };

  const handleUpdateTableMeta = async () => {
    if (!selectedTable) {
      return;
    }
    setSavingTableMeta(true);
    setError(null);
    try {
      await apiJson(`/api/suppliers/${supplierId}/tables/${selectedTable.table_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: tableEditorName.trim() || selectedTable.name,
          status: tableEditorStatus,
        }),
      });
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось обновить таблицу');
    } finally {
      setSavingTableMeta(false);
    }
  };

  const handleReplaceTable = async () => {
    if (!selectedTable) {
      return;
    }
    setReplacingTable(true);
    setError(null);
    try {
      await apiJson(`/api/suppliers/${supplierId}/tables/${selectedTable.table_id}/replace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: replacementVersionName.trim() || `${selectedTable.name} copy`,
          filename: `${(replacementVersionName.trim() || selectedTable.name).toLowerCase().replace(/\s+/g, '-')}.xlsx`,
          source_type: selectedTable.source_type,
          status: 'active',
          uploaded_by: 'admin',
          mapped_columns_json: selectedTable.mapped_columns_json,
          validation_summary_json: {
            replaced_from: selectedTable.table_id,
            copied_rows: tableRows.length,
          },
          rows: tableRows.map((row) => ({
            row_key: row.row_key,
            part_name: row.part_name,
            oem_number: row.oem_number,
            brand: row.brand,
            price: row.price,
            currency: row.currency,
            stock_qty: row.stock_qty,
            delivery_days: row.delivery_days,
            category: row.category,
            ...row.raw_payload_json,
          })),
        }),
      });
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось создать новую версию таблицы');
    } finally {
      setReplacingTable(false);
    }
  };

  const handleReplaceTableFromFile = async () => {
    if (!selectedTable) {
      return;
    }
    if (!replacementFile) {
      setError('Выберите файл новой версии таблицы.');
      return;
    }
    setReplacingTable(true);
    setError(null);
    setImportMessage(null);
    try {
      const form = new FormData();
      form.append('file', replacementFile);
      form.append('replace_table_id', selectedTable.table_id);
      form.append('name', replacementVersionName.trim() || `${selectedTable.name} v${selectedTable.version + 1}`);
      const result = await apiJson<{ import_summary: { imported_rows: number }; table: SupplierTableRecord }>(
        `/api/suppliers/${supplierId}/tables/import`,
        {
          method: 'POST',
          body: form,
        },
      );
      setImportMessage(`Новая версия загружена: ${result.table.name}, ${result.import_summary.imported_rows} строк(и).`);
      setReplacementFile(null);
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось заменить таблицу новой версией');
    } finally {
      setReplacingTable(false);
    }
  };

  const handleArchiveSupplier = async () => {
    try {
      await apiJson(`/api/suppliers/${supplierId}/archive`, { method: 'POST' });
      onRefresh();
      onBack();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось архивировать поставщика');
    }
  };

  const handleSaveSettings = async () => {
    if (!supplier || !settingsDraft) {
      return;
    }
    setSavingSettings(true);
    setError(null);
    setImportMessage(null);
    try {
      await apiJson(`/api/suppliers/${supplierId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supplier_id: supplier.supplier_id,
          name: supplier.name,
          contact_person: supplier.contact_person,
          phone: supplier.phone,
          email: supplier.email,
          city: supplier.city,
          specialization: supplier.specialization,
          reliability_score: supplier.reliability_score,
          avg_delivery_days: supplier.avg_delivery_days,
          status: settingsDraft.status,
          rating_manual: supplier.rating_manual,
          account_owner: settingsDraft.account_owner,
          payment_terms: settingsDraft.payment_terms,
          delivery_terms: settingsDraft.delivery_terms,
          currency_default: settingsDraft.currency_default,
          notes_internal: settingsDraft.notes_internal,
          last_sync_status: settingsDraft.last_sync_status,
        }),
      });
      setImportMessage('Операционные настройки поставщика обновлены.');
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось обновить настройки поставщика');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveRating = async () => {
    if (!supplier) {
      return;
    }
    const parsedRating = Number(ratingDraft);
    if (!Number.isFinite(parsedRating) || parsedRating <= 0) {
      setError('Укажите корректный manual rating.');
      return;
    }
    setSavingRating(true);
    setError(null);
    setImportMessage(null);
    try {
      await apiJson(`/api/suppliers/${supplierId}/rating`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rating_manual: parsedRating,
          reason: ratingReason.trim() || 'manual operator update',
        }),
      });
      setImportMessage(`Manual rating обновлен до ${parsedRating.toFixed(1)}.`);
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось обновить manual rating');
    } finally {
      setSavingRating(false);
    }
  };

  const handleSaveRow = async () => {
    if (!selectedTable || !selectedRow || !rowDraft) {
      return;
    }
    setSavingRow(true);
    setError(null);
    setImportMessage(null);
    try {
      const updated = await apiJson<SupplierTableRowRecord>(
        `/api/suppliers/${supplierId}/tables/${selectedTable.table_id}/rows/${selectedRow.row_key}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_name: rowDraft.part_name.trim(),
            oem_number: rowDraft.oem_number.trim(),
            brand: rowDraft.brand.trim(),
            price: Number(rowDraft.price) || 0,
            currency: rowDraft.currency.trim() || 'RUB',
            stock_qty: Number(rowDraft.stock_qty) || 0,
            delivery_days: Number(rowDraft.delivery_days) || 0,
            category: rowDraft.category.trim(),
          }),
        },
      );
      setTableRows((current) => current.map((row) => (row.row_key === updated.row_key ? updated : row)));
      setSelectedRow(updated);
      setImportMessage(`Позиция ${updated.part_name} обновлена.`);
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось обновить строку');
    } finally {
      setSavingRow(false);
    }
  };

  const toggleRowSelection = (rowKey: string, checked: boolean) => {
    setSelectedRowKeys((current) => {
      if (checked) {
        return current.includes(rowKey) ? current : [...current, rowKey];
      }
      return current.filter((value) => value !== rowKey);
    });
  };

  const handleToggleAllRows = (checked: boolean) => {
    setSelectedRowKeys(checked ? tableRows.map((row) => row.row_key) : []);
  };

  const handleBulkUpdate = async () => {
    if (!selectedTable || selectedRowKeys.length === 0) {
      setError('Выберите строки для массового обновления.');
      return;
    }
    const payload: Record<string, unknown> = { row_keys: selectedRowKeys };
    if (bulkDraft.category.trim()) {
      payload.category = bulkDraft.category.trim();
    }
    if (bulkDraft.delivery_days.trim()) {
      payload.delivery_days = Number(bulkDraft.delivery_days) || 0;
    }
    if (bulkDraft.stock_qty.trim()) {
      payload.stock_qty = Number(bulkDraft.stock_qty) || 0;
    }
    if (Object.keys(payload).length === 1) {
      setError('Заполните хотя бы одно поле для массового обновления.');
      return;
    }

    setBulkSaving(true);
    setError(null);
    setImportMessage(null);
    try {
      const result = await apiJson<{ rows: SupplierTableRowRecord[]; updated_count: number }>(
        `/api/suppliers/${supplierId}/tables/${selectedTable.table_id}/rows/bulk-update`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      );
      const updatedMap = new Map(result.rows.map((row) => [row.row_key, row]));
      setTableRows((current) => current.map((row) => updatedMap.get(row.row_key) ?? row));
      setSelectedRow((current) => (current ? updatedMap.get(current.row_key) ?? current : current));
      setImportMessage(`Массово обновлено ${result.updated_count} строк(и).`);
      setBulkDraft({ category: '', delivery_days: '', stock_qty: '' });
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось выполнить массовое обновление');
    } finally {
      setBulkSaving(false);
    }
  };

  const selectedRowWarnings = useMemo(
    () => (selectedRow ? getRowWarnings(selectedRow) : []),
    [selectedRow],
  );

  const analyticsHighlights = useMemo(() => {
    if (!supplier || !analytics) {
      return [];
    }
    const highlights: Array<{ tone: 'emerald' | 'amber' | 'rose'; text: string }> = [];
    if (supplier.last_sync_status === 'stale') {
      highlights.push({ tone: 'amber', text: 'Активный feed устарел. Нужна загрузка новой версии таблицы.' });
    }
    if (supplier.reliability_score < 0.8) {
      highlights.push({ tone: 'rose', text: 'Низкая надежность поставщика. Проверьте recent incidents и manual override.' });
    }
    if (analytics.summary.avg_price_deviation > 0.1) {
      highlights.push({ tone: 'amber', text: 'Средняя цена отклоняется от исторической медианы более чем на 10%.' });
    }
    if (analytics.summary.active_table_count === 0) {
      highlights.push({ tone: 'rose', text: 'Нет активной таблицы. Matching может идти по устаревшим данным.' });
    }
    if (highlights.length === 0) {
      highlights.push({ tone: 'emerald', text: 'Критичных аналитических сигналов сейчас нет.' });
    }
    return highlights;
  }, [analytics, supplier]);

  const filteredLogs = useMemo(() => {
    const normalizedQuery = logQuery.trim().toLowerCase();
    return logs.filter((log) => {
      const matchesType = logFilter === 'all' || log.event_type === logFilter;
      if (!matchesType) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [
        log.event_type,
        log.actor_id,
        log.table_id ?? '',
        JSON.stringify(log.payload),
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [logFilter, logQuery, logs]);

  const logTypeOptions = useMemo(() => {
    return Array.from(new Set(logs.map((log) => log.event_type))).sort((left, right) => left.localeCompare(right));
  }, [logs]);

  useEffect(() => {
    if (!loading && supplier) {
      gsap.fromTo('.premium-header-content', 
        { opacity: 0, y: 15 }, 
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out', stagger: 0.1 }
      );
    }
  }, [loading, supplierId, supplier]);

  useEffect(() => {
    if (!loading && supplier) {
      gsap.fromTo('.premium-tab-content',
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.4, ease: 'power1.out' }
      );
    }
  }, [loading, activeTab, supplier]);

  if (loading) {
    return <div className="h-full animate-pulse rounded-3xl border border-slate-200 bg-white/70" />;
  }

  if (!supplier) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-rose-200 bg-rose-50 text-rose-700">
        Не удалось загрузить поставщика.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[var(--bg-app)]">
      <div className="relative overflow-hidden bg-[linear-gradient(135deg,#0b1329_0%,#1a1f3c_100%)] p-6 text-white border-b border-white/5 shadow-xl">
        {/* Ambient Glows */}
        <div className="absolute top-[-40%] left-[-10%] w-[350px] h-[350px] rounded-full bg-blue-500/10 blur-[90px] pointer-events-none" />
        <div className="absolute bottom-[-40%] right-[-10%] w-[350px] h-[350px] rounded-full bg-indigo-500/10 blur-[90px] pointer-events-none" />

        <div className="relative z-10 premium-header-content">
          <div className="mb-5 flex items-center justify-between gap-4">
            <button
              onClick={onBack}
              className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-white/90 transition hover:bg-white/10 hover:text-white hover:scale-105 active:scale-95 duration-200"
            >
              <Icon name="arrow-left" size={12} />
              Назад к каталогу
            </button>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => onEditSupplier(supplier)}
                className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-white/90 transition hover:bg-white/10 hover:text-white hover:scale-105 active:scale-95 duration-200"
              >
                <Icon name="pencil" size={12} />
                Редактировать
              </button>
              <button
                onClick={handleArchiveSupplier}
                className="flex items-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2 text-xs font-bold text-rose-100 transition hover:bg-rose-500/20 hover:scale-105 active:scale-95 duration-200"
              >
                <Icon name="trash" size={12} />
                Архивировать
              </button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className={`rounded-full px-3 py-1 text-[9px] font-black uppercase tracking-[0.24em] border ${
                  supplier.status === 'active'
                    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                    : supplier.status === 'blocked'
                    ? 'bg-rose-500/10 text-rose-300 border-rose-500/20'
                    : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                }`}>
                  {supplier.status}
                </span>
                <span className="rounded-full bg-white/5 border border-white/10 px-3 py-1 text-[9px] font-black uppercase tracking-[0.24em] text-white/70">
                  {supplier.last_sync_status}
                </span>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center font-extrabold text-lg text-white shrink-0 shadow-lg select-none uppercase">
                  {supplier.name
                    .replace(/^(ООО|ИП|АО|ЗАО|ИП|ооо|ип|ао|зао)\s+["«]?/i, '')
                    .replace(/["»]/g, '')
                    .trim()
                    .slice(0, 2) || 'П'}
                </div>
                <div>
                  <h2 className="text-3xl font-black tracking-tight text-white leading-tight">{supplier.name}</h2>
                  <p className="mt-1.5 text-xs text-slate-400 font-medium">
                    {supplier.city} • {supplier.specialization || 'General sourcing'}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                {supplier.categories.map((category) => (
                  <span key={category} className="rounded-full bg-white/5 border border-white/5 px-3 py-1 text-[10px] font-semibold text-white/85">
                    {category}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <MetricBox label="Надежность" value={`${Math.round(supplier.reliability_score * 100)}%`} />
              <MetricBox label="Manual rating" value={supplier.rating_manual ? supplier.rating_manual.toFixed(1) : '—'} />
              <MetricBox label="Таблиц" value={`${supplier.active_table_count}/${supplier.table_count}`} />
              <MetricBox label="SLA" value={`${supplier.avg_delivery_days} дн.`} />
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="border-b border-rose-200 bg-rose-50 px-6 py-3 text-sm font-medium text-rose-700">
          {error}
        </div>
      )}

      {importMessage && (
        <div className="border-b border-emerald-200 bg-emerald-50 px-6 py-3 text-sm font-medium text-emerald-700">
          {importMessage}
        </div>
      )}

      <div className="border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex flex-wrap gap-2.5">
          <TabButton label="Overview" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} />
          <TabButton label="Profile" active={activeTab === 'profile'} onClick={() => setActiveTab('profile')} />
          <TabButton label="Tables" active={activeTab === 'tables'} onClick={() => setActiveTab('tables')} />
          <TabButton label="Analytics" active={activeTab === 'analytics'} onClick={() => setActiveTab('analytics')} />
          <TabButton label="Logs" active={activeTab === 'logs'} onClick={() => setActiveTab('logs')} />
          <TabButton label="Settings" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-6 premium-tab-content">
        {activeTab === 'overview' && (
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Panel title="Операционный профиль">
              <div className="grid gap-3.5 md:grid-cols-2">
                <DetailRow label="Контакт" value={supplier.contact_person || '—'} />
                <DetailRow label="Телефон" value={supplier.phone || '—'} isLink linkType="tel" />
                <DetailRow label="Email" value={supplier.email || '—'} isLink linkType="mailto" />
                <DetailRow label="Владелец" value={supplier.account_owner || '—'} />
                <DetailRow label="Payment terms" value={supplier.payment_terms || '—'} />
                <DetailRow label="Delivery terms" value={supplier.delivery_terms || '—'} />
                <DetailRow label="Последний фид" value={supplier.last_feed_at ? new Date(supplier.last_feed_at).toLocaleString() : '—'} />
                <DetailRow label="Последняя активность" value={supplier.last_activity_at ? new Date(supplier.last_activity_at).toLocaleString() : '—'} />
              </div>
            </Panel>

            <Panel title="Operational alerts">
              <div className="space-y-3">
                <AlertChip
                  tone={supplier.last_sync_status === 'stale' ? 'amber' : 'emerald'}
                  text={supplier.last_sync_status === 'stale' ? 'Есть stale feed, нужен refresh таблицы' : 'Фид синхронизирован'}
                />
                <AlertChip
                  tone={supplier.reliability_score < 0.8 ? 'rose' : 'emerald'}
                  text={supplier.reliability_score < 0.8 ? 'Надежность ниже порога 80%' : 'Надежность в рабочем диапазоне'}
                />
                <AlertChip
                  tone={supplier.active_table_count === 0 ? 'rose' : 'emerald'}
                  text={supplier.active_table_count === 0 ? 'Нет активной таблицы для live preview' : 'Активная таблица доступна для инспекции'}
                />
              </div>
            </Panel>
          </div>
        )}

        {activeTab === 'profile' && (
          <Panel title="Карточка поставщика">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <DetailRow label="Название" value={supplier.name} />
              <DetailRow label="Контакт" value={supplier.contact_person || '—'} />
              <DetailRow label="Телефон" value={supplier.phone || '—'} />
              <DetailRow label="Email" value={supplier.email || '—'} />
              <DetailRow label="Город" value={supplier.city || '—'} />
              <DetailRow label="Специализация" value={supplier.specialization || '—'} />
              <DetailRow label="Currency" value={supplier.currency_default} />
              <DetailRow label="Status" value={supplier.status} />
              <DetailRow label="Sync" value={supplier.last_sync_status} />
            </div>
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
              {supplier.notes_internal || 'Внутренние заметки не заполнены.'}
            </div>
          </Panel>
        )}

        {activeTab === 'tables' && (
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
            <Panel title="Таблицы поставщика">
              <div className="space-y-3">
                <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
                  <div>
                    <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                      Название таблицы
                    </label>
                    <input
                      value={newTableName}
                      onChange={(event) => setNewTableName(event.target.value)}
                      placeholder="Например: Q3 OEM price list"
                      className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:border-[var(--accent-primary)] focus:bg-white"
                    />
                  </div>

                  <div>
                    <span className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                      Файл импорта
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      id="input-file-upload"
                      className="hidden"
                      accept=".csv,.xlsx,.json,.txt,.tsv"
                      onChange={(e) => setNewTableFile(e.target.files?.[0] ?? null)}
                    />
                    
                    {!newTableFile ? (
                      <div
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`group border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all duration-300 relative flex flex-col items-center justify-center gap-2 select-none ${
                          dragActive
                            ? 'border-[var(--accent-primary)] bg-blue-50/60 scale-[1.02] shadow-[0_4px_20px_rgba(37,99,235,0.08)]'
                            : 'border-slate-200 bg-slate-50/50 hover:border-[var(--accent-primary)] hover:bg-slate-50 hover:scale-[1.01]'
                        }`}
                      >
                        <Icon 
                          name="cloud-arrow-up" 
                          size={24} 
                          className={`transition-colors duration-300 ${
                            dragActive ? 'text-[var(--accent-primary)]' : 'text-slate-400 group-hover:text-[var(--accent-primary)]'
                          }`}
                        />
                        <span className="text-[12px] font-bold text-slate-700">
                          Перетащите файл сюда
                        </span>
                        <span className="text-[10px] font-medium text-slate-400">
                          или кликните для выбора
                        </span>
                      </div>
                    ) : (
                      <div className="border border-slate-200 rounded-2xl p-4 bg-slate-50/50 flex items-center justify-between gap-3 shadow-inner">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="w-9 h-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center shrink-0">
                            <Icon name="folder-open" size={16} className="text-[var(--accent-primary)]" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-[12px] font-bold text-slate-800 truncate" title={newTableFile.name}>
                              {newTableFile.name}
                            </div>
                            <div className="text-[10px] font-semibold text-slate-400">
                              {(newTableFile.size / 1024).toFixed(1)} KB
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setNewTableFile(null);
                          }}
                          className="w-7 h-7 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 transition-colors shadow-sm"
                          title="Удалить файл"
                        >
                          <Icon name="times" size={12} />
                        </button>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => void (newTableFile ? handleImportTable() : handleCreateTable())}
                    disabled={creatingTable || (!newTableName.trim() && !newTableFile)}
                    className="w-full rounded-2xl bg-[var(--accent-primary)] px-4 py-3 text-xs font-bold text-white transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] hover:shadow-[0_4px_12px_rgba(37,99,235,0.25)] disabled:opacity-50 disabled:scale-100 disabled:shadow-none cursor-pointer flex items-center justify-center gap-2"
                  >
                    {creatingTable && <Icon name="spinner" size={12} className="animate-spin" />}
                    {creatingTable ? 'Создание...' : 'Создать таблицу'}
                  </button>
                </div>
                {tables.map((table) => (
                  <button
                    key={table.table_id}
                    onClick={() => setSelectedTableId(table.table_id)}
                    className={`w-full rounded-2xl border p-3 text-left transition ${
                      selectedTableId === table.table_id
                        ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/5'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-black text-slate-900">{table.name}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          v{table.version} • {table.row_count} строк • {table.filename || table.source_type}
                        </div>
                        {Array.isArray(table.validation_summary_json.warnings) && table.validation_summary_json.warnings.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                              {table.validation_summary_json.warnings.length} warning
                            </span>
                          </div>
                        )}
                      </div>
                      {table.is_active && (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-black uppercase text-emerald-700">
                          Active
                        </span>
                      )}
                    </div>
                    {!table.is_active && (
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleActivateTable(table.table_id);
                        }}
                        className="mt-3 rounded-xl border border-slate-200 px-2.5 py-1.5 text-[11px] font-bold text-slate-700 transition hover:text-slate-900"
                      >
                        Сделать активной
                      </button>
                    )}
                  </button>
                ))}
              </div>
            </Panel>

            <Panel title={selectedTable ? `Live preview: ${selectedTable.name}` : 'Выберите таблицу'}>
              {selectedTable ? (
                <>
                  <div className="mb-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 xl:grid-cols-[minmax(0,1.2fr)_180px_auto]">
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Название таблицы</span>
                      <input
                        value={tableEditorName}
                        onChange={(event) => setTableEditorName(event.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Статус</span>
                      <select
                        value={tableEditorStatus}
                        onChange={(event) => setTableEditorStatus(event.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none"
                      >
                        <option value="active">Active</option>
                        <option value="draft">Draft</option>
                        <option value="stale">Stale</option>
                        <option value="archived">Archived</option>
                      </select>
                    </label>
                    <div className="flex items-end gap-2">
                      <button
                        onClick={() => void handleUpdateTableMeta()}
                        disabled={savingTableMeta || !tableEditorName.trim()}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
                      >
                        {savingTableMeta ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      {!selectedTable.is_active && (
                        <button
                          onClick={() => void handleActivateTable(selectedTable.table_id)}
                          className="rounded-xl bg-[var(--accent-primary)] px-3 py-2 text-sm font-bold text-white transition hover:opacity-90"
                        >
                          Активировать
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-black text-slate-900">Новая версия таблицы</div>
                        <div className="text-xs text-slate-500">
                          Можно создать версию из текущего live preview или загрузить новый файл поверх выбранной версии.
                        </div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-600">
                        v{selectedTable.version}
                      </span>
                    </div>
                    <div className="flex flex-col gap-3 lg:flex-row">
                      <input
                        value={replacementVersionName}
                        onChange={(event) => setReplacementVersionName(event.target.value)}
                        placeholder="Имя новой версии"
                        className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none"
                      />
                      <input
                        type="file"
                        accept=".csv,.xlsx,.json,.txt,.tsv"
                        onChange={(event) => setReplacementFile(event.target.files?.[0] ?? null)}
                        className="block text-xs text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-100 file:px-3 file:py-3 file:font-bold file:text-slate-700"
                      />
                      <button
                        onClick={() => void handleReplaceTable()}
                        disabled={replacingTable || !replacementVersionName.trim()}
                        className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
                      >
                        {replacingTable ? 'Создание версии...' : 'Создать новую версию'}
                      </button>
                      <button
                        onClick={() => void handleReplaceTableFromFile()}
                        disabled={replacingTable || !replacementFile}
                        className="rounded-2xl bg-[var(--accent-primary)] px-4 py-3 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                      >
                        {replacingTable ? 'Загрузка версии...' : 'Загрузить файл как версию'}
                      </button>
                    </div>
                  </div>

                  <div className="mb-4 grid gap-3 xl:grid-cols-[repeat(4,minmax(0,1fr))]">
                    <SummaryMetricCard label="Imported" value={String(selectedTableSummary.importedRows)} tone="emerald" />
                    <SummaryMetricCard label="Total parsed" value={String(selectedTableSummary.totalRows)} tone="slate" />
                    <SummaryMetricCard label="Skipped" value={String(selectedTableSummary.skippedRows)} tone={selectedTableSummary.skippedRows > 0 ? 'amber' : 'slate'} />
                    <SummaryMetricCard label="Warnings" value={String(selectedTableSummary.warnings.length)} tone={selectedTableSummary.warnings.length > 0 ? 'amber' : 'slate'} />
                  </div>

                  {(selectedTableSummary.warnings.length > 0 || selectedTableSummary.artifactId || selectedTableSummary.replacedTableId) && (
                    <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-black text-slate-900">Import health</div>
                          <div className="text-xs text-slate-500">Сводка последнего импорта и технические маркеры для оператора.</div>
                        </div>
                        <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${
                          selectedTableSummary.warnings.length > 0 || selectedTableSummary.skippedRows > 0
                            ? 'bg-amber-50 text-amber-700'
                            : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {selectedTableSummary.warnings.length > 0 || selectedTableSummary.skippedRows > 0 ? 'Needs attention' : 'Healthy'}
                        </span>
                      </div>
                      <div className="space-y-2">
                        {selectedTableSummary.warnings.map((warning) => (
                          <AlertChip key={warning} tone="amber" text={humanizeImportWarning(warning)} />
                        ))}
                        {selectedTableSummary.artifactId && (
                          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                            Artifact: <span className="font-bold">{selectedTableSummary.artifactId}</span>
                          </div>
                        )}
                        {selectedTableSummary.replacedTableId && (
                          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                            Replaced table: <span className="font-bold">{selectedTableSummary.replacedTableId}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="mb-4 flex flex-col gap-3 lg:flex-row">
                    <input
                      value={rowQuery}
                      onChange={(event) => setRowQuery(event.target.value)}
                      placeholder="Фильтр по OEM, бренду, детали"
                      className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none"
                    />
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
                      {selectedTable.row_count} строк
                    </div>
                  </div>
                  <div className="mb-4 grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 xl:grid-cols-[minmax(0,1fr)_140px_140px_auto]">
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Bulk category</span>
                      <input
                        value={bulkDraft.category}
                        onChange={(event) => setBulkDraft((current) => ({ ...current, category: event.target.value }))}
                        placeholder="Например: brakes"
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Days</span>
                      <input
                        value={bulkDraft.delivery_days}
                        onChange={(event) => setBulkDraft((current) => ({ ...current, delivery_days: event.target.value }))}
                        type="number"
                        placeholder="4"
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Stock</span>
                      <input
                        value={bulkDraft.stock_qty}
                        onChange={(event) => setBulkDraft((current) => ({ ...current, stock_qty: event.target.value }))}
                        type="number"
                        placeholder="12"
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none"
                      />
                    </label>
                    <div className="flex items-end gap-2">
                      <button
                        onClick={() => void handleBulkUpdate()}
                        disabled={bulkSaving || selectedRowKeys.length === 0}
                        className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                      >
                        {bulkSaving ? 'Обновление...' : `Обновить ${selectedRowKeys.length || ''}`.trim()}
                      </button>
                      <button
                        onClick={() => setSelectedRowKeys([])}
                        disabled={selectedRowKeys.length === 0}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
                      >
                        Сбросить
                      </button>
                    </div>
                  </div>
                  <div className="overflow-x-auto rounded-2xl border border-slate-200 w-full">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-50 text-slate-500">
                        <tr>
                          <th className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={tableRows.length > 0 && selectedRowKeys.length === tableRows.length}
                              onChange={(event) => handleToggleAllRows(event.target.checked)}
                            />
                          </th>
                          <th className="px-4 py-3">Позиция</th>
                          <th className="px-4 py-3">OEM</th>
                          <th className="px-4 py-3">Бренд</th>
                          <th className="px-4 py-3">Цена</th>
                          <th className="px-4 py-3">Stock</th>
                          <th className="px-4 py-3">Health</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 bg-white">
                        {loadingRows ? (
                          <tr>
                            <td className="px-4 py-4 text-slate-500" colSpan={7}>
                              Загрузка строк...
                            </td>
                          </tr>
                        ) : tableRows.length ? (
                          tableRows.map((row) => (
                            <tr
                              key={row.row_key}
                              onClick={() => setSelectedRow(row)}
                              className={`cursor-pointer transition hover:bg-slate-50 ${
                                selectedRow?.row_key === row.row_key ? 'bg-indigo-50/60' : ''
                              }`}
                            >
                              <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                                <input
                                  type="checkbox"
                                  checked={selectedRowKeys.includes(row.row_key)}
                                  onChange={(event) => toggleRowSelection(row.row_key, event.target.checked)}
                                />
                              </td>
                              <td className="px-4 py-3 font-semibold text-slate-800">{row.part_name}</td>
                              <td className="px-4 py-3 text-slate-600">{row.oem_number || '—'}</td>
                              <td className="px-4 py-3 text-slate-600">{row.brand || '—'}</td>
                              <td className="px-4 py-3 text-slate-600">
                                {row.price.toLocaleString()} {row.currency}
                              </td>
                              <td className="px-4 py-3 text-slate-600">{row.stock_qty}</td>
                              <td className="px-4 py-3">
                                <RowHealthBadge warnings={getRowWarnings(row)} />
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="px-4 py-4 text-slate-500" colSpan={7}>
                              В таблице пока нет строк для предпросмотра.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center text-sm text-slate-500">
                  Слева выберите таблицу или создайте новую.
                </div>
              )}
            </Panel>

            <Panel title="Инспектор строки">
              {selectedRow && rowDraft ? (
                <div className="space-y-3 text-sm">
                  {selectedRowWarnings.length > 0 && (
                    <div className="space-y-2">
                      {selectedRowWarnings.map((warning) => (
                        <AlertChip key={warning} tone="amber" text={warning} />
                      ))}
                    </div>
                  )}
                  <EditableField label="Позиция" value={rowDraft.part_name} onChange={(value) => setRowDraft((current) => current ? { ...current, part_name: value } : current)} />
                  <EditableField label="OEM" value={rowDraft.oem_number} onChange={(value) => setRowDraft((current) => current ? { ...current, oem_number: value } : current)} />
                  <EditableField label="Бренд" value={rowDraft.brand} onChange={(value) => setRowDraft((current) => current ? { ...current, brand: value } : current)} />
                  <EditableField label="Категория" value={rowDraft.category} onChange={(value) => setRowDraft((current) => current ? { ...current, category: value } : current)} />
                  <EditableField label="Цена" value={rowDraft.price} type="number" onChange={(value) => setRowDraft((current) => current ? { ...current, price: value } : current)} />
                  <EditableField label="Валюта" value={rowDraft.currency} onChange={(value) => setRowDraft((current) => current ? { ...current, currency: value } : current)} />
                  <EditableField label="Остаток" value={rowDraft.stock_qty} type="number" onChange={(value) => setRowDraft((current) => current ? { ...current, stock_qty: value } : current)} />
                  <EditableField label="Доставка" value={rowDraft.delivery_days} type="number" onChange={(value) => setRowDraft((current) => current ? { ...current, delivery_days: value } : current)} />
                  <button
                    onClick={() => void handleSaveRow()}
                    disabled={savingRow}
                    className="w-full rounded-2xl bg-[var(--accent-primary)] px-4 py-3 text-sm font-bold text-white transition hover:opacity-90 disabled:opacity-50"
                  >
                    {savingRow ? 'Сохранение...' : 'Сохранить изменения строки'}
                  </button>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Raw payload</div>
                    <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-600">
                      {JSON.stringify(selectedRow.raw_payload_json, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center text-sm text-slate-500">
                  Выберите строку из live preview.
                </div>
              )}
            </Panel>
          </div>
        )}

        {activeTab === 'analytics' && analytics && (
          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Panel title="Health signals">
              <div className="space-y-3">
                {analyticsHighlights.map((highlight, index) => (
                  <AlertChip key={`${highlight.text}-${index}`} tone={highlight.tone} text={highlight.text} />
                ))}
              </div>
            </Panel>

            <Panel title="Summary">
              <div className="grid gap-3 md:grid-cols-2">
                <DetailRow label="Catalog items" value={String(analytics.summary.catalog_item_count)} />
                <DetailRow label="Active tables" value={`${analytics.summary.active_table_count}/${analytics.summary.table_count}`} />
                <DetailRow label="Средняя цена" value={`${analytics.summary.avg_price.toLocaleString()} RUB`} />
                <DetailRow label="Средняя доставка" value={`${analytics.summary.avg_delivery_days} дн.`} />
                <DetailRow label="Manual rating" value={analytics.summary.manual_rating ? analytics.summary.manual_rating.toFixed(1) : '—'} />
                <DetailRow label="Auto rating" value={analytics.summary.auto_rating.toFixed(2)} />
                <DetailRow label="Stale tables" value={String(analytics.summary.stale_table_count)} />
                <DetailRow label="Price delta vs median" value={`${(analytics.summary.avg_price_deviation * 100).toFixed(1)}%`} />
              </div>
            </Panel>

            <Panel title="Category coverage">
              <div className="space-y-3">
                {analytics.category_coverage.map((entry) => (
                  <div key={entry.category}>
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold text-slate-600">
                      <span>{entry.category}</span>
                      <span>{entry.count}</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100">
                      <div
                        className="h-2 rounded-full bg-indigo-500"
                        style={{ width: `${Math.max(8, (entry.count / Math.max(1, analytics.summary.catalog_item_count)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Reliability history">
              <div className="space-y-3">
                {analytics.reliability_history.map((entry) => (
                  <div key={`${entry.logged_at}-${entry.event_type}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-black text-slate-800">{Math.round(entry.reliability_score * 100)}%</span>
                      <span className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">{entry.event_type}</span>
                    </div>
                    <div className="mt-1 text-xs text-slate-500">{new Date(entry.logged_at).toLocaleString()}</div>
                    <div className="mt-2 text-sm text-slate-700">{entry.reason || '—'}</div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Table health">
              <div className="space-y-3">
                {analytics.table_health.map((entry) => (
                  <div key={entry.table_id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div>
                      <div className="text-sm font-black text-slate-800">{entry.name}</div>
                      <div className="text-xs text-slate-500">{entry.row_count} строк</div>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-black uppercase ${
                      entry.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      {entry.status}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        )}

        {activeTab === 'logs' && (
          <Panel title="Журнал событий">
            <div className="mb-4 grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)_auto]">
              <label className="block rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Тип события</span>
                <select
                  value={logFilter}
                  onChange={(event) => setLogFilter(event.target.value)}
                  className="w-full border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
                >
                  <option value="all">Все события</option>
                  {logTypeOptions.map((eventType) => (
                    <option key={eventType} value={eventType}>
                      {eventType}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Поиск по логу</span>
                <input
                  value={logQuery}
                  onChange={(event) => setLogQuery(event.target.value)}
                  placeholder="event, actor, payload"
                  className="w-full border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
                />
              </label>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Найдено</div>
                <div className="mt-1 text-2xl font-black text-slate-900">{filteredLogs.length}</div>
              </div>
            </div>
            <div className="space-y-3">
              {filteredLogs.map((log) => (
                <div key={log.event_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${getLogEventTone(log.event_type)}`} />
                      <div className="text-sm font-black text-slate-800">{log.event_type}</div>
                    </div>
                    <div className="text-xs text-slate-500">{new Date(log.created_at).toLocaleString()}</div>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    <span>{log.actor_id}</span>
                    {log.table_id && <span>table {log.table_id}</span>}
                  </div>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-600">
                    {JSON.stringify(log.payload, null, 2)}
                  </pre>
                </div>
              ))}
              {filteredLogs.length === 0 && (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center text-sm text-slate-500">
                  По текущим фильтрам события не найдены.
                </div>
              )}
            </div>
          </Panel>
        )}

        {activeTab === 'settings' && supplier && settingsDraft && (
          <Panel title="Операционные настройки">
            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <SelectField
                    label="Статус"
                    value={settingsDraft.status}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, status: value } : current)}
                    options={[
                      { value: 'active', label: 'Active' },
                      { value: 'pending', label: 'Pending' },
                      { value: 'blocked', label: 'Blocked' },
                      { value: 'archived', label: 'Archived' },
                    ]}
                  />
                  <SelectField
                    label="Sync status"
                    value={settingsDraft.last_sync_status}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, last_sync_status: value } : current)}
                    options={[
                      { value: 'synced', label: 'Synced' },
                      { value: 'stale', label: 'Stale' },
                      { value: 'syncing', label: 'Syncing' },
                      { value: 'failed', label: 'Failed' },
                    ]}
                  />
                  <EditableField
                    label="Account owner"
                    value={settingsDraft.account_owner}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, account_owner: value } : current)}
                  />
                  <SelectField
                    label="Валюта"
                    value={settingsDraft.currency_default}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, currency_default: value } : current)}
                    options={[
                      { value: 'RUB', label: 'RUB' },
                      { value: 'USD', label: 'USD' },
                      { value: 'EUR', label: 'EUR' },
                      { value: 'CNY', label: 'CNY' },
                    ]}
                  />
                  <EditableField
                    label="Payment terms"
                    value={settingsDraft.payment_terms}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, payment_terms: value } : current)}
                  />
                  <EditableField
                    label="Delivery terms"
                    value={settingsDraft.delivery_terms}
                    onChange={(value) => setSettingsDraft((current) => current ? { ...current, delivery_terms: value } : current)}
                  />
                </div>
                <label className="block rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Operational note</span>
                  <textarea
                    value={settingsDraft.notes_internal}
                    onChange={(event) => setSettingsDraft((current) => current ? { ...current, notes_internal: event.target.value } : current)}
                    className="mt-2 h-28 w-full resize-none border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
                  />
                </label>
                <div className="flex justify-end">
                  <button
                    onClick={() => void handleSaveSettings()}
                    disabled={savingSettings}
                    className="rounded-2xl bg-[var(--accent-primary)] px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
                  >
                    {savingSettings ? 'Сохранение...' : 'Сохранить настройки'}
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 text-sm font-black text-slate-900">Manual rating override</div>
                  <div className="grid gap-3">
                    <EditableField label="Manual rating" value={ratingDraft} type="number" onChange={setRatingDraft} />
                    <label className="block rounded-2xl border border-slate-200 bg-white px-4 py-3">
                      <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">Причина изменения</span>
                      <textarea
                        value={ratingReason}
                        onChange={(event) => setRatingReason(event.target.value)}
                        placeholder="Например: escalation after late deliveries"
                        className="mt-2 h-24 w-full resize-none border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
                      />
                    </label>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <DetailRow label="Auto rating" value={supplier.rating_auto.toFixed(2)} />
                      <DetailRow label="Текущий manual" value={supplier.rating_manual ? supplier.rating_manual.toFixed(1) : '—'} />
                    </div>
                    <button
                      onClick={() => void handleSaveRating()}
                      disabled={savingRating}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900 disabled:opacity-50"
                    >
                      {savingRating ? 'Обновление...' : 'Обновить rating'}
                    </button>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                  Для изменения имени, контактов и базового профиля используйте кнопку <strong>Редактировать</strong> в шапке карточки.
                </div>
              </div>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-2xl px-5 py-2 text-xs font-bold tracking-wide transition-all duration-200 ${
        active 
          ? 'bg-[var(--accent-primary)] text-white shadow-[0_4px_12px_rgba(37,99,235,0.25)] scale-[1.02]' 
          : 'bg-white text-[var(--text-secondary)] border border-[var(--border-default)] hover:border-slate-300 hover:text-[var(--text-primary)] hover:bg-[var(--state-hover)] shadow-sm'
      }`}
    >
      {label}
    </button>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_8px_30px_rgba(0,0,0,0.02)] transition-all">
      <h3 className="mb-4 text-base font-extrabold tracking-tight text-slate-900">{title}</h3>
      {children}
    </section>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 transition-all duration-300 hover:bg-white/10 hover:scale-[1.02] hover:border-white/20 hover:shadow-[0_8px_32px_-10px_rgba(255,255,255,0.05)]">
      <div className="text-[11px] font-black uppercase tracking-[0.18em] text-white/50">{label}</div>
      <div className="mt-1 text-2xl font-black text-white">{value}</div>
    </div>
  );
}

function DetailRow({ label, value, isLink, linkType }: { label: string; value: string; isLink?: boolean; linkType?: 'tel' | 'mailto' }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 shadow-[0_2px_8px_rgba(15,23,42,0.02)] hover:shadow-md transition-all hover:scale-[1.01]">
      <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</div>
      {isLink && value !== '—' ? (
        <a 
          href={`${linkType}:${value}`} 
          className="mt-1 block text-sm font-semibold text-[var(--accent-primary)] hover:underline"
        >
          {value}
        </a>
      ) : (
        <div className="mt-1 text-sm font-semibold text-slate-700">{value}</div>
      )}
    </div>
  );
}

function EditableField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'number';
}) {
  return (
    <label className="block rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="block rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border-none bg-transparent text-sm font-semibold text-slate-700 outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function AlertChip({ tone, text }: { tone: 'emerald' | 'amber' | 'rose'; text: string }) {
  const tones = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    rose: 'border-rose-200 bg-rose-50 text-rose-700',
  };
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${tones[tone]}`}>{text}</div>;
}

function getLogEventTone(eventType: string): string {
  if (eventType.includes('archived') || eventType.includes('blocked')) {
    return 'bg-rose-500';
  }
  if (eventType.includes('rating') || eventType.includes('updated') || eventType.includes('replaced')) {
    return 'bg-amber-500';
  }
  if (eventType.includes('created') || eventType.includes('imported') || eventType.includes('activated')) {
    return 'bg-emerald-500';
  }
  return 'bg-slate-400';
}

function SummaryMetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'emerald' | 'amber' | 'slate';
}) {
  const tones = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
  };
  return (
    <div className={`rounded-2xl border px-4 py-3 ${tones[tone]}`}>
      <div className="text-[11px] font-bold uppercase tracking-[0.18em] opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-black">{value}</div>
    </div>
  );
}

function RowHealthBadge({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700">OK</span>;
  }
  return (
    <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-700">
      {warnings.length} issue{warnings.length > 1 ? 's' : ''}
    </span>
  );
}

function getRowWarnings(row: SupplierTableRowRecord): string[] {
  const warnings: string[] = [];
  if (!row.oem_number) warnings.push('OEM номер не заполнен');
  if (!row.brand) warnings.push('Бренд не заполнен');
  if (row.price <= 0) warnings.push('Цена невалидна или равна 0');
  if (row.stock_qty <= 0) warnings.push('Остаток отсутствует');
  if (row.delivery_days > 7) warnings.push('Срок поставки выше рабочего порога');
  return warnings;
}

function humanizeImportWarning(warning: string): string {
  if (warning === 'no_rows_imported') return 'Импорт завершился без валидных строк.';
  if (warning === 'part_name_inferred_from_first_non_empty_column') return 'Название детали определялось эвристически из первой непустой колонки.';
  if (warning.startsWith('skipped_rows:')) {
    const count = warning.split(':')[1] ?? '0';
    return `Во время импорта пропущено строк: ${count}.`;
  }
  return warning;
}
