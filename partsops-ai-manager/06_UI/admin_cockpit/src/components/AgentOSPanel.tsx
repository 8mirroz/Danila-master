import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { SectionCard, ActionButton } from './Primitives';

type Trace = {
  correlation_id: string;
  provider: string;
  model: string;
  status: string;
  latency_ms: number;
  total_tokens: number;
  cost_usd: number;
  created_at: string;
};

type HermesHealth = {
  status: 'online' | 'degraded' | 'offline';
  version: string;
  profile: string;
  capabilities: string[];
  model: string;
  skills: string[];
  error?: string;
};

export const AgentOSPanel: React.FC = () => {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [hermesHealth, setHermesHealth] = useState<HermesHealth>({
    status: 'offline',
    version: '0.19.0',
    profile: 'partsops',
    capabilities: [],
    model: 'anthropic/claude-3-5-haiku',
    skills: ['partsops-navigation', 'partsops-request-explainer', 'partsops-troubleshooting'],
  });

  const fetchHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/health');
      if (res.ok) {
        const data = await res.json();
        setHermesHealth(data);
      }
    } catch {
      setHermesHealth((prev) => ({ ...prev, status: 'offline' }));
    }
  }, []);

  const fetchTraces = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/observability/traces');
      if (res.ok) {
        const data = await res.json();
        setTraces(data);
      } else {
        setTraces([]);
      }
    } catch (e) {
      console.warn('Backend traces endpoint offline:', e);
      setTraces([]);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchTraces();
    const interval = setInterval(() => {
      fetchHealth();
      fetchTraces();
    }, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchTraces]);

  const totalCost = traces.reduce((acc, t) => acc + (t.cost_usd || 0), 0);
  const totalTokens = traces.reduce((acc, t) => acc + (t.total_tokens || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top Real Status Control Banner */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-6 text-white border border-slate-800 shadow-xl">
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10 w-full">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-emerald-300 font-extrabold uppercase tracking-widest bg-emerald-500/20 border border-emerald-500/30 px-2.5 py-0.5 rounded-full backdrop-blur-md">
                HERMES AGENT OS
              </span>
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  hermesHealth.status === 'online'
                    ? 'bg-emerald-400 animate-pulse'
                    : hermesHealth.status === 'degraded'
                    ? 'bg-amber-400'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-xs text-slate-200 font-bold">
                {hermesHealth.status === 'online'
                  ? 'Hermes API Server готов (Online)'
                  : hermesHealth.status === 'degraded'
                  ? 'Ограниченный режим (Degraded)'
                  : 'Сервис оффлайн (Offline)'}
              </span>
            </div>
            <h2 className="text-xl font-extrabold text-white tracking-tight sm:text-2xl font-sans">
              Операторская консоль и трассировка Hermes
            </h2>
            <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
              Реальный мониторинг состояния изолированного профиля Hermes (`partsops`), доступных навыков, трассировки LLM вызовов и бюджета.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <ActionButton variant="secondary" icon="fa-sync-alt" onClick={() => { fetchHealth(); fetchTraces(); }}>
              Обновить данные
            </ActionButton>
          </div>
        </div>
      </section>

      {/* Real KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Статус готовности</span>
          <b
            className={`text-xl font-extrabold font-mono block mt-1 ${
              hermesHealth.status === 'online'
                ? 'text-emerald-600'
                : hermesHealth.status === 'degraded'
                ? 'text-amber-500'
                : 'text-rose-500'
            }`}
          >
            {hermesHealth.status.toUpperCase()}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">Профиль: {hermesHealth.profile}</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Общий расход сессии</span>
          <b className="text-xl font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            ${totalCost.toFixed(4)}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">из дневного лимита $10.00</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Обработано токенов</span>
          <b className="text-xl font-extrabold text-indigo-600 font-mono block mt-1">
            {totalTokens.toLocaleString()}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">всего вызовов: {traces.length}</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Версия Hermes</span>
          <b className="text-xl font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            v{hermesHealth.version}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">порт 127.0.0.1:8642</span>
        </div>
      </div>

      {/* Main Dual Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: LLM Traces from Backend */}
        <div className="lg:col-span-2 space-y-4">
          <SectionCard
            title="Реальные вызовы моделей (LLM Traces)"
            icon="fa-terminal"
            headerActions={
              <ActionButton variant="secondary" icon="fa-sync-alt" onClick={fetchTraces}>
                Обновить трассы
              </ActionButton>
            }
          >
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
              {traces.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-xs">
                  <i className="fas fa-inbox text-2xl mb-2 text-slate-600 block" />
                  Нет зафиксированных LLM-трасс. Вызовите Hermes через чат-дровер для записи вызова.
                </div>
              ) : (
                <div className="divide-y divide-[var(--border-subtle)] border border-[var(--border-default)] rounded-lg bg-[var(--surface-2)]">
                  {traces.map((trace) => (
                    <div key={trace.correlation_id} className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-slate-500/5 transition-colors">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-[var(--text-muted)] font-extrabold">{trace.correlation_id}</span>
                          <span className="text-[10px] font-bold text-[var(--text-primary)]">{trace.model}</span>
                        </div>
                        <div className="flex items-center gap-3 text-[9px] text-[var(--text-muted)]">
                          <span>Провайдер: <strong className="text-[var(--text-secondary)]">{trace.provider}</strong></span>
                          <span>Токенов: <strong className="text-[var(--text-secondary)]">{trace.total_tokens}</strong></span>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-right shrink-0">
                        <div className="text-right">
                          <span className="text-xs font-mono font-bold text-[var(--text-primary)] block">${(trace.cost_usd || 0).toFixed(5)}</span>
                          <span className="text-[9px] text-[var(--text-muted)]">{trace.latency_ms} ms</span>
                        </div>
                        <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200 rounded-full">
                          {trace.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        {/* Right Column: Active Profile Skills & Capabilities */}
        <div className="space-y-4">
          <SectionCard title="Подключенные Навыки (PartsOps Skills)" icon="fa-microchip">
            <div className="space-y-2 pt-1">
              <span className="text-[10px] text-[var(--text-muted)] block">
                Изолированный профиль `partsops` имеет доступ строго к 3 одобренным skills:
              </span>

              {hermesHealth.skills.map((skillName) => (
                <div key={skillName} className="p-2.5 rounded-lg border border-slate-700 bg-slate-900 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <i className="fas fa-check-circle text-emerald-400 text-xs" />
                    <span className="text-xs font-bold text-slate-200 font-mono">{skillName}</span>
                  </div>
                  <span className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-bold">
                    READ-ONLY
                  </span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Ограничения профиля и безопасность" icon="fa-shield-halved">
            <div className="space-y-2 text-[11px] text-[var(--text-secondary)] pt-1">
              <div className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Прямой доступ к CLI / Terminal</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Файловый доступ / File I/O</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Сетевой Web Search / Scraper</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Автоматическое редактирование skills</span>
                <span className="text-rose-400 font-bold">ЗАБЛОКИРОВАНО</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span>Обезличивание PII (VIN/Телефон)</span>
                <span className="text-emerald-400 font-bold">АКТИВНО</span>
              </div>
            </div>
          </SectionCard>
        </div>

      </div>
    </div>
  );
};
