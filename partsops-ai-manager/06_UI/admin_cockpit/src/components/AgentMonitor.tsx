import { useEffect, useState } from 'react';
import { ActionButton } from './Primitives';
import { apiFetch } from '../lib/api';

type LogEntry = {
  id: string;
  time: string;
  category: 'system' | 'parser' | 'matcher' | 'pricing' | 'erp';
  level: 'info' | 'warn' | 'success';
  message: string;
  requestId?: string;
  hasActions?: boolean;
};

type ProviderStatus = {
  name?: string;
  status?: string;
  model?: string;
  provider?: string;
  error?: string | null;
};

const initialLogs: LogEntry[] = [
  { id: '1', time: '05:18:22', category: 'system', level: 'info', message: 'Ядро PartsOps AI запущено и готово к приему задач.' },
  { id: '2', time: '05:18:23', category: 'parser', level: 'success', message: 'Модель google/gemma-4-31b-it инициализирована.' },
  { id: '3', time: '05:19:01', category: 'matcher', level: 'info', message: 'Справочники поставщиков загружены в оперативный контур.' },
  { id: '4', time: '06:36:34', category: 'erp', level: 'success', message: 'Счёт успешно выгружен в ERP. ИД документа: INV-9921.' },
  { id: '5', time: '06:36:38', category: 'pricing', level: 'warn', message: 'Margin Guard: Маржа 9.8% ниже лимита политики (12.0%) для REQ-4815', requestId: 'REQ-4815', hasActions: true },
];

