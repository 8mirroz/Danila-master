import { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '../lib/api';
import { Button, Icon, ModalShell, StatusBadge } from './Primitives';

type RequestSummary = {
  request_id: string;
  customer_name: string;
  status: string;
  parts_json: string;
};

type RunEvent = {
  sequence: number;
  type: string;
  phase?: string | null;
  message: string;
  payload?: { errors?: string[]; warnings?: string[] };
};

type PipelineRun = {
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'blocked';
  start_from: string;
  requested_lane?: string | null;
  correlation_id: string;
  error_message?: string | null;
};

const TERMINAL = new Set(['completed', 'failed', 'blocked']);
const PHASE_LABELS: Record<string, string> = {
  intake: 'Приём и нормализация',
  processing: 'Подбор и расчёт',
  delivery: 'Документы и доставка',
  reporting: 'Аудит и отчёт',
};

function parseSseChunk(chunk: string): RunEvent[] {
  return chunk.split('\n\n').flatMap((block) => {
    const data = block.split('\n').find((line) => line.startsWith('data: '))?.slice(6);
    if (!data) return [];
    try { return [JSON.parse(data) as RunEvent]; } catch { return []; }
  });
}

export function PipelineRunDialog({
  request,
  targetLane,
  restoreRunId,
  open,
  onClose,
  onCompleted,
}: {
  request: RequestSummary | null;
  targetLane: string | null;
  restoreRunId?: string | null;
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
}) {
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readerRef = useRef<AbortController | null>(null);

  const isActive = Boolean(run && !TERMINAL.has(run.status));
  const phaseRows = useMemo(() => ['intake', 'processing', 'delivery', 'reporting'].map((phase) => {
    const phaseEvents = events.filter((event) => event.phase === phase);
    const latest = phaseEvents.at(-1);
    return { phase, state: latest?.type ?? 'pending', message: latest?.message };
  }), [events]);

  useEffect(() => () => readerRef.current?.abort(), []);

  // Auto-trigger pipeline execution on drop/open
  useEffect(() => {
    if (!open || !request || !targetLane || run || starting || restoreRunId) return;
    void startRun();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, request?.request_id, targetLane, run, starting, restoreRunId]);

  // Trigger completion callback on completed status to refresh Kanban board
  useEffect(() => {
    if (run?.status === 'completed') {
      onCompleted();
    }
  }, [run?.status, onCompleted]);

  useEffect(() => {
    if (!open || !request || !restoreRunId || run) return;
    let disposed = false;
    const restore = async () => {
      try {
        const response = await apiFetch(`/api/requests/${request.request_id}/pipeline-runs/${restoreRunId}`);
        if (!response.ok) throw new Error('Сохранённый pipeline run больше недоступен.');
        const restored = await response.json() as PipelineRun;
        if (disposed) return;
        setRun(restored);
        if (!TERMINAL.has(restored.status)) await streamRun(restored);
        else onCompleted();
      } catch (restoreError) {
        if (!disposed) setError(restoreError instanceof Error ? restoreError.message : 'Не удалось восстановить pipeline run.');
      }
    };
    void restore();
    return () => { disposed = true; };
  // streamRun is intentionally invoked only for a persisted run identity.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, request?.request_id, restoreRunId, run, onCompleted]);

  const streamRun = async (activeRun: PipelineRun) => {
    readerRef.current?.abort();
    const controller = new AbortController();
    readerRef.current = controller;
    try {
      const response = await apiFetch(
        `/api/requests/${request?.request_id}/pipeline-runs/${activeRun.run_id}/events`,
        { signal: controller.signal },
      );
      if (!response.ok || !response.body) throw new Error('Не удалось подключиться к потоку статуса pipeline.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lastBoundary = buffer.lastIndexOf('\n\n');
        if (lastBoundary >= 0) {
          const completed = buffer.slice(0, lastBoundary + 2);
          buffer = buffer.slice(lastBoundary + 2);
          const received = parseSseChunk(completed);
          if (received.length) setEvents((current) => [...current, ...received.filter((event) => !current.some((old) => old.sequence === event.sequence))]);
        }
        if (done) break;
      }
      const statusResponse = await apiFetch(`/api/requests/${request?.request_id}/pipeline-runs/${activeRun.run_id}`);
      if (statusResponse.ok) {
        const latest = await statusResponse.json() as PipelineRun;
        setRun(latest);
        if (TERMINAL.has(latest.status)) onCompleted();
      }
    } catch (streamError) {
      if (!controller.signal.aborted) setError(streamError instanceof Error ? streamError.message : 'Поток статуса недоступен.');
    }
  };

  const startRun = async () => {
    if (!request || !targetLane) return;
    setStarting(true);
    setError(null);
    setEvents([]);
    try {
      const response = await apiFetch(`/api/requests/${request.request_id}/pipeline-runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requested_lane: targetLane }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось поставить pipeline в очередь.');
      const startedRun = data as PipelineRun;
      setRun(startedRun);
      localStorage.setItem('partsops.activePipelineRun', JSON.stringify({ requestId: request.request_id, runId: startedRun.run_id, targetLane }));
      await streamRun(startedRun);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : 'Не удалось запустить pipeline.');
    } finally {
      setStarting(false);
    }
  };

  const handleClose = () => {
    if (isActive) {
      onClose();
      return;
    }
    if (run && TERMINAL.has(run.status)) localStorage.removeItem('partsops.activePipelineRun');
    onClose();
  };

  return (
    <ModalShell
      open={open && request !== null}
      onClose={handleClose}
      title={run ? 'Выполнение pipeline' : 'Подтверждение запуска pipeline'}
      subtitle={isActive ? 'Run продолжит работу в фоне; диалог можно свернуть.' : 'Финальный этап определяет pipeline, а не drag-and-drop.'}
      widthClass="max-w-2xl"
      footer={!run ? (
        <div className="flex justify-end gap-2.5">
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button variant="primary" icon="circle-check" disabled={starting} onClick={() => void startRun()}>
            {starting ? 'Постановка в очередь…' : 'Запустить pipeline'}
          </Button>
        </div>
      ) : undefined}
    >
      {request && <div className="space-y-5">
        <div className="rounded-[20px] border border-[var(--border-default)] bg-[var(--surface-2)] p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-xs font-bold text-[var(--text-primary)]">{request.request_id}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{request.customer_name || 'Клиент не указан'}</p>
            </div>
            <StatusBadge status={request.status} />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 border-t border-[var(--border-default)] pt-3 sm:grid-cols-2">
            <div><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">Запрошенная зона</p><p className="mt-1 text-xs font-semibold text-[var(--text-primary)]">{targetLane}</p></div>
            <div><p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-muted)]">Точка старта</p><p className="mt-1 text-xs font-semibold text-[var(--text-primary)]">{run ? PHASE_LABELS[run.start_from] ?? run.start_from : 'Сервер определит после проверки'}</p></div>
          </div>
        </div>

        {run && <div className="rounded-[20px] border border-[var(--border-default)] bg-white p-4">
          <div className="flex items-center justify-between gap-3"><span className="text-xs font-bold text-[var(--text-primary)]">Ход выполнения</span><span className="font-mono text-[10px] text-[var(--text-muted)]">{run.run_id}</span></div>
          <div className="mt-4 space-y-2">
            {phaseRows.map(({ phase, state, message }) => {
              const done = state === 'phase.completed';
              const failed = state === 'phase.failed';
              const active = state === 'phase.started';
              return <div key={phase} className="flex items-center gap-3 rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] ${failed ? 'bg-rose-100 text-rose-700' : done ? 'bg-emerald-100 text-emerald-700' : active ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-500'}`}><Icon name={failed ? 'x-mark' : done ? 'circle-check' : active ? 'rotate' : 'minus'} size={12} /></span>
                <div className="min-w-0"><p className="text-xs font-semibold text-[var(--text-primary)]">{PHASE_LABELS[phase]}</p>{message && <p className="truncate text-[10px] text-[var(--text-muted)]">{message}</p>}</div>
              </div>;
            })}
          </div>
          <div className="mt-4 rounded-xl border border-[var(--border-default)] bg-[var(--surface-2)] px-3 py-2 text-[10px] text-[var(--text-muted)]">Correlation ID: <span className="font-mono text-[var(--text-secondary)]">{run.correlation_id}</span></div>
        </div>}

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</div>}
        {run?.status === 'completed' && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">Pipeline завершён. Доска обновлена по подтверждённому состоянию сервера.</div>}
        {run?.status === 'failed' && <div className="flex justify-end"><Button variant="secondary" onClick={() => { setRun(null); setEvents([]); }}>Повторить запуск</Button></div>}
      </div>}
    </ModalShell>
  );
}
