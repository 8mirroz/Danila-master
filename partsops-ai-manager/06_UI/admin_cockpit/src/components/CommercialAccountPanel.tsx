import { Button, Icon } from './Primitives';

type Subscription = {
  status: string;
  plan_code: string;
  position_limit: number;
  current_period_end?: string | null;
};

type Usage = {
  positions_used: number;
  positions_remaining: number;
  position_limit: number;
};

type Onboarding = {
  checklist_json?: string;
  completed_steps_json?: string;
};

export type CommercialAccountData = {
  organization: { display_name?: string; organization_id: string };
  subscription: Subscription;
  usage: Usage;
  onboarding: Onboarding;
  members?: Array<{ email: string; role: string; status: string }>;
  analytics?: { automation_rate: number; automated_positions: number; valid_positions: number; median_time_to_quote_minutes: number | null; margin_violations: number; pending_approvals: number };
};

interface CommercialAccountPanelProps {
  data: CommercialAccountData | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpenSuppliers: () => void;
  onCreateRequest: () => void;
}

const stepLabels: Record<string, string> = {
  import_supplier_feed: 'Импортировать прайс поставщика',
  configure_pricing_policy: 'Настроить margin policy',
  process_first_rfq: 'Обработать первую заявку',
  export_first_quote: 'Экспортировать первое КП',
};

function parseSteps(serialized?: string): string[] {
  try {
    const value = JSON.parse(serialized ?? '[]');
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function statusLabel(status: string): string {
  return ({ trial: 'Пробный период', active: 'Активна', past_due: 'Требует оплаты', suspended: 'Приостановлена', canceled: 'Отменена' } as Record<string, string>)[status] ?? status;
}

function formatTimeToQuote(minutes: number | null): string {
  if (minutes === null) return 'ещё нет';
  if (minutes < 60) return `${Math.round(minutes)} мин`;
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

export function CommercialAccountPanel({ data, loading, error, onRetry, onOpenSuppliers, onCreateRequest }: CommercialAccountPanelProps) {
  if (loading) {
    return <section aria-label="Коммерческий статус" className="panel-card p-5 animate-pulse"><div className="h-4 w-40 rounded bg-slate-200" /><div className="mt-4 h-16 rounded-[var(--radius-control)] bg-slate-100" /></section>;
  }

  if (error || !data) {
    return (
      <section aria-label="Коммерческий статус" className="rounded-[var(--radius-card)] border border-amber-200 bg-amber-50/70 p-5 text-sm text-amber-950">
        <div className="flex items-start justify-between gap-4">
          <div><p className="font-bold">Статус организации недоступен</p><p className="mt-1 text-xs text-amber-800">Основной workflow доступен, но тариф и onboarding не подтверждены.</p></div>
          <Button size="sm" variant="secondary" icon="rotate" onClick={onRetry}>Повторить</Button>
        </div>
      </section>
    );
  }

  const steps = parseSteps(data.onboarding.checklist_json);
  const completed = new Set(parseSteps(data.onboarding.completed_steps_json));
  const usedPercent = data.usage.position_limit > 0 ? Math.min(100, Math.round((data.usage.positions_used / data.usage.position_limit) * 100)) : 0;
  const periodEnd = data.subscription.current_period_end ? new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(new Date(data.subscription.current_period_end)) : null;

  return (
    <section aria-label="Организация и тариф" className="panel-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border-default)] px-5 py-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--text-muted)]">Организация</p>
          <h3 className="mt-1 text-sm font-bold text-[var(--text-primary)]">{data.organization.display_name || data.organization.organization_id}</h3>
        </div>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-800">{statusLabel(data.subscription.status)}</span>
      </div>
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div>
          <div className="flex items-baseline justify-between gap-3"><span className="text-xs font-semibold text-[var(--text-secondary)]">{data.subscription.plan_code === 'team' ? 'Team' : data.subscription.plan_code === 'start' ? 'Start' : 'Beta trial'}</span><span data-numeric className="font-mono text-xs font-bold text-[var(--text-primary)]">{data.usage.positions_used} / {data.usage.position_limit}</span></div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-3)]"><div className="h-full rounded-full bg-[var(--accent-primary)] transition-[width] duration-300" style={{ width: `${usedPercent}%` }} /></div>
          <p className="mt-2 text-[11px] text-[var(--text-secondary)]">Осталось {data.usage.positions_remaining} позиций{periodEnd ? ` до ${periodEnd}` : ''}.</p>
        </div>
        <div>
          <div className="flex items-center justify-between gap-3"><p className="text-xs font-semibold text-[var(--text-secondary)]">Первый полезный результат</p><span className="font-mono text-[10px] text-[var(--text-muted)]">{completed.size}/{steps.length}</span></div>
          <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {steps.map((step) => (
              <div key={step} className={`flex items-center gap-2 text-[11px] ${completed.has(step) ? 'text-emerald-700' : 'text-[var(--text-secondary)]'}`}>
                <Icon name={completed.has(step) ? 'circle-check' : 'list'} size={13} />
                <span>{stepLabels[step] ?? step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      {data.analytics && <div className="mx-5 mb-5 grid gap-3 rounded-[var(--radius-control)] border border-emerald-100 bg-emerald-50/60 px-4 py-3 sm:grid-cols-2 lg:grid-cols-4"><div><div className="flex items-baseline justify-between gap-3"><span className="text-xs font-semibold text-emerald-900">Automation Rate</span><strong data-numeric className="font-mono text-lg text-emerald-800">{data.analytics.automation_rate}%</strong></div><p className="mt-1 text-[11px] text-emerald-800">{data.analytics.automated_positions} из {data.analytics.valid_positions} позиций без ручной коррекции.</p></div><p className="text-xs text-sky-900">Медиана подготовки КП: <strong data-numeric>{formatTimeToQuote(data.analytics.median_time_to_quote_minutes)}</strong></p><p className="text-xs text-amber-900">Margin violations: <strong data-numeric>{data.analytics.margin_violations}</strong></p><p className="text-xs text-blue-900">Ожидают согласования: <strong data-numeric>{data.analytics.pending_approvals}</strong></p></div>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-default)] px-5 py-3"><span className="text-[11px] text-[var(--text-secondary)]">Команда: <strong data-numeric>{data.members?.length ?? 0}</strong></span><div className="flex gap-2"><Button size="sm" variant="secondary" icon="car" onClick={onOpenSuppliers}>Поставщики</Button><Button size="sm" variant="primary" icon="plus" onClick={onCreateRequest}>Новая заявка</Button></div></div>
    </section>
  );
}
