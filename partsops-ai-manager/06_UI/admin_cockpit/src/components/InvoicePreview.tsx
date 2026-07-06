import { useEffect, useState, useCallback } from 'react';
import { apiFetch, buildApiUrl } from '../lib/api';
import { ActionButton, InlineAlert } from './Primitives';

type InvoicePreviewProps = {
  requestId: string;
  onSent?: () => void;
};

type DeliveryStatus = {
  message_id: number;
  channel: string;
  recipient: string;
  status: string;
  attempts: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
};

export const InvoicePreview = ({ requestId, onSent }: InvoicePreviewProps) => {
  const [channel, setChannel] = useState<'email' | 'telegram' | 'both'>('email');
  const [recipient, setRecipient] = useState('');
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deliveryLogs, setDeliveryLogs] = useState<DeliveryStatus[]>([]);
  const [invoiceExists, setInvoiceExists] = useState<boolean | null>(null);

  const checkInvoiceAndLogs = useCallback(async () => {
    try {
      // 1. Check if invoice exists by fetching status
      const resStatus = await apiFetch(`/api/delivery/status/${requestId}`);
      if (resStatus.ok) {
        const logs = await resStatus.json();
        setDeliveryLogs(logs);
      }
      
      // 2. Fetch invoice PDF info
      const resPdf = await apiFetch(`/api/delivery/invoice/${requestId}/pdf`);
      setInvoiceExists(resPdf.ok);
    } catch (e) {
      console.error("Error checking invoice status:", e);
      setInvoiceExists(false);
    }
  }, [requestId]);

  useEffect(() => {
    void checkInvoiceAndLogs();
    const interval = setInterval(checkInvoiceAndLogs, 15000); // Poll status every 15s
    return () => clearInterval(interval);
  }, [checkInvoiceAndLogs]);

  const handleSend = async () => {
    if (!recipient) {
      setError("Укажите получателя (Email или ID чата Telegram)");
      return;
    }
    setSending(true);
    setError(null);
    setSendResult(null);
    try {
      const res = await apiFetch(`/api/delivery/send/${requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: channel,
          recipient: recipient,
          dry_run: false, // send real notification in dev mode
        }),
      });
      
      const data = await res.json();
      if (res.ok) {
        setSendResult(`Успешно отправлено через ${channel}!`);
        void checkInvoiceAndLogs();
        if (onSent) onSent();
      } else {
        setError(data.detail || "Не удалось отправить счет");
      }
    } catch (e) {
      console.error("Error sending invoice:", e);
      setError("Ошибка при отправке запроса");
    } finally {
      setSending(false);
    }
  };

  if (invoiceExists === null) {
    return (
      <div className="flex items-center justify-center p-8 border border-[var(--border-default)] rounded-xl bg-[var(--surface-1)]">
        <i className="fas fa-spinner fa-spin text-blue-500 mr-2"></i>
        <span className="text-xs text-[var(--text-secondary)]">Проверка наличия черновика счета...</span>
      </div>
    );
  }

  if (invoiceExists === false) {
    return (
      <div className="border border-[var(--border-default)] rounded-xl bg-[var(--surface-1)] p-5 text-center">
        <i className="fas fa-file-invoice text-slate-400 text-3xl mb-2"></i>
        <p className="text-xs text-[var(--text-secondary)]">
          Черновик коммерческого предложения (счета) еще не сформирован.
        </p>
        <p className="text-[10px] text-[var(--text-muted)] mt-1">
          Сначала выполните шаг 5 (Расчет цен и маржи) для генерации счета.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 border border-[var(--border-default)] rounded-xl bg-[var(--surface-1)] p-5 shadow-sm">
      {/* Column 1: PDF Preview */}
      <div className="space-y-2 flex flex-col h-[500px]">
        <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5">
          <i className="fas fa-eye text-blue-600"></i> Предварительный просмотр счета
        </span>
        <div className="flex-1 bg-slate-50 border border-[var(--border-default)] rounded-lg overflow-hidden relative">
          <iframe 
            src={buildApiUrl(`/api/delivery/invoice/${requestId}/pdf`)}
            className="w-full h-full border-none"
            title="Invoice PDF Preview"
          ></iframe>
        </div>
      </div>

      {/* Column 2: Send controls and delivery logs */}
      <div className="space-y-4 flex flex-col justify-between">
        <div className="space-y-4">
          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] flex items-center gap-1.5 border-b border-[var(--border-subtle)] pb-2.5">
            <i className="fas fa-paper-plane text-blue-600"></i> Доставка коммерческого предложения
          </span>

          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase block mb-1">Канал доставки</label>
              <div className="flex gap-2">
                {(['email', 'telegram', 'both'] as const).map(ch => (
                  <button
                    key={ch}
                    onClick={() => {
                      setChannel(ch);
                      if (ch === 'email') setRecipient('client@example.com');
                      else if (ch === 'telegram') setRecipient('123456789');
                    }}
                    className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold border transition-all ${
                      channel === ch 
                        ? 'bg-blue-50 border-blue-500 text-blue-700' 
                        : 'bg-[var(--surface-2)] border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--state-hover)]'
                    }`}
                  >
                    {ch === 'email' ? 'Email' : ch === 'telegram' ? 'Telegram' : 'Оба канала'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase block mb-1">Получатель</label>
              <input
                type="text"
                placeholder={channel === 'email' ? 'client@example.com' : channel === 'telegram' ? 'ID чата Telegram' : 'client@example.com или ID чата'}
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] rounded-lg px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] font-sans"
              />
            </div>

            {error && <InlineAlert type="danger" message={error} />}
            {sendResult && <InlineAlert type="success" message={sendResult} />}

            <ActionButton
              variant="primary"
              icon="fa-paper-plane"
              onClick={handleSend}
              loading={sending}
              className="w-full justify-center py-2"
            >
              Отправить счет клиенту
            </ActionButton>
          </div>
        </div>

        {/* Delivery Logs */}
        <div className="space-y-2 pt-4 border-t border-[var(--border-subtle)]">
          <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider block">История отправок</span>
          {deliveryLogs.length === 0 ? (
            <div className="text-[10px] text-[var(--text-muted)] italic py-4 text-center">
              Счет еще не отправлялся.
            </div>
          ) : (
            <div className="max-h-[180px] overflow-y-auto space-y-2 pr-1">
              {deliveryLogs.map((log) => (
                <div key={log.message_id} className="bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-lg p-2.5 text-xs flex justify-between items-start">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-[var(--text-secondary)] uppercase">{log.channel}</span>
                      <span className="text-[10px] text-[var(--text-muted)] truncate w-32" title={log.recipient}>
                        {log.recipient}
                      </span>
                    </div>
                    {log.last_error && (
                      <span className="text-[10px] text-red-600 block">{log.last_error}</span>
                    )}
                    <span className="text-[9px] text-[var(--text-muted)] block mt-0.5">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className={`px-2 py-0.5 text-[9px] font-extrabold uppercase rounded-full ${
                      log.status === 'sent' || log.status === 'delivered'
                        ? 'bg-green-100 text-green-700'
                        : log.status === 'failed'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-amber-100 text-amber-700'
                    }`}>
                      {log.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
