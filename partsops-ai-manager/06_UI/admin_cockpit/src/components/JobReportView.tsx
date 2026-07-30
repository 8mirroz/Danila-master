import React from 'react';
import { StatusBadge, ActionButton } from './Primitives';
import { notify } from '../lib/notify';
import { AnalogComparisonMatrix } from './AnalogComparisonMatrix';

type RequestData = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  created_at: string;
  parts_json: string;
  vehicle_make?: string;
  vehicle_model?: string;
  vehicle_vin_masked?: string;
  priority?: string;
};

interface JobReportViewProps {
  request: RequestData | null;
  onBack: () => void;
}

export const JobReportView: React.FC<JobReportViewProps> = ({ request, onBack }) => {
  if (!request) {
    return (
      <div className="glass-panel-dark rounded-2xl p-8 text-center text-slate-400 space-y-4">
        <i className="fas fa-file-invoice text-3xl text-slate-600" />
        <p className="text-xs">Запрос для формирования отчёта не выбран</p>
        <ActionButton onClick={onBack}>Вернуться в панель управления</ActionButton>
      </div>
    );
  }

  // Parse parts list — never inject demo catalog when empty
  let partsList: any[] = [];
  try {
    partsList = request.parts_json ? JSON.parse(request.parts_json) : [];
  } catch {
    partsList = [];
  }
  if (!Array.isArray(partsList)) {
    partsList = [];
  }

  const totalItems = partsList.length;
  // Use real line prices when present; do not invent default 3500 / 15% margin
  const totalPriceBuy = partsList.reduce((acc: number, item: any) => {
    const unit = Number(item.price ?? item.sale_price ?? item.purchase_price);
    if (!Number.isFinite(unit)) return acc;
    return acc + unit * Number(item.quantity || 1);
  }, 0);
  const pricedCount = partsList.filter(
    (item: any) => Number.isFinite(Number(item.price ?? item.sale_price ?? item.purchase_price)),
  ).length;
  const hasPricedLines = pricedCount > 0;
  const marginPctRaw = partsList
    .map((item: any) => Number(item.margin ?? item.margin_pct))
    .filter((n: number) => Number.isFinite(n));
  const marginPct =
    marginPctRaw.length > 0
      ? marginPctRaw.reduce((a: number, b: number) => a + b, 0) / marginPctRaw.length
      : null;
  const marginFactor = marginPct == null ? 0 : marginPct > 1 ? marginPct / 100 : marginPct;
  const totalPriceClient =
    hasPricedLines
      ? totalPriceBuy * (1 + marginFactor)
      : null;

  const handleDownloadExcel = () => {
    if (!partsList.length) {
      notify.error('Экспорт заблокирован: в заявке нет подтверждённых позиций');
      return;
    }
    const downloadUrl = `/api/requests/${request.request_id}/export-excel`;
    const anchor = document.createElement('a');
    anchor.href = downloadUrl;
    anchor.download = `partsops_report_${request.request_id}.xlsx`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    notify.success(`Загрузка Excel файла partsops_report_${request.request_id}.xlsx запущена`);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header Bar */}
      <div className="glass-panel-dark rounded-2xl p-5 border border-slate-800 shadow-2xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <button
              onClick={onBack}
              className="text-slate-400 hover:text-white text-xs flex items-center gap-1 font-semibold transition-colors mr-2"
            >
              <i className="fas fa-arrow-left text-[10px]" />
              <span>Назад</span>
            </button>
            <span className="font-mono text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
              {request.request_id}
            </span>
            <StatusBadge status={request.status} />
          </div>
          <h2 className="text-xl font-extrabold text-white tracking-tight mt-2">
            Итоговый Отчёт по Заданию и Смета Спецификации
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Заказчик: <strong className="text-slate-200">{request.customer_name || 'Не указан'}</strong> | Автомобиль: <strong className="text-slate-200">{request.vehicle_make || 'Уточняется'} {request.vehicle_model || ''}</strong>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleDownloadExcel}
            className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-2"
          >
            <i className="fas fa-file-excel text-sm" />
            <span>Скачать Отчёт Excel (.xlsx)</span>
          </button>
          <ActionButton
            variant="secondary"
            icon="fa-rotate"
            onClick={() => {
              void notify.erpSync();
            }}
            title="Проверить статус ERP (full push 1С/SAP не one-click)"
          >
            Статус ERP
          </ActionButton>
        </div>
      </div>

      {/* Summary KPI Strip — live fields only, no decorative fake % / delivery */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Всего артикулов в задании
          </span>
          <span className="text-2xl font-black text-white font-mono block mt-1">
            {totalItems} шт.
          </span>
          <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1 mt-1">
            {totalItems === 0
              ? 'позиций нет в request.parts_json'
              : `${pricedCount}/${totalItems} с ценой`}
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Сумма закупки (OEM)
          </span>
          <span className="text-2xl font-black text-slate-200 font-mono block mt-1">
            {hasPricedLines ? `${totalPriceBuy.toLocaleString()} ₽` : 'н/д'}
          </span>
          <span className="text-[10px] text-slate-400 font-semibold mt-1 block">
            {hasPricedLines ? 'по строкам с price/sale_price' : 'цены в parts_json отсутствуют'}
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Итого к оплате клиенту
          </span>
          <span className="text-2xl font-black text-emerald-400 font-mono block mt-1">
            {totalPriceClient != null ? `${Math.round(totalPriceClient).toLocaleString()} ₽` : 'н/д'}
          </span>
          <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1 mt-1">
            {marginPct != null
              ? `Наценка из данных: ${marginPct > 1 ? marginPct.toFixed(1) : (marginPct * 100).toFixed(1)}%`
              : 'маржа не задана в parts_json'}
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Средний срок поставки
          </span>
          <span className="text-2xl font-black text-white font-mono block mt-1">
            {(() => {
              const days = partsList
                .map((item: any) => Number(item.delivery_days))
                .filter((n: number) => Number.isFinite(n));
              if (days.length === 0) return 'н/д';
              const avg = days.reduce((a: number, b: number) => a + b, 0) / days.length;
              return `${avg.toFixed(1)} дн.`;
            })()}
          </span>
          <span className="text-[10px] text-slate-400 font-semibold mt-1 block">
            из delivery_days в позициях
          </span>
        </div>
      </div>

      {totalItems === 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
          Спецификация пуста — demo-позиции не подставляются. Выберите запрос с parts_json или завершите matching.
        </div>
      )}

      {/* Specification Table */}
      <div className="glass-panel-dark rounded-2xl p-5 border border-slate-800 space-y-4">
        <div className="flex justify-between items-center border-b border-slate-800 pb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <i className="fas fa-table-list text-emerald-400" />
            <span>Детализированная спецификация деталей</span>
          </h3>
          <span className="text-[10px] text-slate-400 font-mono">
            Экспорт положен в шаблон `.xlsx` (openpyxl)
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-[var(--border-default)] bg-[var(--surface-1)]">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--border-default)] bg-[var(--surface-2)] text-[var(--text-muted)] font-semibold uppercase text-[10px] tracking-wider">
                <th className="px-4 py-3">№</th>
                <th className="px-4 py-3">Артикул OEM</th>
                <th className="px-4 py-3">Наименование</th>
                <th className="px-4 py-3">Поставщик</th>
                <th className="px-4 py-3 text-center">Кол-во</th>
                <th className="px-4 py-3 text-center">Срок</th>
                <th className="px-4 py-3 text-right">Закупка</th>
                <th className="px-4 py-3 text-right">Цена клиенту</th>
                <th className="px-4 py-3 text-right">Итого</th>
                <th className="px-4 py-3 text-center">Match</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-default)] font-sans">
              {partsList.length ? partsList.map((item: any, idx: number) => {
                const name = item.name || item.part_name || '';
                const oem = item.oem || item.oem_number || item.article || '';
                const qty = Number(item.quantity || 0);
                const supplier = item.supplier_name || '';
                const days = item.delivery_days;
                const buyPrice = Number(item.price ?? item.purchase_price);
                const hasBuyPrice = Number.isFinite(buyPrice);
                const clientPrice = Number(item.client_price ?? (hasBuyPrice ? buyPrice * (1 + marginFactor) : NaN));
                const rowTotal = Number(item.line_total ?? (Number.isFinite(clientPrice) ? clientPrice * qty : NaN));
                const score = item.score ?? item.match_score;

                return (
                  <tr key={idx} className="transition-colors hover:bg-[var(--state-hover)]">
                    <td className="px-4 py-3 font-mono text-slate-500">{idx + 1}</td>
                    <td className="px-4 py-3 font-mono font-bold text-emerald-700">{oem}</td>
                    <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{name}</td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{supplier}</td>
                    <td className="px-4 py-3 text-center font-mono font-bold text-[var(--text-secondary)]">{qty ? `${qty} шт` : '—'}</td>
                    <td className="px-4 py-3 text-center font-mono text-slate-400">{days ? `${days} дн` : '—'}</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-400">{hasBuyPrice ? `${buyPrice.toLocaleString()} ₽` : '—'}</td>
                    <td className="px-4 py-3 text-right font-mono text-[var(--text-primary)]">{Number.isFinite(clientPrice) ? `${Math.round(clientPrice).toLocaleString()} ₽` : '—'}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">{Number.isFinite(rowTotal) ? `${Math.round(rowTotal).toLocaleString()} ₽` : '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30">
                        {score ?? 'нет evidence'}
                      </span>
                    </td>
                  </tr>
                );
              }) : (
                <tr><td colSpan={10} className="px-4 py-10 text-center text-slate-500">Нет подтверждённых позиций — данные не подставляются.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Smart Analog Resolver Component */}
        <AnalogComparisonMatrix requestId={request.request_id} />

        {/* Excel Download CTA footer */}
        <div className="flex justify-between items-center pt-3 border-t border-slate-800 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <i className="fas fa-file-excel text-emerald-400 text-base" />
            <span>Готов к загрузке документ <strong>partsops_report_{request.request_id}.xlsx</strong></span>
          </div>

          <button
            onClick={handleDownloadExcel}
            className="px-4 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 font-bold text-xs transition-all flex items-center gap-2"
          >
            <i className="fas fa-download" />
            <span>Скачать `.xlsx`</span>
          </button>
        </div>
      </div>
    </div>
  );
};
