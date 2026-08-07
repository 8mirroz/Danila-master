import React, { useState } from 'react';
import { apiFetch } from '../lib/api';
import { notify } from '../lib/notify';
import { ModalShell, Button, Input } from './Primitives';

interface BatchSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (createdRequest: any) => void;
}

export const BatchSearchModal: React.FC<BatchSearchModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [articlesText, setArticlesText] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [vehicleVin, setVehicleVin] = useState('');
  const [priority, setPriority] = useState('normal');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const articles = articlesText
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (articles.length === 0) {
      notify.error('Укажите хотя бы один артикул OEM для поиска');
      return;
    }

    setLoading(true);
    try {
      const partsJson = JSON.stringify(
        articles.map((art) => ({
          name: `Деталь OEM ${art}`,
          oem: art,
          quantity: 1,
        }))
      );

      const res = await apiFetch('/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'batch_oem_search',
          text: `Массовый поиск по ${articles.length} артикулам: ${articles.join(', ')}`,
          customer_name: customerName || 'Частный клиент',
          vehicle_vin: vehicleVin || undefined,
          priority: priority,
          parts_json: partsJson,
        }),
      });

      if (res.ok) {
        const createdReq = await res.json();
        notify.success(`Запрос ${createdReq.request_id || 'создан'} — быстрый поиск запущен`);
        onSuccess(createdReq);
        onClose();
      } else {
        const err = await res.json().catch(() => null);
        notify.error(`Ошибка отправки: ${err?.detail || 'неизвестная ошибка'}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка соединения с бэкендом';
      notify.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ModalShell
      open={isOpen}
      onClose={onClose}
      title="Быстрый поиск по артикулу"
      subtitle="Введите артикулы OEM списком для мгновенного поиска и автоматического подбора цен"
      widthClass="max-w-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Клиент / Организация"
            type="text"
            placeholder="например, ИП Иванов или Название автосервиса"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
          />
          <Input
            label="VIN / Марка автомобиля"
            type="text"
            placeholder="например, WBA3A51080F123456"
            value={vehicleVin}
            onChange={(e) => setVehicleVin(e.target.value)}
          />
        </div>

        <div>
          <div className="flex justify-between items-center mb-1">
            <label className="block text-[10px] text-ink-muted font-bold uppercase tracking-wider">
              Список артикулов (OEM) — по одному на строку
            </label>
            <span className="text-[10px] font-mono text-accent-primary font-bold">
              {articlesText.split('\n').filter((s) => s.trim().length > 0).length} шт.
            </span>
          </div>
          <textarea
            value={articlesText}
            onChange={(e) => setArticlesText(e.target.value)}
            rows={5}
            required
            placeholder={'34116858047\n11427953129\n31126855743'}
            className="w-full rounded-control border border-line bg-surface-1 p-3 text-xs text-ink-primary font-mono placeholder-ink-muted outline-none focus:border-accent-primary leading-relaxed"
          />
        </div>

        <div className="flex items-center justify-between pt-2">
          <div>
            <label className="block text-[10px] text-ink-muted font-bold uppercase tracking-wider mb-1">
              Приоритет
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="rounded-control border border-line bg-surface-1 px-3 py-1.5 text-xs text-ink-primary outline-none focus:border-accent-primary font-sans"
            >
              <option value="normal">Обычный</option>
              <option value="urgent">Срочно</option>
              <option value="vip">VIP Клиент</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" variant="primary" icon="paper-plane" loading={loading}>
              Запустить поиск OEM
            </Button>
          </div>
        </div>
      </form>
    </ModalShell>
  );
};
