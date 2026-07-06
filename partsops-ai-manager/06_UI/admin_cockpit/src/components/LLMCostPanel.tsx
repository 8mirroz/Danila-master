import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../lib/api';

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
  
  const dailyLimit = 10.0; // Daily budget limit of $10.00 for demo

  const fetchCosts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/admin/observability/llm-costs');
      if (!res.ok) {
        throw new Error(`Ошибка: ${res.status} ${res.statusText}`);
      }
      const costData = await res.json();
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
    const interval = setInterval(fetchCosts, 30000); // refresh every 30 seconds
    return () => clearInterval(interval);
  }, [fetchCosts]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center p-8 border border-[var(--border-default)] rounded-xl bg-[var(--surface-1)]">
        <i className="fas fa-spinner fa-spin text-blue-500 mr-2"></i>
        <span className="text-xs text-[var(--text-secondary)]">Загрузка статистики затрат LLM...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 border border-red-200 rounded-xl bg-red-50 text-red-700 text-xs flex items-center">
        <i className="fas fa-triangle-exclamation mr-2"></i>
        <span>{error}</span>
      </div>
    );
  }

  if (!data) return null;

  const budgetUtilization = Math.min(100, (data.total_cost_usd / dailyLimit) * 100);

  return (
    <div className="border border-[var(--border-default)] rounded-xl bg-[var(--surface-1)] shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
          <i className="fas fa-chart-line text-blue-600"></i> Мониторинг затрат LLM & Бюджет
        </h3>
        <button 
          onClick={fetchCosts}
          className="text-[10px] text-blue-600 hover:text-blue-800 font-semibold"
          title="Обновить данные"
        >
          <i className="fas fa-sync-alt"></i>
        </button>
      </div>

      {/* Main KPI */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[var(--surface-2)] p-3 rounded-lg border border-[var(--border-default)]">
          <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase block">Общие расходы</span>
          <span className="text-lg font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            ${data.total_cost_usd.toFixed(4)}
          </span>
        </div>
        <div className="bg-[var(--surface-2)] p-3 rounded-lg border border-[var(--border-default)]">
          <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase block">Всего запросов</span>
          <span className="text-lg font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            {data.count}
          </span>
        </div>
      </div>

      {/* Budget Utilization bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-[10px] font-bold uppercase text-[var(--text-secondary)]">
          <span>Использование бюджета</span>
          <span>{budgetUtilization.toFixed(1)}% / ${dailyLimit.toFixed(2)} limit</span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              budgetUtilization > 85 ? 'bg-red-500' : budgetUtilization > 60 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${budgetUtilization}%` }}
          ></div>
        </div>
      </div>

      {/* Provider & Model Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
        {/* By Provider */}
        <div className="space-y-2">
          <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider block">По провайдерам</span>
          {Object.keys(data.by_provider).length === 0 ? (
            <span className="text-[10px] text-[var(--text-muted)] block">Данных нет</span>
          ) : (
            <div className="space-y-1.5">
              {Object.entries(data.by_provider).map(([provider, cost]) => (
                <div key={provider} className="flex justify-between text-xs items-center bg-[var(--surface-2)] px-2.5 py-1.5 rounded border border-[var(--border-subtle)]">
                  <span className="font-medium text-[var(--text-secondary)] truncate w-32">{provider}</span>
                  <span className="font-bold text-[var(--text-primary)] font-mono">${cost.toFixed(4)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* By Model */}
        <div className="space-y-2">
          <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider block">По моделям</span>
          {Object.keys(data.by_model).length === 0 ? (
            <span className="text-[10px] text-[var(--text-muted)] block">Данных нет</span>
          ) : (
            <div className="space-y-1.5">
              {Object.entries(data.by_model).map(([model, cost]) => (
                <div key={model} className="flex justify-between text-xs items-center bg-[var(--surface-2)] px-2.5 py-1.5 rounded border border-[var(--border-subtle)]">
                  <span className="font-medium text-[var(--text-secondary)] truncate w-32" title={model}>{model.split('/').pop()}</span>
                  <span className="font-bold text-[var(--text-primary)] font-mono">${cost.toFixed(4)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
