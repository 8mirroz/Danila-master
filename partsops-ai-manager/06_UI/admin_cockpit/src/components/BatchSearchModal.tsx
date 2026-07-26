import React, { useState } from 'react';
import { useFocusTrap, useKeydown } from '../lib/focus';
import { apiFetch } from '../lib/api';
import { notify } from '../lib/notify';

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
  const [articlesText, setArticlesText] = useState(
    "34116858047\n11427953129\n31126855743\n64119237555"
  );
  const [customerName, setCustomerName] = useState("ООО АвтоТехСнаб");
  const [vehicleVin, setVehicleVin] = useState("WBA3A51080F123456");
  const [priority, setPriority] = useState("urgent");
  const [loading, setLoading] = useState(false);

  const modalRef = React.useRef<HTMLDivElement>(null);
  useFocusTrap(modalRef, isOpen);
  useKeydown('Escape', onClose, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const articles = articlesText
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (articles.length === 0) {
      notify.error("Укажите хотя бы один артикул OEM для поиска");
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
          customer_name: customerName,
          vehicle_vin: vehicleVin,
          priority: priority,
          parts_json: partsJson,
        }),
      });

      if (res.ok) {
        const createdReq = await res.json();
        notify.success(`Запрос ${createdReq.request_id || 'создан'} — пакетный поиск запущен`);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-fadeIn">
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="batch-modal-title"
        className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 text-slate-100 p-6 shadow-2xl space-y-5 animate-scaleUp"
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <i className="fas fa-[#10b981] fa-list-check text-sm" />
            </span>
            <div>
              <h3 id="batch-modal-title" className="text-sm font-bold text-white">
                Пакетный поиск по списку артикулов OEM
              </h3>
              <p className="text-[11px] text-slate-400">
                Введите артикулы списком для автоматического поиска и подбора цен
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm transition-colors p-1"
          >
            <i className="fas fa-times" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                Клиент / Организация
              </label>
              <input
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                required
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-emerald-400"
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                VIN / Марка автомобиля
              </label>
              <input
                type="text"
                value={vehicleVin}
                onChange={(e) => setVehicleVin(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-emerald-400 font-mono"
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                Список артикулов (OEM) — по одному на строку
              </label>
              <span className="text-[10px] font-mono text-emerald-400">
                {articlesText.split('\n').filter((s) => s.trim().length > 0).length} шт.
              </span>
            </div>
            <textarea
              value={articlesText}
              onChange={(e) => setArticlesText(e.target.value)}
              rows={5}
              required
              placeholder="34116858047&#10;11427953129&#10;31126855743"
              className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-white font-mono placeholder-slate-600 outline-none focus:border-emerald-400 leading-relaxed"
            />
          </div>

          <div className="flex items-center justify-between pt-2">
            <div>
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                Приоритет
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-white outline-none focus:border-emerald-400"
              >
                <option value="normal">Обычный</option>
                <option value="urgent">Срочно</option>
                <option value="vip">VIP Клиент</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white rounded-xl border border-slate-800 hover:bg-slate-800 transition-colors"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 text-xs font-bold text-white rounded-xl bg-emerald-500 hover:bg-emerald-600 shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-1.5"
              >
                {loading ? (
                  <>
                    <i className="fas fa-circle-notch fa-spin text-xs" />
                    <span>Поиск и ИИ подбор...</span>
                  </>
                ) : (
                  <>
                    <i className="fas fa-bolt text-xs" />
                    <span>Запустить Поиск и ИИ Подбор</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
