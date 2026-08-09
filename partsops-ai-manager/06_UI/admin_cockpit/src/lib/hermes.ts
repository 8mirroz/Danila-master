export type HermesHealthStatus = 'online' | 'degraded' | 'offline';

export type HermesHealth = {
  status: HermesHealthStatus;
  profile: string;
  version?: string;
  model?: string;
  capabilities: string[];
  skills: string[];
  latency_ms?: number;
  error?: string;
  /** hermes | local | unavailable */
  mode?: string;
  local_fallback?: boolean;
  key_configured?: boolean;
  hermes_url?: string;
  hint?: string;
};

export type HermesStreamEvent =
  | { type: 'run.started'; run_id: string; correlation_id: string; sequence?: number; timestamp?: string }
  | { type: 'assistant.delta'; run_id: string; correlation_id: string; text: string; sequence?: number; timestamp?: string }
  | { type: 'run.progress'; run_id: string; correlation_id: string; label?: string; detail?: string; sequence?: number; timestamp?: string }
  | { type: 'source'; run_id: string; correlation_id: string; source_id: string; title: string; sequence?: number; timestamp?: string }
  | { type: 'navigation.action'; run_id: string; correlation_id: string; action: Record<string, unknown>; sequence?: number; timestamp?: string }
  | { type: 'run.completed'; run_id: string; correlation_id: string; usage?: Record<string, unknown>; sequence?: number; timestamp?: string }
  | { type: 'run.failed' | 'run.stopped'; run_id: string; correlation_id: string; code?: string; message?: string; retryable?: boolean; sequence?: number; timestamp?: string };

export function consumeSseBuffer(buffer: string): { events: HermesStreamEvent[]; remainder: string } {
  const events: HermesStreamEvent[] = [];
  const frames = buffer.split(/\n\n/);
  const remainder = frames.pop() ?? '';

  for (const frame of frames) {
    const data = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('');
    if (!data || data === '[DONE]') continue;
    try {
      events.push(JSON.parse(data) as HermesStreamEvent);
    } catch {
      // Keep incomplete or malformed upstream frames out of the UI stream.
    }
  }

  return { events, remainder };
}
