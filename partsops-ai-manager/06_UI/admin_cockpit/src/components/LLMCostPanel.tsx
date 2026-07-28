import { useEffect, useState, useCallback } from 'react';
import { apiJson } from '../lib/api';
import { Card, Button, ErrorState, Skeleton } from './Primitives';

type CostData = {
  total_cost_usd: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  count: number;
};

export const LLMCostPanel = () => {
  const [data, setData] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dailyLimit = 10.0;

  const fetchCosts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const costData = await apiJson<CostData>('/api/admin/observability/llm-costs');
      setData(costData);
    } catch (e) {
      console.error('Error fetching LLM costs:', e);
      setError(e instanceof Error ? e.message : 'Не удалось загрузить данные стоимости LLM');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCosts();
    const interval = setInterval(fetchCosts, 30000);
    return () => clearInterval(interval);
  }, [fetchCosts]);

  if (loading && !data) {
    return (
      <Card title="Мониторинг затрат LLM" icon="robot">
        <div className="p-6 space-y-3">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card title="Мониторинг затрат LLM" icon="robot">
        <ErrorState message={error} onRetry={fetchCosts} />
      </Card>
    );
  }

  const totalCost = data?.total_cost_usd ?? 0;
  const budgetUtilization = Math.min(100, (totalCost / dailyLimit) * 100);

  const providers = data?.by_provider
    ? Object.entries(data.by_provider).map(([name, cost]) => ({
        name,
        cost,
        percentage: totalCost > 0 ? Math.round((cost / totalCost) * 100) : 0,
      }))
    : [];

  const providerColors = ['#2563eb', '#0e9f6e', '#d97706', '#0284c7', '#8b5cf6'];

  return (
    <Card
      title="Телеметрия ИИ-Агентов и Затраты LLM"
      icon="robot"
      headerActions={
        <Button variant="ghost" size="sm" icon="rotate" onClick={fetchCosts}>
          Обновить
        </Button>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column: LLM Spend & Budget */}
        <div className="space-y-4 rounded-[var(--radius-card)] border border-[var(--border-default)] bg-[var(--surface-2)] p-4">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                Расход за сутки (LLM Daily Spend)
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono text-[var(--text-primary)] tracking-tight">
                  ${totalCost.toFixed(3)}
                </span>
                <span className="text-xs text-[var(--text-muted)] font-mono">
                  / ${dailyLimit.toFixed(2)} лимит
                </span>
              </div>
            </div>
            <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[10px] font-bold text-blue-700">
              {budgetUtilization.toFixed(2)}% бюджета
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-[var(--surface-3)] rounded-full h-2 overflow-hidden border border-[var(--border-subtle)]">
            <div
              className="h-full rounded-full bg-[var(--accent-primary)] transition-all duration-500"
              style={{ width: `${Math.max(2, budgetUtilization)}%` }}
            />
          </div>

          <div className="text-[11px] text-[var(--text-secondary)] font-medium">
            Всего запросов к LLM: <strong className="font-mono text-[var(--text-primary)]">{data?.count ?? 0}</strong>
          </div>
        </div>

        {/* Right Column: Dynamic Provider breakdown */}
        <div className="space-y-3 rounded-[var(--radius-card)] border border-[var(--border-default)] bg-[var(--surface-2)] p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
            Распределение затрат по провайдерам
          </span>

          {providers.length === 0 ? (
            <div className="text-xs text-[var(--text-muted)] p-4 text-center">
              Запросы к LLM отсутствуют в текущей сессии
            </div>
          ) : (
            <div className="flex items-center gap-4">
              {/* Dynamic SVG Donut */}
              <div className="relative h-16 w-16 shrink-0 flex items-center justify-center">
                <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-[var(--surface-3)]"
                    strokeWidth="4"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  {providers.map((p, idx) => {
                    const strokeDasharray = `${p.percentage}, 100`;
                    const prevSum = providers.slice(0, idx).reduce((acc, curr) => acc + curr.percentage, 0);
                    return (
                      <path
                        key={p.name}
                        stroke={providerColors[idx % providerColors.length]}
                        strokeDasharray={strokeDasharray}
                        strokeDashoffset={`-${prevSum}`}
                        strokeWidth="4"
                        strokeLinecap="round"
                        fill="none"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                    );
                  })}
                </svg>
                <span className="absolute text-[10px] font-bold text-[var(--text-primary)] font-mono">
                  {data?.count ?? 0}
                </span>
              </div>

              {/* Provider list */}
              <div className="space-y-1.5 flex-1 text-[11px]">
                {providers.map((p, idx) => (
                  <div key={p.name} className="flex justify-between items-center text-[var(--text-secondary)]">
                    <span className="flex items-center gap-1.5 capitalize">
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: providerColors[idx % providerColors.length] }}
                      />
                      <span className="truncate max-w-[120px] font-medium">{p.name}</span>
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[var(--text-primary)] font-bold">${p.cost.toFixed(3)}</span>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">({p.percentage}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
