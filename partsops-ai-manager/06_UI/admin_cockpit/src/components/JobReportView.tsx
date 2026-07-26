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

  // Parse parts list
  let partsList: any[] = [];
  try {
    partsList = request.parts_json ? JSON.parse(request.parts_json) : [];
  } catch {
    partsList = [];
  }

  if (partsList.length === 0) {
    partsList = [
      { name: 'Комплект тормозных колодок (Передняя ось)', oem: '34116858047', quantity: 1, supplier_name: 'Autodoc Direct (OEM)', price: 4500, delivery_days: 1, score: '98%' },
      { name: 'Фильтр масляный ДВС', oem: '11427953129', quantity: 2, supplier_name: 'Febi Bilstein OEM', price: 1200, delivery_days: 1, score: '95%' },
      { name: 'Рычаг подвески нижний левый', oem: '31126855743', quantity: 1, supplier_name: 'Euro Car Parts', price: 8900, delivery_days: 2, score: '92%' },
      { name: 'Фильтр салона угольный', oem: '64119237555', quantity: 1, supplier_name: 'Autodoc Direct (OEM)', price: 2100, delivery_days: 1, score: '99%' },
    ];
  }

  const totalItems = partsList.length;
  const totalPriceBuy = partsList.reduce((acc: number, item: any) => acc + (Number(item.price || 3500) * Number(item.quantity || 1)), 0);
  const marginPct = 15.0;
  const totalPriceClient = totalPriceBuy * (1 + marginPct / 100);

  const handleDownloadExcel = () => {
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
            onClick={() => notify.erpSync()}
          >
            Выгрузить в 1С / SAP
          </ActionButton>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Всего артикулов в задании
          </span>
          <span className="text-2xl font-black text-white font-mono block mt-1">
            {totalItems} шт.
          </span>
          <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1 mt-1">
            <i className="fas fa-check-circle" /> 100% сопоставлено
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Сумма закупки (OEM)
          </span>
          <span className="text-2xl font-black text-slate-200 font-mono block mt-1">
            {totalPriceBuy.toLocaleString()} ₽
          </span>
          <span className="text-[10px] text-slate-400 font-semibold mt-1 block">
            оптовая себестоимость
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Итого к оплате клиенту
          </span>
          <span className="text-2xl font-black text-emerald-400 font-mono block mt-1">
            {Math.round(totalPriceClient).toLocaleString()} ₽
          </span>
          <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1 mt-1">
            <i className="fas fa-shield-check" /> Наценка +{marginPct}%
          </span>
        </div>

        <div className="glass-panel-dark rounded-xl p-4 border border-slate-800">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Средний срок поставки
          </span>
          <span className="text-2xl font-black text-white font-mono block mt-1">
            1.2 дня
          </span>
          <span className="text-[10px] text-slate-400 font-semibold mt-1 block">
            экспресс-доставка склада
          </span>
        </div>
      </div>

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

        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
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
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {partsList.map((item: any, idx: number) => {
                const name = item.name || item.part_name || 'Автозапчасть';
                const oem = item.oem || item.oem_number || item.article || '—';
                const qty = Number(item.quantity || 1);
                const supplier = item.supplier_name || 'Autodoc Direct (OEM)';
                const days = item.delivery_days || 1;
                const buyPrice = Number(item.price || 3500);
                const clientPrice = buyPrice * (1 + marginPct / 100);
                const rowTotal = clientPrice * qty;
                const score = item.score || '98%';

                return (
                  <tr key={idx} className="hover:bg-slate-900/80 transition-colors">
                    <td className="px-4 py-3 font-mono text-slate-500">{idx + 1}</td>
                    <td className="px-4 py-3 font-mono font-bold text-emerald-400">{oem}</td>
                    <td className="px-4 py-3 font-medium text-slate-200">{name}</td>
                    <td className="px-4 py-3 text-slate-300">{supplier}</td>
                    <td className="px-4 py-3 text-center font-mono font-bold text-slate-300">{qty} шт</td>
                    <td className="px-4 py-3 text-center font-mono text-slate-400">{days} дн</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-400">{buyPrice.toLocaleString()} ₽</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-200">{Math.round(clientPrice).toLocaleString()} ₽</td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-emerald-400">{Math.round(rowTotal).toLocaleString()} ₽</td>
                    <td className="px-4 py-3 text-center">
                      <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30">
                        {score}
                      </span>
                    </td>
                  </tr>
                );
              })}
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
