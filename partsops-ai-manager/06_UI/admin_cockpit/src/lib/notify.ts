type ToastId = string;

const activeTimers = new Map<ToastId, number>();

function show(level: 'log' | 'info' | 'warn' | 'error', msg: string, duration = 4000): ToastId {
  const id = `toast-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  console[level](msg);
  const timer = window.setTimeout(() => activeTimers.delete(id), duration);
  activeTimers.set(id, timer);
  return id;
}

export const notify = {
  transition: (from: string, to: string) =>
    show('info', `Статус: ${from} -> ${to}`),

  success: (msg: string) => show('info', msg),

  error: (msg: string) => show('error', msg, 6000),

  info: (msg: string) => show('info', msg),

  /**
   * Honest ERP status check — does NOT start a full ERP push (no such one-click API).
   * Reads /api/admin/data-health and reports failing flag + last sync time.
   */
  erpSync: async () => {
    try {
      const { apiFetch } = await import('./api');
      const res = await apiFetch('/api/admin/data-health');
      if (!res.ok) {
        show('error', `ERP status: API ${res.status}`, 6000);
        return;
      }
      const data = await res.json();
      const failing = Boolean(data?.health_indicators?.erp_health?.currently_failing);
      const lastSync =
        data?.freshness?.last_erp_sync ??
        data?.freshness?.last_erp_sync_at ??
        null;
      show(
        'info',
        `Статус ERP: ${failing ? 'Сбой' : 'OK'}, last sync: ${lastSync ?? 'н/д'}. ` +
          'Полный ERP push — не one-click job (только invoice endpoint).',
        7000,
      );
    } catch (err) {
      show(
        'error',
        `ERP status unavailable: ${err instanceof Error ? err.message : String(err)}`,
        6000,
      );
    }
  },

  invoiceDrafted: (num: string) =>
    show('info', `Черновик счёта создан: ${num}`),

  apiError: (status: number, detail: string) =>
    show('error', `API ${status}: ${detail}`, 8000),

  loading: (msg: string) => show('log', msg),

  dismiss: (id?: string) => {
    const ids = id ? [id] : [...activeTimers.keys()];
    for (const key of ids) {
      const timer = activeTimers.get(key);
      if (timer) {
        window.clearTimeout(timer);
        activeTimers.delete(key);
      }
    }
  },
};
