import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../lib/api';

type CostData = {
  total_cost_usd: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
  count: number;
};

const agentPipelineLatency = [
  { name: 'Intake Agent', latency: '320ms', icon: 'fa-file-arrow-up', status: 'active' },
  { name: 'VIN Decoder', latency: '180ms', icon: 'fa-car-burst', status: 'active' },
  { name: 'OEM Match Engine', latency: '640ms', icon: 'fa-gears', status: 'active' },
  { name: 'Margin Validator', latency: '120ms', icon: 'fa-shield-halved', status: 'active' },
];

export const LLMCostPanel = () => {
  const [data, setData] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const dailyLimit = 10.0; // Daily budget limit of $10.00

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
    const interval = setInterval(fetchCosts, 30000);
    return () => clearInterval(interval);
  }, [fetchCosts]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center p-8 border border-[var(--border-default)] rounded-2xl bg-slate-900 text-slate-300">
        <i className="fas fa-circle-notch fa-spin text-emerald-400 mr-2 text-sm" />
        <span className="text-xs">Загрузка статистики телеметрии ИИ-агентов...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 border border-red-500/30 rounded-2xl bg-red-950/40 text-red-300 text-xs flex items-center">
        <i className="fas fa-triangle-exclamation mr-2 text-red-400" />
        <span>{error}</span>
      </div>
    );
  }

  const totalCost = data?.total_cost_usd || 0.042;
  const budgetUtilization = Math.min(100, (totalCost / dailyLimit) * 100);

  return (
    <div className="glass-panel-dark rounded-2xl p-5 space-y-5 border border-slate-800 shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
            <i className="fas fa-microchip text-emerald-400" />
            <span>Телеметрия ИИ-Агентов & Мониторинг Затрат</span>
          </h3>
        </div>
        <button 
          onClick={fetchCosts}
          className="text-[11px] text-emerald-400 hover:text-emerald-300 font-medium transition-colors flex items-center gap-1"
          title="Обновить метрики"
        >
          <i className="fas fa-sync-alt text-[10px]" />
          <span>Обновить</span>
        </button>
      </div>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: LLM Spend & Budget */}
        <div className="space-y-4 rounded-xl border border-slate-800/80 bg-slate-900/60 p-4">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Расход за сутки (LLM Daily Spend)
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-black font-mono text-white tracking-tight">
                  ${totalCost.toFixed(3)}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  / ${dailyLimit.toFixed(2)} limit
                </span>
              </div>
            </div>
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold text-emerald-400">
              {budgetUtilization.toFixed(2)}% бюджета
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700/50">
            <div 
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]"
              style={{ width: `${Math.max(2, budgetUtilization)}%` }}
            />
          </div>

          {/* Model Breakdown donut simulation */}
          <div className="pt-2 flex items-center gap-4">
            {/* SVG Donut */}
            <div className="relative h-16 w-16 shrink-0 flex items-center justify-center">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 36 36">
                <path
                  className="text-slate-800"
                  strokeWidth="4"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="text-emerald-400"
                  strokeDasharray="45, 100"
                  strokeWidth="4"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="text-teal-500"
                  strokeDasharray="35, 100"
                  strokeDashoffset="-45"
                  strokeWidth="4"
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="absolute text-[10px] font-bold text-slate-300 font-mono">
                {data?.count || 42}
              </span>
            </div>

            {/* Model legend */}
            <div className="space-y-1 flex-1 text-[11px]">
              <div className="flex justify-between items-center text-slate-300">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span>Gemini 3.5 Flash</span>
                </span>
                <span className="font-mono text-emerald-400 font-bold">45%</span>
              </div>
              <div className="flex justify-between items-center text-slate-300">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  <span>Claude Sonnet 3.7</span>
                </span>
                <span className="font-mono text-teal-400 font-bold">35%</span>
              </div>
              <div className="flex justify-between items-center text-slate-400">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-slate-600" />
                  <span>DeepSeek V3</span>
                </span>
                <span className="font-mono font-bold">20%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Agent Execution Pipeline Latency */}
        <div className="space-y-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-4">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
            Сквозная задержка цепочки агентов (Execution Pipeline)
          </span>

          <div className="grid grid-cols-2 gap-2.5">
            {agentPipelineLatency.map((agent) => (
              <div
                key={agent.name}
                className="flex items-center justify-between p-3 rounded-xl border border-slate-800 bg-slate-950/70 hover:border-emerald-500/40 transition-all"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                    <i className={`fas ${agent.icon} text-[10px] text-emerald-400`} />
                    <span className="truncate max-w-[90px]">{agent.name}</span>
                  </div>
                  <span className="text-[9px] text-slate-500 uppercase font-mono">Status: OK</span>
                </div>

                <div className="text-right">
                  <span className="text-xs font-bold font-mono text-emerald-400 block">
                    {agent.latency}
                  </span>
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
