import React from 'react';

interface AnalyticsGridProps {
  queueLength: number;
  urgentCount: number;
  blockedCount: number;
  approvalCount: number;
  matchingCount: number;
  invoiceReadyCount: number;
}

const TrendBar: React.FC<{ label: string; value: number; tone: string; note: string }> = ({ label, value, tone, note }) => (
  <div className="rounded-[18px] border border-line bg-surface-1 p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">{label}</div>
        <div className="mt-1 text-2xl font-bold tracking-tight text-ink-primary">{value}</div>
      </div>
      <span className={`h-9 w-9 rounded-full border ${tone} flex items-center justify-center text-[11px] font-bold`}>{value}</span>
    </div>
    <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-3">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(100, Math.max(12, value * 12))}%` }} />
    </div>
    <div className="mt-2 text-[11px] text-ink-secondary">{note}</div>
  </div>
);

export const AnalyticsGrid: React.FC<AnalyticsGridProps> = ({
  queueLength,
  urgentCount,
  blockedCount,
  approvalCount,
  matchingCount,
  invoiceReadyCount,
}) => {
  const totalAttention = queueLength + blockedCount + approvalCount + matchingCount;
  const pressureLabel = queueLength === 0 ? 'Очередь пуста' : totalAttention > 25 ? 'Высокое давление' : 'Стабильный поток';

  return (
    <div className="space-y-4">
      <div className="grid gap-3 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-[22px] border border-line bg-surface-2 p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Queue pressure</div>
              <div className="mt-1 text-xl font-semibold text-ink-primary">{pressureLabel}</div>
            </div>
            <div className="rounded-full border border-line bg-surface-1 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-ink-secondary">
              {queueLength} active
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[16px] border border-line bg-surface-1 p-4 shadow-sm">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Urgent</div>
              <div className="mt-1 text-2xl font-bold tracking-tight text-ink-primary">{urgentCount}</div>
              <div className="mt-1 text-[11px] text-ink-secondary">требуют первоочередной реакции</div>
            </div>
            <div className="rounded-[16px] border border-line bg-surface-1 p-4 shadow-sm">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Blocked</div>
              <div className="mt-1 text-2xl font-bold tracking-tight text-ink-primary">{blockedCount}</div>
              <div className="mt-1 text-[11px] text-ink-secondary">уточнение или ручной разбор</div>
            </div>
            <div className="rounded-[16px] border border-line bg-surface-1 p-4 shadow-sm">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Approval</div>
              <div className="mt-1 text-2xl font-bold tracking-tight text-ink-primary">{approvalCount}</div>
              <div className="mt-1 text-[11px] text-ink-secondary">ожидают подтверждения цены</div>
            </div>
            <div className="rounded-[16px] border border-line bg-surface-1 p-4 shadow-sm">
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Invoice ready</div>
              <div className="mt-1 text-2xl font-bold tracking-tight text-ink-primary">{invoiceReadyCount}</div>
              <div className="mt-1 text-[11px] text-ink-secondary">готово к ERP-черновику</div>
            </div>
          </div>
        </div>

        <div className="rounded-[22px] border border-line bg-surface-1 p-5 shadow-sm">
          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">Decision loop</div>
          <div className="mt-2 text-xl font-semibold text-ink-primary">queue → inspect → compare → approve</div>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-secondary">
            Метрики здесь показывают не декоративный обзор, а плотность живой очереди, долю блокеров и сколько кейсов уже можно провести до ERP.
          </p>

          <div className="mt-4 grid gap-3">
            <TrendBar label="Matching" value={matchingCount} tone="bg-sky-500 text-white border-sky-500" note="детали в режиме сравнения офферов" />
            <TrendBar label="Attention" value={totalAttention} tone="bg-amber-500 text-white border-amber-500" note="общий объем активных решений" />
          </div>
        </div>
      </div>
    </div>
  );
};