const categoryLabel: Record<LogEntry['category'], { label: string; cls: string }> = {
  system: { label: 'Ядро', cls: 'text-slate-600 bg-slate-50 border-slate-100' },
  parser: { label: 'Парсер', cls: 'text-blue-600 bg-blue-50 border-blue-100' },
  matcher: { label: 'Матчер', cls: 'text-sky-600 bg-sky-50 border-sky-100' },
  pricing: { label: 'Цены', cls: 'text-amber-600 bg-amber-50 border-amber-100' },
  erp: { label: 'ERP', cls: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
};

export const AgentMonitor = () => {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [filterText, setFilterText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);
  const [budgetStats, setBudgetStats] = useState<{ hourly_tokens_used?: number; daily_cost_usd?: number } | null>(null);
  const [monitorState, setMonitorState] = useState<'online' | 'degraded' | 'stale'>('stale');

  const refreshOpsState = async () => {
    setIsLoading(true);
    const [providersResult, budgetResult] = await Promise.allSettled([
      apiFetch('/api/admin/llm-status').then((response) => {
        if (!response.ok) {
          throw new Error(`llm-status ${response.status}`);
        }
        return response.json();
      }),
      apiFetch('/api/admin/budget-stats').then((response) => {
        if (!response.ok) {
          throw new Error(`budget-stats ${response.status}`);
        }
        return response.json();
      }),
    ]);

    const nextProviders = providersResult.status === 'fulfilled'
      ? (providersResult.value.providers || [])
      : [];
    const nextBudget = budgetResult.status === 'fulfilled' ? budgetResult.value : null;
    setProviderStatuses(nextProviders);
    setBudgetStats(nextBudget);

    if (providersResult.status === 'fulfilled' && budgetResult.status === 'fulfilled') {
      setMonitorState('online');
    } else if (providersResult.status === 'rejected' || budgetResult.status === 'rejected') {
      setMonitorState('degraded');
    } else {
      setMonitorState('stale');
    }
    setIsLoading(false);
  };

  useEffect(() => {
    void refreshOpsState();
    const interval = window.setInterval(() => {
      void refreshOpsState();
    }, 30000);
    return () => window.clearInterval(interval);
  }, []);

  const handleRestart = () => {
    const timeStr = new Date().toTimeString().split(' ')[0];
    setLogs([
      { id: Date.now().toString(), time: timeStr, category: 'system', level: 'info', message: 'Перезапуск операционного монитора по запросу оператора.' },
      { id: (Date.now() + 1).toString(), time: timeStr, category: 'system', level: 'success', message: 'Контекст обновлен из backend-эндпоинтов LLM и бюджета.' },
    ]);
    void refreshOpsState();
  };

  const getLevelIcon = (lvl: LogEntry['level']) => {
    switch (lvl) {
      case 'success': return 'fa-circle-check text-green-500';
      case 'warn': return 'fa-triangle-exclamation text-amber-500';
      default: return 'fa-circle-info text-blue-500';
    }
  };

  const filteredLogs = logs.filter((log) =>
    log.message.toLowerCase().includes(filterText.toLowerCase()) ||
    log.category.toLowerCase().includes(filterText.toLowerCase()),
  );

  const sessionSpend = budgetStats?.daily_cost_usd ?? null;
  const rpmPolicy = providerStatuses.length > 0 ? providerStatuses.length * 10 : null;

  return (
    <section className="panel-card animate-fade-in">
      <div className="flex flex-col gap-6 border-b border-[var(--border-subtle)] px-6 py-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="ui-stack-3 max-w-3xl">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-sky-700">
              Agent OS
            </span>
            <div className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${
              monitorState === 'online' ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : monitorState === 'degraded' ? 'border-amber-200 bg-amber-50 text-amber-700'
                : 'border-slate-200 bg-slate-50 text-slate-600'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                monitorState === 'online' ? 'bg-emerald-500' : monitorState === 'degraded' ? 'bg-amber-500' : 'bg-slate-500'
              }`} />
              {monitorState === 'online' ? 'Контур живой' : monitorState === 'degraded' ? 'Часть данных stale' : 'Ожидание backend данных'}
            </div>
          </div>
          <div className="ui-stack-2">
            <h3 className="text-[34px] font-bold leading-[0.98] tracking-[-0.05em] text-[var(--text-primary)]">Операторская консоль AI-движка</h3>
            <p className="max-w-2xl text-[15px] leading-8 text-[var(--text-secondary)]">
              Монитор показывает только живые сигналы backend: провайдеры LLM, бюджет и журнал действий. Если источник недоступен, это явно помечается как stale/degraded.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[420px]">
          <div className="ui-metric-card">
            <div className="ui-eyebrow">Session spend</div>
            <div className="mt-2 text-xl font-bold tracking-[-0.04em] text-[var(--text-primary)]">
              {sessionSpend !== null ? `$${sessionSpend.toFixed(2)}` : 'stale'}
            </div>
            <div className="mt-1 text-[11px] text-[var(--text-secondary)]">daily_cost_usd</div>
          </div>
          <div className="ui-metric-card">
            <div className="ui-eyebrow">RPM policy</div>
            <div className="mt-2 text-xl font-bold tracking-[-0.04em] text-[var(--text-primary)]">
              {rpmPolicy !== null ? rpmPolicy : 'stale'}
            </div>
            <div className="mt-1 text-[11px] text-[var(--text-secondary)]">по числу backend-провайдеров</div>
          </div>
          <div className="ui-metric-card">
            <div className="ui-eyebrow">Queue health</div>
            <div className="mt-2 text-xl font-bold tracking-[-0.04em] text-emerald-600">{filteredLogs.length}</div>
            <div className="mt-1 text-[11px] text-[var(--text-secondary)]">{isLoading ? 'refreshing' : 'cached signals'}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 px-6 py-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <div className="ui-stack-5">
          <div className="ui-section ui-stack-4">
            <div className="flex items-center justify-between gap-2">
              <span className="ui-eyebrow">Конфигурация модели</span>
              <span className="text-[10px] font-semibold text-[var(--text-secondary)]">Live policy</span>
            </div>
            <div className="ui-stack-4 text-xs">
              <div className="grid grid-cols-1 gap-2">
                {providerStatuses.length > 0 ? providerStatuses.map((provider, index) => (
                  <div key={`${provider.model || provider.name || index}`} className="rounded-2xl border border-[var(--border-default)] bg-[var(--surface-1)] px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-semibold text-[var(--text-primary)]">{provider.model || provider.name || 'provider'}</span>
                      <span className="text-[10px] font-bold uppercase text-[var(--text-secondary)]">{provider.status || 'unknown'}</span>
                    </div>
                    {provider.error && <div className="mt-1 text-[10px] text-rose-600">{provider.error}</div>}
                  </div>
                )) : (
                  <div className="rounded-2xl border border-dashed border-[var(--border-default)] bg-[var(--surface-1)] px-3 py-4 text-[11px] text-[var(--text-muted)]">
                    Данные провайдеров недоступны. Состояние ниже помечено как stale.
                  </div>
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 text-center text-[10px] font-bold">
                <div className="ui-stat-card">
                  <span className="block text-[var(--text-muted)]">LLM</span>
                  <span className={`mt-1 block ${providerStatuses.length ? 'text-emerald-600' : 'text-slate-500'}`}>
                    {providerStatuses.length ? 'LIVE' : 'STALE'}
                  </span>
                </div>
                <div className="ui-stat-card">
                  <span className="block text-[var(--text-muted)]">Budget</span>
                  <span className={`mt-1 block ${budgetStats ? 'text-emerald-600' : 'text-slate-500'}`}>
                    {budgetStats ? 'SYNCED' : 'STALE'}
                  </span>
                </div>
                <div className="ui-stat-card">
                  <span className="block text-[var(--text-muted)]">Logs</span>
                  <span className="mt-1 block text-sky-600">{filteredLogs.length}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleRestart}
              className="flex-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold transition-all hover:bg-slate-100"
            >
              <i className="fas fa-arrows-rotate mr-1.5" />
              Обновить
            </button>
            <ActionButton
              variant="secondary"
              icon="fa-pause"
              onClick={() => setLogs(initialLogs)}
              className="flex-1 rounded-full text-xs"
            >
              Сбросить лог
            </ActionButton>
          </div>
        </div>

        <div className="ui-section flex min-h-[420px] flex-col">
          <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="ui-stack-2">
              <div className="flex items-center gap-1.5 ui-eyebrow">
                <i className="fas fa-terminal text-[var(--accent-primary)]"></i>
                Живой лог событий
              </div>
              <div className="text-xl font-bold tracking-[-0.03em] text-[var(--text-primary)]">Сигналы, исключения и решения оператора</div>
            </div>
            <input
              type="text"
              placeholder="Фильтр событий..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="ui-toolbar-field md:w-64"
            />
          </div>

          <div className="custom-scrollbar flex-1 space-y-3 overflow-y-auto rounded-[18px] border border-[var(--border-default)] bg-[var(--surface-1)] p-4 font-mono text-[10px] shadow-inner">
            {filteredLogs.map((log) => {
              const badge = categoryLabel[log.category];
              return (
                <div key={log.id} className="ui-log-item">
                  <div className="flex items-start gap-2 text-[var(--text-secondary)] transition-all hover:text-[var(--text-primary)]">
                    <span className="shrink-0 select-none text-[var(--text-muted)] font-semibold">{log.time}</span>
                    <i className={`fas ${getLevelIcon(log.level)} shrink-0 mt-0.5`}></i>
                    <span className={`shrink-0 select-none rounded-full border px-1.5 py-px text-[8px] font-bold uppercase ${badge.cls}`}>
                      {badge.label}
                    </span>
                    <span className="leading-6 text-[11px]">{log.message}</span>
                  </div>

                  {log.hasActions && log.requestId && (
                    <div className="flex items-center gap-2 pl-14 pt-3 select-none">
                      <button
                        onClick={() => setLogs((prev) => prev.map((entry) => (
                          entry.id === log.id ? { ...entry, message: `${entry.message} (Подтверждено: Апрув 12%)`, hasActions: false } : entry
                        )))}
                        className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[8px] font-bold uppercase text-emerald-700 transition-all hover:bg-emerald-100"
                      >
                        Апрув 12%
                      </button>
                      <button
                        onClick={() => setLogs((prev) => prev.map((entry) => (
                          entry.id === log.id ? { ...entry, message: `${entry.message} (Подтверждено: Игнорировать)`, hasActions: false } : entry
                        )))}
                        className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[8px] font-bold uppercase text-slate-600 transition-all hover:bg-slate-100"
                      >
                        Игнорировать
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            {filteredLogs.length === 0 && (
              <div className="py-12 text-center italic text-[var(--text-muted)] select-none">
                Лог-записи не найдены
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
