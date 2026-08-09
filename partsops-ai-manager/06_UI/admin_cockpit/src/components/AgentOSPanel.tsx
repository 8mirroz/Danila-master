import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { SectionCard, ActionButton, Icon } from './Primitives';

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
  mode?: string;
  local_fallback?: boolean;
  prefer_local?: boolean;
  key_configured?: boolean;
  hermes_url?: string;
  hint?: string;
  latency_ms?: number;
};

export const AgentOSPanel: React.FC = () => {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [hermesHealth, setHermesHealth] = useState<HermesHealth>({
    status: 'offline',
    version: 'unknown',
    profile: 'partsops',
    capabilities: [],
    model: 'partsops',
    skills: ['partsops-navigation', 'partsops-request-explainer', 'partsops-troubleshooting'],
    mode: 'unavailable',
    local_fallback: true,
  });

  const fetchHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/health');
      if (res.ok) {
        const data = await res.json();
        setHermesHealth((prev) => ({
          ...prev,
          ...data,
          capabilities: Array.isArray(data.capabilities) ? data.capabilities : prev.capabilities,
          skills: Array.isArray(data.skills) ? data.skills : prev.skills,
        }));
      }
    } catch {
      setHermesHealth((prev) => ({ ...prev, status: 'offline', mode: 'unavailable' }));
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
      <section className="panel-card relative overflow-hidden p-6">
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10 w-full">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-emerald-700">
                HERMES AGENT OS
              </span>
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  hermesHealth.status === 'online'
                    ? 'bg-emerald-500 animate-pulse'
                    : hermesHealth.status === 'degraded'
                    ? 'bg-amber-400'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-xs font-semibold text-ink-secondary">
                {hermesHealth.status === 'online'
                  ? 'Hermes API Server готов (Online)'
                  : hermesHealth.status === 'degraded'
                  ? hermesHealth.mode === 'local'
                    ? 'Локальный grounded fallback'
                    : 'Ограниченный режим (Degraded)'
                  : 'Сервис оффлайн (Offline)'}
              </span>
              {hermesHealth.mode && (
                <span className="rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-ink-muted">
                  mode:{hermesHealth.mode}
                </span>
              )}
            </div>
            <h2 className="font-sans text-xl font-bold tracking-tight text-ink-primary sm:text-2xl">
              Операторская консоль и трассировка Hermes
            </h2>
            <p className="max-w-xl text-xs leading-relaxed text-ink-secondary">
              Реальный мониторинг состояния изолированного профиля Hermes (`partsops`), доступных навыков, трассировки LLM вызовов и бюджета.
              {hermesHealth.hint ? (
                <span className="mt-1 block text-[11px] text-ink-muted">{hermesHealth.hint}</span>
              ) : null}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <ActionButton variant="secondary" icon="sync-alt" onClick={() => { fetchHealth(); fetchTraces(); }}>
              Обновить данные
            </ActionButton>
          </div>
        </div>
      </section>

      {/* Real KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface-1 border border-line rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-ink-muted uppercase tracking-wider">Статус готовности</span>
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
          <span className="text-[9px] text-ink-secondary mt-1.5">Профиль: {hermesHealth.profile}</span>
        </div>

        <div className="bg-surface-1 border border-line rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-ink-muted uppercase tracking-wider">Общий расход сессии</span>
          <b className="text-xl font-extrabold text-ink-primary font-mono block mt-1">
            ${totalCost.toFixed(4)}
          </b>
          <span className="text-[9px] text-ink-secondary mt-1.5">из дневного лимита $10.00</span>
        </div>

        <div className="bg-surface-1 border border-line rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-ink-muted uppercase tracking-wider">Обработано токенов</span>
          <b className="text-xl font-extrabold text-indigo-600 font-mono block mt-1">
            {totalTokens.toLocaleString()}
          </b>
          <span className="text-[9px] text-ink-secondary mt-1.5">всего вызовов: {traces.length}</span>
        </div>

        <div className="bg-surface-1 border border-line rounded-xl p-4 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-ink-muted uppercase tracking-wider">Версия / канал</span>
          <b className="text-xl font-extrabold text-ink-primary font-mono block mt-1">
            v{hermesHealth.version || '—'}
          </b>
          <span className="text-[9px] text-ink-secondary mt-1.5">
            {hermesHealth.hermes_url || 'http://127.0.0.1:8642'}
            {typeof hermesHealth.latency_ms === 'number' ? ` · ${hermesHealth.latency_ms}ms` : ''}
            {hermesHealth.local_fallback ? ' · fallback ready' : ''}
          </span>
        </div>
      </div>

      {/* Main Dual Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: LLM Traces from Backend */}
        <div className="lg:col-span-2 space-y-4">
          <SectionCard
            title="Реальные вызовы моделей (LLM Traces)"
            icon="terminal"
            headerActions={
              <ActionButton variant="secondary" icon="sync-alt" onClick={fetchTraces}>
                Обновить трассы
              </ActionButton>
            }
          >
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
              {traces.length === 0 ? (
                <div className="p-8 text-center text-ink-muted text-xs">
                  <Icon name="inbox" size={24} className="text-2xl mb-2 text-ink-secondary block" />
                  Нет зафиксированных LLM-трасс. Вызовите Hermes через чат-дровер для записи вызова.
                </div>
              ) : (
                <div className="divide-y divide-[var(--border-subtle)] border border-line rounded-lg bg-surface-2">
                  {traces.map((trace) => (
                    <div key={trace.correlation_id} className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-surface-20/5 transition-colors">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-ink-muted font-extrabold">{trace.correlation_id}</span>
                          <span className="text-[10px] font-bold text-ink-primary">{trace.model}</span>
                        </div>
                        <div className="flex items-center gap-3 text-[9px] text-ink-muted">
                          <span>Провайдер: <strong className="text-ink-secondary">{trace.provider}</strong></span>
                          <span>Токенов: <strong className="text-ink-secondary">{trace.total_tokens}</strong></span>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-right shrink-0">
                        <div className="text-right">
                          <span className="text-xs font-mono font-bold text-ink-primary block">${(trace.cost_usd || 0).toFixed(5)}</span>
                          <span className="text-[9px] text-ink-muted">{trace.latency_ms} ms</span>
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
          <SectionCard title="Подключенные Навыки (PartsOps Skills)" icon="microchip">
            <div className="space-y-2 pt-1">
              <span className="text-[10px] text-ink-muted block">
                Изолированный профиль `partsops` имеет доступ строго к 3 одобренным skills:
              </span>

              {hermesHealth.skills.map((skillName) => (
                <div key={skillName} className="p-2.5 rounded-lg border border-line bg-ink-primary flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon name="check-circle" size={12} className="text-emerald-400 text-xs" />
                    <span className="text-xs font-bold text-ink-primary font-mono">{skillName}</span>
                  </div>
                  <span className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-bold">
                    READ-ONLY
                  </span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Ограничения профиля и безопасность" icon="shield-halved">
            <div className="space-y-2 text-[11px] text-ink-secondary pt-1">
              <div className="flex items-center justify-between py-1 border-b border-line">
                <span>Прямой доступ к CLI / Terminal</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-line">
                <span>Файловый доступ / File I/O</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-line">
                <span>Сетевой Web Search / Scraper</span>
                <span className="text-rose-400 font-bold">ОТКЛЮЧЕН</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-line">
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
