import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiJson } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';
import {
  Button,
  ErrorState,
  Icon,
  InlineAlert,
  Skeleton,
  SubnavPills,
} from './Primitives';
import { gsap } from 'gsap';
import {
  CURRENCY_OPTIONS,
  STATUS_FILTER_OPTIONS,
  TABLE_STATUS_OPTIONS,
  getSupplierStatusMeta,
  getSyncStatusMeta,
  getTableStatusLabel,
  supplierInitials,
} from './supplierConfig';
import type {
  SupplierAnalyticsRecord,
  SupplierLogRecord,
  SupplierRecord,
  SupplierTableRecord,
  SupplierTableRowRecord,
} from './supplierTypes';

type TabType = 'overview' | 'profile' | 'tables' | 'analytics' | 'logs' | 'settings';

const DETAIL_TABS: Array<{ id: TabType; label: string; icon: string }> = [
  { id: 'overview', label: 'Обзор', icon: 'circle-info' },
  { id: 'profile', label: 'Профиль', icon: 'book-open' },
  { id: 'tables', label: 'Таблицы', icon: 'folder-open' },
  { id: 'analytics', label: 'Аналитика', icon: 'wave-square' },
  { id: 'logs', label: 'Журнал', icon: 'list' },
  { id: 'settings', label: 'Настройки', icon: 'pencil' },
];
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
  const [confirmArchive, setConfirmArchive] = useState(false);

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
    setConfirmArchive(false);
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
      setError('Укажите корректный ручной рейтинг.');
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
          reason: ratingReason.trim() || 'ручное обновление оператором',
        }),
      });
      setImportMessage(`Ручной рейтинг обновлён до ${parsedRating.toFixed(1)}.`);
      await fetchSupplierWorkspace();
      onRefresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось обновить ручной рейтинг');
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
      highlights.push({ tone: 'amber', text: 'Активный фид устарел. Загрузите новую версию таблицы.' });
    }
    if (supplier.reliability_score < 0.8) {
      highlights.push({ tone: 'rose', text: 'Низкая надёжность. Проверьте инциденты и ручной рейтинг.' });
    }
    if (analytics.summary.avg_price_deviation > 0.1) {
      highlights.push({ tone: 'amber', text: 'Средняя цена отклоняется от медианы более чем на 10%.' });
    }
    if (analytics.summary.active_table_count === 0) {
      highlights.push({ tone: 'rose', text: 'Нет активной таблицы. Подбор может идти по устаревшим данным.' });
    }
    if (highlights.length === 0) {
      highlights.push({ tone: 'emerald', text: 'Критичных сигналов сейчас нет.' });
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
    if (loading || !supplier) return;
    const header = document.querySelector('.premium-header-content');
    const tab = document.querySelector('.premium-tab-content');
    if (header) {
      gsap.fromTo(
        header,
        { y: 10 },
        { y: 0, duration: 0.45, ease: 'power2.out', clearProps: 'transform' },
      );
    }
    if (tab) {
      gsap.fromTo(
        tab,
        { y: 6 },
        { y: 0, duration: 0.35, ease: 'power1.out', clearProps: 'transform' },
      );
    }
  }, [loading, activeTab, supplier, supplierId]);

  if (loading) {
    return (
      <div className="flex h-full flex-col gap-4 overflow-hidden p-5 md:p-6">
        <div className="panel-card p-6">
          <div className="mb-4 flex gap-3">
            <Skeleton className="h-9 w-36" />
            <Skeleton className="ml-auto h-9 w-28" />
            <Skeleton className="h-9 w-28" />
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div className="space-y-3">
              <Skeleton className="h-6 w-24 rounded-full" />
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-control" />
              ))}
            </div>
          </div>
        </div>
        <Skeleton className="h-12 w-full rounded-control" />
        <div className="grid flex-1 gap-4 md:grid-cols-2">
          <Skeleton className="h-48 w-full rounded-card" />
          <Skeleton className="h-48 w-full rounded-card" />
        </div>
      </div>
    );
  }

  if (!supplier) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
        <Button variant="secondary" icon="arrow-left" onClick={onBack}>
          Назад к каталогу
        </Button>
        <ErrorState
          title="Не удалось загрузить поставщика"
          message={error || 'Карточка недоступна. Вернитесь в каталог или повторите попытку.'}
          onRetry={() => void fetchSupplierWorkspace()}
        />
      </div>
    );
  }

  const statusMeta = getSupplierStatusMeta(supplier.status);
  const syncMeta = getSyncStatusMeta(supplier.last_sync_status);
  const initials = supplierInitials(supplier.name) || 'П';

  return (
    <div className="flex h-full flex-col overflow-hidden bg-app-bg">
      <div className="relative overflow-hidden border-b border-white/5 bg-[linear-gradient(135deg,#0b1b33_0%,#12306b_55%,#1d4ed8_145%)] p-5 text-white shadow-ds-md md:p-6">
        <div className="pointer-events-none absolute left-[-10%] top-[-40%] h-[320px] w-[320px] rounded-full bg-blue-400/10 blur-[90px]" />
        <div className="pointer-events-none absolute bottom-[-40%] right-[-10%] h-[320px] w-[320px] rounded-full bg-indigo-400/10 blur-[90px]" />

        <div className="premium-header-content relative z-10">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 rounded-control border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold text-white/90 transition hover:bg-white/15"
            >
              <Icon name="arrow-left" size={12} />
              Назад к каталогу
            </button>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onEditSupplier(supplier)}
                className="inline-flex items-center gap-2 rounded-control border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold text-white/90 transition hover:bg-white/15"
              >
                <Icon name="pencil" size={12} />
                Редактировать
              </button>
              <button
                type="button"
                onClick={() => setConfirmArchive(true)}
                className="inline-flex items-center gap-2 rounded-control border border-rose-400/30 bg-rose-500/15 px-4 py-2 text-xs font-semibold text-rose-100 transition hover:bg-rose-500/25"
              >
                <Icon name="trash" size={12} />
                Архивировать
              </button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-white">
                  {statusMeta.label}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-white/75">
                  {syncMeta.label}
                </span>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 shrink-0 select-none items-center justify-center rounded-[16px] border border-white/15 bg-white/10 text-lg font-bold uppercase text-white shadow-lg">
                  {initials}
                </div>
                <div className="min-w-0">
                  <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">{supplier.name}</h2>
                  <p className="mt-1.5 text-xs font-medium text-white/65">
                    {supplier.city || '—'} · {supplier.specialization || 'Общий sourcing'}
                  </p>
                </div>
              </div>

              {supplier.categories.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {supplier.categories.map((category) => (
                    <span
                      key={category}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold text-white/85"
                    >
                      {category}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <MetricBox label="Надёжность" value={`${Math.round(supplier.reliability_score * 100)}%`} />
              <MetricBox label="Ручной рейтинг" value={supplier.rating_manual ? supplier.rating_manual.toFixed(1) : '—'} />
              <MetricBox label="Таблиц" value={`${supplier.active_table_count}/${supplier.table_count}`} />
              <MetricBox label="SLA" value={`${supplier.avg_delivery_days} дн.`} />
            </div>
          </div>
        </div>
      </div>

      {(error || importMessage) && (
        <div className="space-y-0 border-b border-line bg-surface-1 px-5 pt-3 md:px-6">
          {error && <InlineAlert type="danger" message={error} />}
          {importMessage && <InlineAlert type="success" message={importMessage} />}
        </div>
      )}

      <div className="border-b border-line bg-surface-1 px-5 py-3 md:px-6">
        <SubnavPills
          activeTab={activeTab}
          onChangeTab={(id) => setActiveTab(id as TabType)}
          tabs={DETAIL_TABS}
        />
      </div>

      <div className="premium-tab-content min-h-0 flex-1 overflow-y-auto p-5 md:p-6">
        {activeTab === 'overview' && (
          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Panel title="Операционный профиль">
              <div className="grid gap-3 md:grid-cols-2">
                <DetailRow label="Контакт" value={supplier.contact_person || '—'} />
                <DetailRow label="Телефон" value={supplier.phone || '—'} isLink linkType="tel" />
                <DetailRow label="Email" value={supplier.email || '—'} isLink linkType="mailto" />
                <DetailRow label="Владелец" value={supplier.account_owner || '—'} />
                <DetailRow label="Условия оплаты" value={supplier.payment_terms || '—'} />
                <DetailRow label="Условия поставки" value={supplier.delivery_terms || '—'} />
                <DetailRow
                  label="Последний фид"
                  value={supplier.last_feed_at ? new Date(supplier.last_feed_at).toLocaleString('ru-RU') : '—'}
                />
                <DetailRow
                  label="Последняя активность"
                  value={supplier.last_activity_at ? new Date(supplier.last_activity_at).toLocaleString('ru-RU') : '—'}
                />
              </div>
            </Panel>

            <Panel title="Операционные сигналы">
              <div className="space-y-3">
                <AlertChip
                  tone={supplier.last_sync_status === 'stale' ? 'amber' : 'emerald'}
                  text={
                    supplier.last_sync_status === 'stale'
                      ? 'Фид устарел — нужна новая версия таблицы'
                      : 'Фид синхронизирован'
                  }
                />
                <AlertChip
                  tone={supplier.reliability_score < 0.8 ? 'rose' : 'emerald'}
                  text={
                    supplier.reliability_score < 0.8
                      ? 'Надёжность ниже порога 80%'
                      : 'Надёжность в рабочем диапазоне'
                  }
                />
                <AlertChip
                  tone={supplier.active_table_count === 0 ? 'rose' : 'emerald'}
                  text={
                    supplier.active_table_count === 0
                      ? 'Нет активной таблицы для live-просмотра'
                      : 'Активная таблица доступна для инспекции'
                  }
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
              <DetailRow label="Телефон" value={supplier.phone || '—'} isLink linkType="tel" />
              <DetailRow label="Email" value={supplier.email || '—'} isLink linkType="mailto" />
              <DetailRow label="Город" value={supplier.city || '—'} />
              <DetailRow label="Специализация" value={supplier.specialization || '—'} />
              <DetailRow label="Валюта" value={supplier.currency_default} />
              <DetailRow label="Статус" value={statusMeta.label} />
              <DetailRow label="Синхронизация" value={syncMeta.label} />
            </div>
            <div className="mt-4 rounded-control border border-line bg-surface-2 px-4 py-3 text-sm text-ink-secondary">
              {supplier.notes_internal || 'Внутренние заметки не заполнены.'}
            </div>
          </Panel>
        )}

        {activeTab === 'tables' && (
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
            <Panel title="Таблицы поставщика">
              <div className="space-y-3">
                <div className="space-y-4 rounded-control border border-line bg-surface-2 p-4">
                  <div>
                    <label className="ui-eyebrow mb-1 block">Название таблицы</label>
                    <input
                      value={newTableName}
                      onChange={(event) => setNewTableName(event.target.value)}
                      placeholder="Например: Прайс OEM Q3"
                      className="w-full rounded-control border border-line bg-surface-1 px-4 py-2.5 text-sm text-ink-primary outline-none transition focus:border-accent-primary"
                    />
                  </div>

                  <div>
                    <span className="ui-eyebrow mb-1 block">Файл импорта</span>
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
                        className={`group relative flex cursor-pointer select-none flex-col items-center justify-center gap-2 rounded-control border-2 border-dashed p-6 text-center transition-all duration-[var(--transition-base)] ${
                          dragActive
                            ? 'scale-[1.01] border-accent-primary bg-[var(--state-selected)] shadow-ds-sm'
                            : 'border-line bg-surface-1 hover:border-accent-primary hover:bg-surface-2'
                        }`}
                      >
                        <Icon
                          name="cloud-arrow-up"
                          size={24}
                          className={`transition-colors ${
                            dragActive ? 'text-accent-primary' : 'text-ink-muted group-hover:text-accent-primary'
                          }`}
                        />
                        <span className="text-[12px] font-bold text-ink-primary">Перетащите файл сюда</span>
                        <span className="text-[10px] font-medium text-ink-muted">или кликните для выбора</span>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between gap-3 rounded-control border border-line bg-surface-1 p-4">
                        <div className="flex min-w-0 items-center gap-2.5">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[rgba(37,99,235,0.2)] bg-[var(--state-selected)]">
                            <Icon name="folder-open" size={16} className="text-accent-primary" />
                          </div>
                          <div className="min-w-0">
                            <div className="truncate text-[12px] font-bold text-ink-primary" title={newTableFile.name}>
                              {newTableFile.name}
                            </div>
                            <div className="text-[10px] font-semibold text-ink-muted">
                              {(newTableFile.size / 1024).toFixed(1)} KB
                            </div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setNewTableFile(null);
                          }}
                          className="flex h-7 w-7 items-center justify-center rounded-[10px] border border-line bg-surface-1 text-ink-muted transition hover:text-ink-primary"
                          title="Удалить файл"
                          aria-label="Удалить файл"
                        >
                          <Icon name="times" size={12} />
                        </button>
                      </div>
                    )}
                  </div>

                  <Button
                    variant="primary"
                    className="w-full"
                    loading={creatingTable}
                    disabled={creatingTable || (!newTableName.trim() && !newTableFile)}
                    onClick={() => void (newTableFile ? handleImportTable() : handleCreateTable())}
                  >
                    {newTableFile ? 'Импортировать таблицу' : 'Создать таблицу'}
                  </Button>
                </div>
                {tables.map((table) => (
                  <button
                    key={table.table_id}
                    type="button"
                    onClick={() => setSelectedTableId(table.table_id)}
                    className={`w-full rounded-control border p-3 text-left transition-all ${
                      selectedTableId === table.table_id
                        ? 'border-[rgba(37,99,235,0.35)] bg-[var(--state-selected)] ring-2 ring-[rgba(37,99,235,0.12)]'
                        : 'border-line bg-surface-1 hover:border-[rgba(37,99,235,0.2)]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-bold text-ink-primary">{table.name}</div>
                        <div className="mt-1 text-xs text-ink-muted">
                          v{table.version} · {table.row_count} строк · {table.filename || table.source_type}
                        </div>
                        {Array.isArray(table.validation_summary_json.warnings) && table.validation_summary_json.warnings.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                              {table.validation_summary_json.warnings.length} предупр.
                            </span>
                          </div>
                        )}
                      </div>
                      {table.is_active && (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-700">
                          Активна
                        </span>
                      )}
                    </div>
                    {!table.is_active && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleActivateTable(table.table_id);
                        }}
                        className="mt-3 rounded-[10px] border border-line bg-surface-1 px-2.5 py-1.5 text-[11px] font-bold text-ink-secondary transition hover:text-ink-primary"
                      >
                        Сделать активной
                      </button>
                    )}
                  </button>
                ))}
              </div>
            </Panel>

            <Panel title={selectedTable ? `Предпросмотр: ${selectedTable.name}` : 'Выберите таблицу'}>
              {selectedTable ? (
                <>
                  <div className="mb-4 grid gap-3 rounded-control border border-line bg-surface-2 p-4 xl:grid-cols-[minmax(0,1.2fr)_180px_auto]">
                    <label className="block">
                      <span className="ui-eyebrow mb-1 block">Название таблицы</span>
                      <input
                        value={tableEditorName}
                        onChange={(event) => setTableEditorName(event.target.value)}
                        className="w-full rounded-control border border-line bg-surface-1 px-3 py-2 text-sm text-ink-primary outline-none focus:border-accent-primary"
                      />
                    </label>
                    <label className="block">
                      <span className="ui-eyebrow mb-1 block">Статус</span>
                      <select
                        value={tableEditorStatus}
                        onChange={(event) => setTableEditorStatus(event.target.value)}
                        className="w-full rounded-control border border-line bg-surface-1 px-3 py-2 text-sm text-ink-primary outline-none focus:border-accent-primary"
                      >
                        {TABLE_STATUS_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="flex items-end gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={savingTableMeta}
                        disabled={savingTableMeta || !tableEditorName.trim()}
                        onClick={() => void handleUpdateTableMeta()}
                      >
                        Сохранить
                      </Button>
                      {!selectedTable.is_active && (
                        <Button size="sm" variant="primary" onClick={() => void handleActivateTable(selectedTable.table_id)}>
                          Активировать
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="mb-4 flex flex-col gap-3 rounded-control border border-line bg-surface-1 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-bold text-ink-primary">Новая версия таблицы</div>
                        <div className="text-xs text-ink-muted">
                          Создайте версию из текущего предпросмотра или загрузите новый файл поверх выбранной.
                        </div>
                      </div>
                      <span className="rounded-full bg-surface-2 px-2.5 py-1 text-[11px] font-bold tabular-nums text-ink-secondary">
                        v{selectedTable.version}
                      </span>
                    </div>
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                      <input
                        value={replacementVersionName}
                        onChange={(event) => setReplacementVersionName(event.target.value)}
                        placeholder="Имя новой версии"
                        className="flex-1 rounded-control border border-line bg-surface-2 px-4 py-2.5 text-sm text-ink-primary outline-none focus:border-accent-primary"
                      />
                      <input
                        type="file"
                        accept=".csv,.xlsx,.json,.txt,.tsv"
                        onChange={(event) => setReplacementFile(event.target.files?.[0] ?? null)}
                        className="block text-xs text-ink-secondary file:mr-3 file:rounded-control file:border-0 file:bg-surface-2 file:px-3 file:py-2.5 file:font-bold file:text-ink-secondary"
                      />
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={replacingTable}
                        disabled={replacingTable || !replacementVersionName.trim()}
                        onClick={() => void handleReplaceTable()}
                      >
                        Создать версию
                      </Button>
                      <Button
                        size="sm"
                        variant="primary"
                        loading={replacingTable}
                        disabled={replacingTable || !replacementFile}
                        onClick={() => void handleReplaceTableFromFile()}
                      >
                        Загрузить файл
                      </Button>
                    </div>
                  </div>

                  <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <SummaryMetricCard label="Импортировано" value={String(selectedTableSummary.importedRows)} tone="emerald" />
                    <SummaryMetricCard label="Распознано" value={String(selectedTableSummary.totalRows)} tone="slate" />
                    <SummaryMetricCard
                      label="Пропущено"
                      value={String(selectedTableSummary.skippedRows)}
                      tone={selectedTableSummary.skippedRows > 0 ? 'amber' : 'slate'}
                    />
                    <SummaryMetricCard
                      label="Предупреждения"
                      value={String(selectedTableSummary.warnings.length)}
                      tone={selectedTableSummary.warnings.length > 0 ? 'amber' : 'slate'}
                    />
                  </div>

                  {(selectedTableSummary.warnings.length > 0 ||
                    selectedTableSummary.artifactId ||
                    selectedTableSummary.replacedTableId) && (
                    <div className="mb-4 rounded-control border border-line bg-surface-2 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-bold text-ink-primary">Здоровье импорта</div>
                          <div className="text-xs text-ink-muted">
                            Сводка последнего импорта и технические маркеры.
                          </div>
                        </div>
                        <span
                          className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                            selectedTableSummary.warnings.length > 0 || selectedTableSummary.skippedRows > 0
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {selectedTableSummary.warnings.length > 0 || selectedTableSummary.skippedRows > 0
                            ? 'Требует внимания'
                            : 'В норме'}
                        </span>
                      </div>
                      <div className="space-y-2">
                        {selectedTableSummary.warnings.map((warning) => (
                          <AlertChip key={warning} tone="amber" text={humanizeImportWarning(warning)} />
                        ))}
                        {selectedTableSummary.artifactId && (
                          <div className="rounded-control border border-line bg-surface-1 px-4 py-3 text-sm text-ink-secondary">
                            Артефакт:{' '}
                            <span className="font-mono font-bold text-ink-primary">
                              {selectedTableSummary.artifactId}
                            </span>
                          </div>
                        )}
                        {selectedTableSummary.replacedTableId && (
                          <div className="rounded-control border border-line bg-surface-1 px-4 py-3 text-sm text-ink-secondary">
                            Заменена таблица:{' '}
                            <span className="font-mono font-bold text-ink-primary">
                              {selectedTableSummary.replacedTableId}
                            </span>
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
                      className="flex-1 rounded-control border border-line bg-surface-2 px-4 py-2.5 text-sm text-ink-primary outline-none focus:border-accent-primary"
                    />
                    <div className="rounded-control border border-line bg-surface-2 px-4 py-2.5 text-sm font-bold tabular-nums text-ink-secondary">
                      {selectedTable.row_count} строк
                    </div>
                  </div>

                  <div className="mb-4 grid gap-3 rounded-control border border-line bg-surface-2 p-4 xl:grid-cols-[minmax(0,1fr)_140px_140px_auto]">
                    <label className="block">
                      <span className="ui-eyebrow mb-1 block">Массовая категория</span>
                      <input
                        value={bulkDraft.category}
                        onChange={(event) => setBulkDraft((current) => ({ ...current, category: event.target.value }))}
                        placeholder="Например: тормоза"
                        className="w-full rounded-control border border-line bg-surface-1 px-3 py-2 text-sm text-ink-primary outline-none focus:border-accent-primary"
                      />
                    </label>
                    <label className="block">
                      <span className="ui-eyebrow mb-1 block">Дни</span>
                      <input
                        value={bulkDraft.delivery_days}
                        onChange={(event) =>
                          setBulkDraft((current) => ({ ...current, delivery_days: event.target.value }))
                        }
                        type="number"
                        placeholder="4"
                        className="w-full rounded-control border border-line bg-surface-1 px-3 py-2 text-sm tabular-nums text-ink-primary outline-none focus:border-accent-primary"
                      />
                    </label>
                    <label className="block">
                      <span className="ui-eyebrow mb-1 block">Остаток</span>
                      <input
                        value={bulkDraft.stock_qty}
                        onChange={(event) => setBulkDraft((current) => ({ ...current, stock_qty: event.target.value }))}
                        type="number"
                        placeholder="12"
                        className="w-full rounded-control border border-line bg-surface-1 px-3 py-2 text-sm tabular-nums text-ink-primary outline-none focus:border-accent-primary"
                      />
                    </label>
                    <div className="flex items-end gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        loading={bulkSaving}
                        disabled={bulkSaving || selectedRowKeys.length === 0}
                        onClick={() => void handleBulkUpdate()}
                      >
                        {selectedRowKeys.length > 0 ? `Обновить (${selectedRowKeys.length})` : 'Обновить'}
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={selectedRowKeys.length === 0}
                        onClick={() => setSelectedRowKeys([])}
                      >
                        Сбросить
                      </Button>
                    </div>
                  </div>

                  <div className="w-full overflow-x-auto rounded-card border border-line bg-surface-1">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-surface-2 text-ink-muted">
                        <tr>
                          <th className="px-4 py-3" scope="col">
                            <input
                              type="checkbox"
                              aria-label="Выбрать все строки"
                              checked={tableRows.length > 0 && selectedRowKeys.length === tableRows.length}
                              onChange={(event) => handleToggleAllRows(event.target.checked)}
                            />
                          </th>
                          <th className="px-4 py-3" scope="col">
                            Позиция
                          </th>
                          <th className="px-4 py-3" scope="col">
                            OEM
                          </th>
                          <th className="px-4 py-3" scope="col">
                            Бренд
                          </th>
                          <th className="px-4 py-3" scope="col">
                            Цена
                          </th>
                          <th className="px-4 py-3" scope="col">
                            Остаток
                          </th>
                          <th className="px-4 py-3" scope="col">
                            Статус
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {loadingRows ? (
                          <tr>
                            <td className="px-4 py-4 text-ink-muted" colSpan={7}>
                              Загрузка строк...
                            </td>
                          </tr>
                        ) : tableRows.length ? (
                          tableRows.map((row) => (
                            <tr
                              key={row.row_key}
                              onClick={() => setSelectedRow(row)}
                              className={`cursor-pointer transition-colors hover:bg-state-hover ${
                                selectedRow?.row_key === row.row_key ? 'bg-[var(--state-selected)]' : ''
                              }`}
                            >
                              <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                                <input
                                  type="checkbox"
                                  aria-label={`Выбрать ${row.part_name}`}
                                  checked={selectedRowKeys.includes(row.row_key)}
                                  onChange={(event) => toggleRowSelection(row.row_key, event.target.checked)}
                                />
                              </td>
                              <td className="px-4 py-3 font-semibold text-ink-primary">{row.part_name}</td>
                              <td className="px-4 py-3 font-mono text-xs text-ink-secondary">
                                {row.oem_number || '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-secondary">{row.brand || '—'}</td>
                              <td className="px-4 py-3 tabular-nums text-ink-secondary">
                                {row.price.toLocaleString('ru-RU')} {row.currency}
                              </td>
                              <td className="px-4 py-3 tabular-nums text-ink-secondary">{row.stock_qty}</td>
                              <td className="px-4 py-3">
                                <RowHealthBadge warnings={getRowWarnings(row)} />
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td className="px-4 py-4 text-ink-muted" colSpan={7}>
                              В таблице пока нет строк для предпросмотра.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="rounded-card border border-dashed border-line-strong bg-surface-2 px-6 py-12 text-center text-sm text-ink-muted">
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
                  <EditableField
                    label="Позиция"
                    value={rowDraft.part_name}
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, part_name: value } : current))}
                  />
                  <EditableField
                    label="OEM"
                    value={rowDraft.oem_number}
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, oem_number: value } : current))}
                  />
                  <EditableField
                    label="Бренд"
                    value={rowDraft.brand}
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, brand: value } : current))}
                  />
                  <EditableField
                    label="Категория"
                    value={rowDraft.category}
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, category: value } : current))}
                  />
                  <EditableField
                    label="Цена"
                    value={rowDraft.price}
                    type="number"
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, price: value } : current))}
                  />
                  <EditableField
                    label="Валюта"
                    value={rowDraft.currency}
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, currency: value } : current))}
                  />
                  <EditableField
                    label="Остаток"
                    value={rowDraft.stock_qty}
                    type="number"
                    onChange={(value) => setRowDraft((current) => (current ? { ...current, stock_qty: value } : current))}
                  />
                  <EditableField
                    label="Доставка (дни)"
                    value={rowDraft.delivery_days}
                    type="number"
                    onChange={(value) =>
                      setRowDraft((current) => (current ? { ...current, delivery_days: value } : current))
                    }
                  />
                  <Button
                    variant="primary"
                    className="w-full"
                    loading={savingRow}
                    disabled={savingRow}
                    onClick={() => void handleSaveRow()}
                  >
                    Сохранить изменения строки
                  </Button>
                  <div className="rounded-control border border-line bg-surface-2 p-4">
                    <div className="ui-eyebrow mb-2">Сырой payload</div>
                    <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-ink-secondary">
                      {JSON.stringify(selectedRow.raw_payload_json, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="rounded-card border border-dashed border-line-strong bg-surface-2 px-6 py-12 text-center text-sm text-ink-muted">
                  Выберите строку из предпросмотра.
                </div>
              )}
            </Panel>
          </div>
        )}

        {activeTab === 'analytics' && analytics && (
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Сигналы здоровья">
              <div className="space-y-3">
                {analyticsHighlights.map((highlight, index) => (
                  <AlertChip key={`${highlight.text}-${index}`} tone={highlight.tone} text={highlight.text} />
                ))}
              </div>
            </Panel>

            <Panel title="Сводка">
              <div className="grid gap-3 md:grid-cols-2">
                <DetailRow label="Позиций в каталоге" value={String(analytics.summary.catalog_item_count)} />
                <DetailRow label="Активные таблицы" value={`${analytics.summary.active_table_count}/${analytics.summary.table_count}`} />
                <DetailRow label="Средняя цена" value={`${analytics.summary.avg_price.toLocaleString('ru-RU')} ₽`} />
                <DetailRow label="Средняя доставка" value={`${analytics.summary.avg_delivery_days} дн.`} />
                <DetailRow label="Ручной рейтинг" value={analytics.summary.manual_rating ? analytics.summary.manual_rating.toFixed(1) : '—'} />
                <DetailRow label="Авторейтинг" value={analytics.summary.auto_rating.toFixed(2)} />
                <DetailRow label="Устаревшие таблицы" value={String(analytics.summary.stale_table_count)} />
                <DetailRow label="Отклонение цены" value={`${(analytics.summary.avg_price_deviation * 100).toFixed(1)}%`} />
              </div>
            </Panel>

            <Panel title="Покрытие категорий">
              <div className="space-y-3">
                {analytics.category_coverage.length === 0 && (
                  <p className="text-sm text-ink-muted">Нет данных по категориям.</p>
                )}
                {analytics.category_coverage.map((entry) => (
                  <div key={entry.category}>
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold text-ink-secondary">
                      <span>{entry.category}</span>
                      <span className="tabular-nums">{entry.count}</span>
                    </div>
                    <div className="h-2 rounded-full bg-surface-3">
                      <div
                        className="h-2 rounded-full bg-accent-primary"
                        style={{ width: `${Math.max(8, (entry.count / Math.max(1, analytics.summary.catalog_item_count)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="История надёжности">
              <div className="space-y-3">
                {analytics.reliability_history.map((entry) => (
                  <div
                    key={`${entry.logged_at}-${entry.event_type}`}
                    className="rounded-control border border-line bg-surface-2 px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-bold tabular-nums text-ink-primary">
                        {Math.round(entry.reliability_score * 100)}%
                      </span>
                      <span className="ui-eyebrow">{entry.event_type}</span>
                    </div>
                    <div className="mt-1 text-xs text-ink-muted">
                      {new Date(entry.logged_at).toLocaleString('ru-RU')}
                    </div>
                    <div className="mt-2 text-sm text-ink-secondary">{entry.reason || '—'}</div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Здоровье таблиц">
              <div className="space-y-3">
                {analytics.table_health.map((entry) => (
                  <div
                    key={entry.table_id}
                    className="flex items-center justify-between rounded-control border border-line bg-surface-2 px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-bold text-ink-primary">{entry.name}</div>
                      <div className="text-xs text-ink-muted">{entry.row_count} строк</div>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${
                        entry.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-surface-3 text-ink-secondary'
                      }`}
                    >
                      {entry.is_active ? getTableStatusLabel('active') : getTableStatusLabel(entry.status)}
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
              <label className="block rounded-control border border-line bg-surface-2 px-4 py-3">
                <span className="ui-eyebrow mb-1 block">Тип события</span>
                <select
                  value={logFilter}
                  onChange={(event) => setLogFilter(event.target.value)}
                  className="w-full border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
                >
                  <option value="all">Все события</option>
                  {logTypeOptions.map((eventType) => (
                    <option key={eventType} value={eventType}>
                      {eventType}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block rounded-control border border-line bg-surface-2 px-4 py-3">
                <span className="ui-eyebrow mb-1 block">Поиск по логу</span>
                <input
                  value={logQuery}
                  onChange={(event) => setLogQuery(event.target.value)}
                  placeholder="событие, актор, payload"
                  className="w-full border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
                />
              </label>
              <div className="rounded-control border border-line bg-surface-2 px-4 py-3">
                <div className="ui-eyebrow">Найдено</div>
                <div className="mt-1 text-2xl font-bold tabular-nums text-ink-primary">{filteredLogs.length}</div>
              </div>
            </div>
            <div className="space-y-3">
              {filteredLogs.map((log) => (
                <div
                  key={log.event_id}
                  className="ui-log-item"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${getLogEventTone(log.event_type)}`} />
                      <div className="text-sm font-bold text-ink-primary">{log.event_type}</div>
                    </div>
                    <div className="text-xs text-ink-muted">
                      {new Date(log.created_at).toLocaleString('ru-RU')}
                    </div>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs font-semibold text-ink-muted">
                    <span>{log.actor_id}</span>
                    {log.table_id && <span className="font-mono">table {log.table_id}</span>}
                  </div>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-ink-secondary">
                    {JSON.stringify(log.payload, null, 2)}
                  </pre>
                </div>
              ))}
              {filteredLogs.length === 0 && (
                <div className="rounded-card border border-dashed border-line-strong bg-surface-2 px-6 py-10 text-center text-sm text-ink-muted">
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
                    onChange={(value) => setSettingsDraft((current) => (current ? { ...current, status: value } : current))}
                    options={STATUS_FILTER_OPTIONS.filter((o) => o.value !== 'all')}
                  />
                  <SelectField
                    label="Синхронизация"
                    value={settingsDraft.last_sync_status}
                    onChange={(value) =>
                      setSettingsDraft((current) => (current ? { ...current, last_sync_status: value } : current))
                    }
                    options={[
                      { value: 'synced', label: 'Синхронизирован' },
                      { value: 'stale', label: 'Устарел' },
                      { value: 'syncing', label: 'Синхронизация' },
                      { value: 'failed', label: 'Сбой' },
                    ]}
                  />
                  <EditableField
                    label="Владелец"
                    value={settingsDraft.account_owner}
                    onChange={(value) =>
                      setSettingsDraft((current) => (current ? { ...current, account_owner: value } : current))
                    }
                  />
                  <SelectField
                    label="Валюта"
                    value={settingsDraft.currency_default}
                    onChange={(value) =>
                      setSettingsDraft((current) => (current ? { ...current, currency_default: value } : current))
                    }
                    options={CURRENCY_OPTIONS.map((value) => ({ value, label: value }))}
                  />
                  <EditableField
                    label="Условия оплаты"
                    value={settingsDraft.payment_terms}
                    onChange={(value) =>
                      setSettingsDraft((current) => (current ? { ...current, payment_terms: value } : current))
                    }
                  />
                  <EditableField
                    label="Условия поставки"
                    value={settingsDraft.delivery_terms}
                    onChange={(value) =>
                      setSettingsDraft((current) => (current ? { ...current, delivery_terms: value } : current))
                    }
                  />
                </div>
                <label className="block rounded-control border border-line bg-surface-2 px-4 py-3">
                  <span className="ui-eyebrow">Операционная заметка</span>
                  <textarea
                    value={settingsDraft.notes_internal}
                    onChange={(event) =>
                      setSettingsDraft((current) =>
                        current ? { ...current, notes_internal: event.target.value } : current,
                      )
                    }
                    className="mt-2 h-28 w-full resize-none border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
                  />
                </label>
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    loading={savingSettings}
                    onClick={() => void handleSaveSettings()}
                    disabled={savingSettings}
                  >
                    Сохранить настройки
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-control border border-line bg-surface-2 p-4">
                  <div className="mb-3 text-sm font-bold text-ink-primary">Ручной рейтинг</div>
                  <div className="grid gap-3">
                    <EditableField label="Значение" value={ratingDraft} type="number" onChange={setRatingDraft} />
                    <label className="block rounded-control border border-line bg-surface-1 px-4 py-3">
                      <span className="ui-eyebrow">Причина изменения</span>
                      <textarea
                        value={ratingReason}
                        onChange={(event) => setRatingReason(event.target.value)}
                        placeholder="Например: задержки поставок"
                        className="mt-2 h-24 w-full resize-none border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
                      />
                    </label>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <DetailRow label="Авторейтинг" value={supplier.rating_auto.toFixed(2)} />
                      <DetailRow
                        label="Текущий ручной"
                        value={supplier.rating_manual ? supplier.rating_manual.toFixed(1) : '—'}
                      />
                    </div>
                    <Button
                      variant="secondary"
                      loading={savingRating}
                      disabled={savingRating}
                      onClick={() => void handleSaveRating()}
                    >
                      Обновить рейтинг
                    </Button>
                  </div>
                </div>

                <div className="rounded-control border border-line bg-surface-2 px-4 py-3 text-sm text-ink-secondary">
                  Для изменения имени, контактов и базового профиля используйте кнопку{' '}
                  <strong className="text-ink-primary">Редактировать</strong> в шапке карточки.
                </div>
              </div>
            </div>
          </Panel>
        )}
      </div>

      <ConfirmModal
        isOpen={confirmArchive}
        title={`Архивировать «${supplier.name}»?`}
        description="Карточка скроется из активного каталога. Данные и таблицы сохранятся."
        variant="danger"
        confirmLabel="Архивировать"
        cancelLabel="Отмена"
        onConfirm={() => {
          void handleArchiveSupplier();
        }}
        onCancel={() => setConfirmArchive(false)}
      />
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel-card-tight p-5 md:p-6">
      <h3 className="mb-4 text-sm font-bold tracking-tight text-ink-primary md:text-base">{title}</h3>
      {children}
    </section>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control border border-white/10 bg-white/5 p-4 transition-all duration-[var(--transition-base)] hover:border-white/20 hover:bg-white/10">
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/55">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-white">{value}</div>
    </div>
  );
}

function DetailRow({
  label,
  value,
  isLink,
  linkType,
}: {
  label: string;
  value: string;
  isLink?: boolean;
  linkType?: 'tel' | 'mailto';
}) {
  return (
    <div className="rounded-control border border-line bg-surface-2 px-4 py-3 transition-shadow hover:shadow-ds-sm">
      <div className="ui-eyebrow">{label}</div>
      {isLink && value !== '—' ? (
        <a
          href={`${linkType}:${value}`}
          className="mt-1 block text-sm font-semibold text-accent-primary hover:underline"
        >
          {value}
        </a>
      ) : (
        <div className="mt-1 text-sm font-semibold text-ink-secondary">{value}</div>
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
    <label className="block rounded-control border border-line bg-surface-2 px-4 py-3">
      <span className="ui-eyebrow">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
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
    <label className="block rounded-control border border-line bg-surface-2 px-4 py-3">
      <span className="ui-eyebrow">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border-none bg-transparent text-sm font-semibold text-ink-primary outline-none"
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
  return (
    <div className={`rounded-control border px-4 py-3 text-sm font-semibold ${tones[tone]}`}>
      {text}
    </div>
  );
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
  return 'bg-surface-5';
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
    slate: 'border-line bg-surface-2 text-ink-secondary',
  };
  return (
    <div className={`rounded-control border px-4 py-3 ${tones[tone]}`}>
      <div className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

function RowHealthBadge({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-bold text-emerald-700">OK</span>;
  }
  return (
    <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-700">
      {warnings.length} {warnings.length === 1 ? 'замечание' : 'замечания'}
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
