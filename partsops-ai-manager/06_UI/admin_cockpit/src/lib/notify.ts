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

  erpSync: () =>
    show('info', 'ERP синхронизация запущена'),

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
