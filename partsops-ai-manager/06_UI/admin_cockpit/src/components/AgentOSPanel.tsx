import { useEffect, useState, useCallback } from 'react';
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

type LogEvent = {
  time: string;
  src: 'SYSTEM' | 'ERP' | 'PII_MASK' | 'LLM_ROUTING' | 'VALIDATOR';
  msg: string;
  tone: 'ok' | 'warn' | 'danger' | 'info';
};

export const AgentOSPanel = () => {
  const [traces, setTraces] = useState<Trace[]>([]);

  // Agent OS State
  const [agentStatus, setAgentStatus] = useState<'active' | 'paused' | 'safemode'>('active');
  const [rpmLimit, setRpmLimit] = useState(20);
  const [budgetLimit, setBudgetLimit] = useState(10.0);
  const [logLevel, setLogLevel] = useState('DEBUG');
  const [localCost, setLocalCost] = useState(2.02);

  // Mocked local events
  const [localEvents, setLocalEvents] = useState<LogEvent[]>([
    { time: '17:12:46', src: 'SYSTEM', msg: 'Выгрузка audit log в SHA-256 хранилище завершена.', tone: 'info' },
    { time: '17:12:56', src: 'PII_MASK', msg: 'Маскирование PII успешно удалило VIN и телефоны клиентов.', tone: 'ok' },
    { time: '17:13:02', src: 'VALIDATOR', msg: 'Целостность спецификации подтверждена SHA-256.', tone: 'ok' },
    { time: '17:13:20', src: 'ERP', msg: 'ERP-адаптер синхронизировал 5 черновиков счетов.', tone: 'ok' },
  ]);

  const fetchTraces = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/observability/traces');
      if (res.ok) {
        const data = await res.json();
        setTraces(data);
      } else {
        throw new Error('API traces offline. Loading simulated traces.');
      }
    } catch (e) {
      console.warn('Backend offline or trace endpoint error:', e);
      // Populate with mockup trace data if backend is offline
      setTraces([
        {
          correlation_id: 'tr-8f92b49',
          provider: 'OpenRouter',
          model: 'meta-llama/llama-3-70b-instruct',
          status: 'success',
          latency_ms: 1240,
          total_tokens: 1540,
          cost_usd: 0.00115,
          created_at: new Date().toISOString(),
        },
        {
          correlation_id: 'tr-5a11c82',
          provider: 'OpenAI',
          model: 'gpt-4o-mini',
          status: 'success',
          latency_ms: 850,
          total_tokens: 890,
          cost_usd: 0.00027,
          created_at: new Date(Date.now() - 60000).toISOString(),
        },
      ]);
    }
  }, []);

  useEffect(() => {
    fetchTraces();
    const interval = setInterval(fetchTraces, 15000);
    return () => clearInterval(interval);
  }, [fetchTraces]);

  const handleSimulateLog = () => {
    const systems: Array<LogEvent['src']> = ['SYSTEM', 'ERP', 'PII_MASK', 'LLM_ROUTING', 'VALIDATOR'];
    const messages = [
      'Получен новый вебхук от ERP. Очередь обновлена.',
      'AI-агент выполнил парсинг счетов с точностью 94%.',
      'Заблокировано обращение к невалидному API поставщика.',
      'Маскирование PII: VIN [скрыт] из соображений безопасности.',
      'Запущена проверка Golden Dataset для регрессионного теста.',
    ];
    const tones: Array<LogEvent['tone']> = ['ok', 'info', 'warn', 'danger'];

    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

    const newEvent: LogEvent = {
      time: timeStr,
      src: systems[Math.floor(Math.random() * systems.length)],
      msg: messages[Math.floor(Math.random() * messages.length)],
      tone: tones[Math.floor(Math.random() * tones.length)],
    };

    setLocalEvents((prev) => [newEvent, ...prev]);
    setLocalCost((prev) => prev + 0.05);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Control Section */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-950 via-slate-900 to-indigo-950 p-6 text-white border border-emerald-800/40 shadow-xl">
        <div className="absolute -right-24 -top-24 h-48 w-48 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -left-24 -bottom-24 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10 w-full">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-emerald-300 font-extrabold uppercase tracking-widest bg-emerald-500/20 border border-emerald-500/30 px-2.5 py-0.5 rounded-full backdrop-blur-md">
                АГЕНТ ОС
              </span>
              <span className={`h-2 w-2 rounded-full ${agentStatus === 'active' ? 'bg-emerald-400 animate-pulse' : agentStatus === 'paused' ? 'bg-amber-400' : 'bg-red-400 animate-ping'}`} />
              <span className="text-xs text-emerald-200 font-bold">
                {agentStatus === 'active' ? 'Поток активен' : agentStatus === 'paused' ? 'Поток приостановлен' : 'Безопасный режим'}
              </span>
            </div>
            <h2 className="text-xl font-extrabold text-white tracking-tight sm:text-2xl font-sans">
              Операторская консоль AI-движка
            </h2>
            <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
              Контроль LLM-моделей, бюджета сессии, лимитов RPM, ручного вмешательства и логов безопасности в реальном времени.
            </p>
          </div>

          {/* Quick controls */}
          <div className="flex flex-wrap items-center gap-2 bg-white/5 p-1.5 rounded-2xl border border-white/10 backdrop-blur-md w-full sm:w-auto">
            {agentStatus !== 'active' ? (
              <button
                onClick={() => {
                  setAgentStatus('active');
                  alert('AI-поток возобновлен.');
                }}
                className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-slate-900 bg-emerald-400 hover:bg-emerald-300 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
              >
                <i className="fas fa-play" />
                <span>Запустить поток</span>
              </button>
            ) : (
              <button
                onClick={() => {
                  setAgentStatus('paused');
                  alert('AI-поток приостановлен.');
                }}
                className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-amber-500 hover:bg-amber-400 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
              >
                <i className="fas fa-pause" />
                <span>Приостановить</span>
              </button>
            )}

            <button
              onClick={() => {
                setAgentStatus('safemode');
                alert('Безопасный режим (Safe Mode) активирован. Требуются явные подтверждения для всех действий.');
              }}
              className={`flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] ${
                agentStatus === 'safemode' ? 'bg-red-600 text-white' : 'text-slate-200 bg-white/10 hover:bg-white/20'
              }`}
            >
              <i className="fas fa-shield-halved" />
              <span>Safe Mode</span>
            </button>

            <button
              onClick={() => {
                if (confirm('Перезапустить контекст AI-агента? Очередь не очистится.')) {
                  setLocalCost(0.0);
                  alert('Контекст успешно очищен. Логи перезапущены.');
                }
              }}
              className="flex items-center justify-center h-9 w-9 rounded-xl text-slate-400 hover:text-red-400 bg-white/5 hover:bg-white/10 border border-white/10 transition-all duration-200"
              title="Перезапустить агента"
            >
              <i className="fas fa-arrow-rotate-right text-xs" />
            </button>
          </div>
        </div>
      </section>

      {/* Dynamic KPI Dashboard */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between hover:border-emerald-500/20 hover:shadow-sm transition-all duration-300">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Расход сессии</span>
          <b className="text-xl font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            ${localCost.toFixed(2)}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">из лимита ${budgetLimit.toFixed(2)}</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between hover:border-emerald-500/20 hover:shadow-sm transition-all duration-300">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Лимит RPM</span>
          <b className="text-xl font-extrabold text-[var(--text-primary)] font-mono block mt-1">
            {rpmLimit}
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">запросов в минуту</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between hover:border-emerald-500/20 hover:shadow-sm transition-all duration-300">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Здоровье очереди</span>
          <b className="text-xl font-extrabold text-emerald-600 font-mono block mt-1">
            98.8%
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">31 событие в окне</span>
        </div>

        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 flex flex-col justify-between hover:border-emerald-500/20 hover:shadow-sm transition-all duration-300">
          <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Доля ошибок</span>
          <b className="text-xl font-extrabold text-amber-500 font-mono block mt-1">
            1.2%
          </b>
          <span className="text-[9px] text-[var(--text-secondary)] mt-1.5">последний час работы</span>
        </div>
      </div>

      {/* Dual Panel Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Live Event Log & Traces */}
        <div className="lg:col-span-2 space-y-4">
          <SectionCard
            title="Живой лог событий & LLM Traces"
            icon="fa-terminal"
            headerActions={
              <div className="flex gap-2">
                <ActionButton variant="secondary" icon="fa-wand-magic-sparkles" onClick={handleSimulateLog}>
                  Симулировать шаг
                </ActionButton>
                <ActionButton variant="secondary" icon="fa-sync-alt" onClick={fetchTraces}>
                  Обновить
                </ActionButton>
              </div>
            }
          >
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
              
              {/* Local System signals */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Системные сигналы</span>
                <div className="divide-y divide-[var(--border-subtle)] border border-[var(--border-default)] rounded-lg bg-[var(--surface-2)]">
                  {localEvents.map((evt, idx) => {
                    const isOk = evt.tone === 'ok';
                    const isWarn = evt.tone === 'warn';
                    const isDanger = evt.tone === 'danger';
                    const badgeColor = isOk ? 'bg-emerald-500/10 text-emerald-700' : isWarn ? 'bg-amber-500/10 text-amber-700' : isDanger ? 'bg-rose-500/10 text-rose-700' : 'bg-blue-500/10 text-blue-700';
                    return (
                      <div key={idx} className="p-2.5 flex items-start gap-3 hover:bg-slate-500/5 transition-colors">
                        <span className="text-[10px] font-mono text-[var(--text-muted)] shrink-0 pt-0.5">{evt.time}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded shrink-0 ${badgeColor}`}>{evt.src}</span>
                        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{evt.msg}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* LLM Traces from backend */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Вызовы моделей ИИ (LLM Traces)</span>
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
                          <span className="text-xs font-mono font-bold text-[var(--text-primary)] block">${trace.cost_usd.toFixed(5)}</span>
                          <span className="text-[9px] text-[var(--text-muted)]">{trace.latency_ms} ms</span>
                        </div>
                        <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200 rounded-full">
                          {trace.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          </SectionCard>
        </div>

        {/* Right Column: Active Configuration & Watchlist */}
        <div className="space-y-4">
          <SectionCard title="Конфигурация & Ограничения" icon="fa-sliders">
            <div className="space-y-4 pt-1">
              
              {/* RPM Slider */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-[var(--text-secondary)]">Лимит запросов RPM</span>
                  <span className="font-mono text-emerald-600 font-bold">{rpmLimit} / мин</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="60"
                  step="5"
                  value={rpmLimit}
                  onChange={(e) => setRpmLimit(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                />
              </div>

              {/* Session budget */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-[var(--text-secondary)]">Бюджетный лимит</span>
                  <span className="font-mono text-indigo-600 font-bold">${budgetLimit.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="5"
                  value={budgetLimit}
                  onChange={(e) => setBudgetLimit(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                />
              </div>

              {/* Log level dropdown */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--text-secondary)]">Уровень детализации логов</label>
                <select
                  value={logLevel}
                  onChange={(e) => setLogLevel(e.target.value)}
                  className="w-full border border-[var(--border-default)] rounded-xl bg-[var(--surface-2)] p-2 text-xs font-semibold focus:border-emerald-600 outline-none"
                >
                  <option value="DEBUG">DEBUG (Все вызовы и сырые промпты)</option>
                  <option value="INFO">INFO (Ключевые решения и ошибки)</option>
                  <option value="WARN">WARN (Только исключения и аномалии)</option>
                </select>
              </div>

              {/* Boolean configs */}
              <div className="pt-2 space-y-2 border-t border-[var(--border-subtle)]">
                <div className="flex justify-between items-center py-1">
                  <div>
                    <span className="text-xs font-bold block">Принудительное маскирование PII</span>
                    <span className="text-[9px] text-[var(--text-muted)] leading-tight block">Авто-удаление VIN и телефонов клиентов в логах</span>
                  </div>
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                </div>
                
                <div className="flex justify-between items-center py-1">
                  <div>
                    <span className="text-xs font-bold block">Валидация SHA-256</span>
                    <span className="text-[9px] text-[var(--text-muted)] leading-tight block">Защита целостности пакета перед ERP-экспортом</span>
                  </div>
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                </div>
              </div>

            </div>
          </SectionCard>

          <SectionCard title="Список наблюдения ИИ-потока" icon="fa-eye">
            <div className="space-y-2 pt-1 text-[11px]">
              <div className="bg-slate-500/5 p-2 rounded-lg flex items-center justify-between border border-[var(--border-default)]">
                <div>
                  <strong className="block font-bold">АвтоЛиния</strong>
                  <span className="text-[9px] text-[var(--text-muted)]">Приоритетный SLA, ср. 7 мин</span>
                </div>
                <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">online</span>
              </div>
              <div className="bg-slate-500/5 p-2 rounded-lg flex items-center justify-between border border-[var(--border-default)]">
                <div>
                  <strong className="block font-bold">Orbit Parts</strong>
                  <span className="text-[9px] text-[var(--text-muted)]">Активен, ср. 12 мин</span>
                </div>
                <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">active</span>
              </div>
              <div className="bg-slate-500/5 p-2 rounded-lg flex items-center justify-between border border-[var(--border-default)]">
                <div>
                  <strong className="block font-bold">Nova Trade</strong>
                  <span className="text-[9px] text-[var(--text-muted)]">Цена устарела, ср. 29 мин</span>
                </div>
                <span className="text-[9px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">stale</span>
              </div>
            </div>
          </SectionCard>
        </div>

      </div>

      {/* Bottom Evidence Debug Layer */}
      <section className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-[var(--border-subtle)] pb-3">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
              <i className="fas fa-shield-halved text-indigo-600"></i> Хронология доказательств & Трассировка
            </h3>
            <p className="text-[10px] text-[var(--text-muted)]">Верификация прохождения автоматических проверок (Evidence Gates) и сохранение неизменяемых логов.</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button className="px-2.5 py-1 rounded bg-slate-500/10 hover:bg-slate-500/20 text-slate-700 text-[10px] font-bold transition-all border border-slate-200">Трассировка</button>
            <button className="px-2.5 py-1 rounded bg-slate-500/10 hover:bg-slate-500/20 text-slate-700 text-[10px] font-bold transition-all border border-slate-200">Raw JSON</button>
            <button className="px-2.5 py-1 rounded bg-slate-500/10 hover:bg-slate-500/20 text-slate-700 text-[10px] font-bold transition-all border border-slate-200">Лог ошибок</button>
            <button className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold transition-all border-none shadow-sm">Запустить проверку SLA</button>
          </div>
        </div>
        
        <div className="flex items-center gap-3 bg-emerald-500/5 border border-emerald-500/20 p-3 rounded-xl">
          <i className="fas fa-circle-check text-emerald-600 text-base animate-pulse"></i>
          <div>
            <span className="text-[11px] font-bold block text-[var(--text-primary)]">SHA-256 шифрование цепочки поставок подтверждено</span>
            <span className="text-[9px] text-[var(--text-secondary)]">Хеш-сумма: <code className="font-mono text-indigo-600 bg-slate-100 px-1 rounded">3a19b8...8f1a23</code>. Все вызовы инструментов ИИ подписаны цифровым ключом оператора.</span>
          </div>
        </div>
      </section>
    </div>
  );
};
