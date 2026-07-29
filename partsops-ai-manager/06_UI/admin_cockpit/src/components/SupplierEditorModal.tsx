import React, { useEffect, useState } from 'react';
import { ModalShell, Icon } from './Primitives';
import { ApiError, apiJson } from '../lib/api';
import type { SupplierRecord } from './supplierTypes';

interface SupplierEditorModalProps {
  open: boolean;
  onClose: () => void;
  supplier?: SupplierRecord | null;
  onSaved: (supplier: SupplierRecord) => void;
}

type DraftState = {
  supplier_id?: string;
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  city: string;
  specialization: string;
  reliability_score: number;
  avg_delivery_days: number;
  status: string;
  rating_manual: number | null;
  account_owner: string;
  payment_terms: string;
  delivery_terms: string;
  currency_default: string;
  last_sync_status: string;
  notes_internal: string;
};

const DEFAULT_DRAFT: DraftState = {
  name: '',
  contact_person: '',
  phone: '',
  email: '',
  city: '',
  specialization: '',
  reliability_score: 0.9,
  avg_delivery_days: 2,
  status: 'active',
  rating_manual: 4.5,
  account_owner: 'Ops Team',
  payment_terms: 'Net 30',
  delivery_terms: 'EXW',
  currency_default: 'RUB',
  last_sync_status: 'synced',
  notes_internal: '',
};

export const SupplierEditorModal: React.FC<SupplierEditorModalProps> = ({
  open,
  onClose,
  supplier,
  onSaved,
}) => {
  const [draft, setDraft] = useState<DraftState>(DEFAULT_DRAFT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (supplier) {
      setDraft({
        supplier_id: supplier.supplier_id,
        name: supplier.name,
        contact_person: supplier.contact_person || '',
        phone: supplier.phone || '',
        email: supplier.email || '',
        city: supplier.city || '',
        specialization: supplier.specialization || '',
        reliability_score: supplier.reliability_score ?? 0.9,
        avg_delivery_days: supplier.avg_delivery_days ?? 2,
        status: supplier.status || 'active',
        rating_manual: supplier.rating_manual ?? 4.5,
        account_owner: supplier.account_owner || 'Ops Team',
        payment_terms: supplier.payment_terms || 'Net 30',
        delivery_terms: supplier.delivery_terms || 'EXW',
        currency_default: supplier.currency_default || 'RUB',
        last_sync_status: supplier.last_sync_status || 'synced',
        notes_internal: supplier.notes_internal || '',
      });
    } else {
      setDraft(DEFAULT_DRAFT);
    }
    setError(null);
  }, [supplier, open]);

  const handleSubmit = async () => {
    if (!draft.name.trim()) {
      setError('Укажите название поставщика.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const isPatch = Boolean(draft.supplier_id);
      const path = isPatch ? `/api/suppliers/${draft.supplier_id}` : '/api/suppliers';
      const method = isPatch ? 'PATCH' : 'POST';
      const savedData = await apiJson<SupplierRecord>(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      onSaved(savedData);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось сохранить карточку поставщика');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalShell
      open={open}
      onClose={onClose}
      title={supplier ? 'Редактирование карточки поставщика' : 'Новая карточка поставщика'}
      subtitle="Укажите контакты, параметры договора и SLA поставщика"
      widthClass="max-w-3xl"
      footer={
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-2xl border border-slate-200 bg-white px-5 py-2.5 text-xs font-bold text-slate-700 transition hover:bg-slate-50"
          >
            Отмена
          </button>
          <button
            onClick={() => void handleSubmit()}
            disabled={saving || !draft.name.trim()}
            className="rounded-2xl bg-[var(--accent-primary)] px-6 py-2.5 text-xs font-bold text-white transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 flex items-center gap-2 shadow-sm"
          >
            {saving && <Icon name="spinner" size={14} className="animate-spin" />}
            {saving ? 'Сохранение...' : 'Сохранить карточку'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3 text-xs font-semibold text-rose-700">
            {error}
          </div>
        )}

        <div className="grid gap-4.5 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Название компании *
            </label>
            <input
              value={draft.name}
              onChange={(e) => setDraft((c) => ({ ...c, name: e.target.value }))}
              placeholder="например: ООО «АвтоАльянс»"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Контактное лицо
            </label>
            <input
              value={draft.contact_person}
              onChange={(e) => setDraft((c) => ({ ...c, contact_person: e.target.value }))}
              placeholder="Иванов Алексей"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Телефон
            </label>
            <input
              value={draft.phone}
              onChange={(e) => setDraft((c) => ({ ...c, phone: e.target.value }))}
              placeholder="+7-495-123-4567"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Email
            </label>
            <input
              value={draft.email}
              onChange={(e) => setDraft((c) => ({ ...c, email: e.target.value }))}
              placeholder="sales@autoalliance.ru"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Город
            </label>
            <input
              value={draft.city}
              onChange={(e) => setDraft((c) => ({ ...c, city: e.target.value }))}
              placeholder="Москва"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Специализация / Бренды
            </label>
            <input
              value={draft.specialization}
              onChange={(e) => setDraft((c) => ({ ...c, specialization: e.target.value }))}
              placeholder="BMW, Audi, Mercedes, VAG"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Надежность (0.0 - 1.0)
            </label>
            <input
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={draft.reliability_score}
              onChange={(e) => setDraft((c) => ({ ...c, reliability_score: Number(e.target.value) || 0 }))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              SLA Доставки (дни)
            </label>
            <input
              type="number"
              min="1"
              value={draft.avg_delivery_days}
              onChange={(e) => setDraft((c) => ({ ...c, avg_delivery_days: Number(e.target.value) || 1 }))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            />
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Статус
            </label>
            <select
              value={draft.status}
              onChange={(e) => setDraft((c) => ({ ...c, status: e.target.value }))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            >
              <option value="active">Активен</option>
              <option value="pending">Ожидает</option>
              <option value="blocked">Заблокирован</option>
              <option value="archived">Архив</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Основная валюта
            </label>
            <select
              value={draft.currency_default}
              onChange={(e) => setDraft((c) => ({ ...c, currency_default: e.target.value }))}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
            >
              <option value="RUB">RUB (₽)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="CNY">CNY (¥)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
            Внутренние заметки
          </label>
          <textarea
            rows={3}
            value={draft.notes_internal}
            onChange={(e) => setDraft((c) => ({ ...c, notes_internal: e.target.value }))}
            placeholder="Внутренний комментарий по работе с поставщиком..."
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-800 outline-none focus:border-[var(--accent-primary)] focus:bg-white"
          />
        </div>
      </div>
    </ModalShell>
  );
};
