import { useEffect, useState, useCallback } from 'react';
import { apiFetch, buildApiUrl } from '../lib/api';
import { ActionButton, InlineAlert, Icon } from './Primitives';

type InvoicePreviewProps = {
  requestId: string;
  onSent?: () => void;
  /** When false, skip PDF GET (avoids expected 404 noise for pre-invoice requests). */
  expectInvoice?: boolean;
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

export const InvoicePreview = ({ requestId, onSent, expectInvoice = false }: InvoicePreviewProps) => {
  const [channel, setChannel] = useState<'email' | 'telegram'>('email');
  const [recipient, setRecipient] = useState('');
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deliveryLogs, setDeliveryLogs] = useState<DeliveryStatus[]>([]);
  const [invoiceExists, setInvoiceExists] = useState<boolean | null>(expectInvoice ? null : false);
  const [statusError, setStatusError] = useState<string | null>(null);

  const checkInvoiceAndLogs = useCallback(async (opts?: { probePdf?: boolean }) => {
    setStatusError(null);
    try {
      const resStatus = await apiFetch(`/api/delivery/status/${requestId}`);
      if (!resStatus.ok) throw new Error(`Delivery status HTTP ${resStatus.status}`);
      const logs = await resStatus.json();
      setDeliveryLogs(Array.isArray(logs) ? logs : []);

      const shouldProbe = opts?.probePdf === true && expectInvoice;
      if (shouldProbe) {
        const resPdf = await apiFetch(`/api/delivery/invoice/${requestId}/pdf`);
        setInvoiceExists(resPdf.ok);
      } else if (!expectInvoice) {
        setInvoiceExists(false);
      }
    } catch (e) {
      console.warn('Invoice status check failed', e);
      setStatusError(e instanceof Error ? e.message : 'Не удалось загрузить статус доставки');
    }
  }, [requestId, expectInvoice]);

  useEffect(() => {
    void checkInvoiceAndLogs({ probePdf: expectInvoice });
    const interval = setInterval(() => void checkInvoiceAndLogs({ probePdf: false }), 30000);
    return () => clearInterval(interval);
  }, [checkInvoiceAndLogs, expectInvoice]);

  if (statusError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-center">
        <InlineAlert type="danger" message={`Статус счета недоступен: ${statusError}`} />
        <ActionButton variant="secondary" onClick={() => void checkInvoiceAndLogs()}>Повторить</ActionButton>
      </div>
    );
  }

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
          dry_run: false,
        }),
      });
      
      const data = await res.json();
      if (res.ok && data.success && ['sent', 'delivered'].includes(data.status)) {
        setSendResult(`Успешно отправлено через ${channel}!`);
        void apiFetch(`/api/requests/${requestId}/transition`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_state: 'SENT_TO_CLIENT', reason: 'Счет успешно доставлен клиенту' }),
        }).catch(() => {});
        void checkInvoiceAndLogs();
        if (onSent) onSent();
      } else {
        setError(data.detail || data.error || `Доставка не подтверждена: ${data.status || `HTTP ${res.status}`}`);
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
      <div className="flex items-center justify-center p-8 border border-line rounded-xl bg-surface-1">
        <Icon name="spinner" size={14} className="text-blue-500 mr-2 animate-spin" />
        <span className="text-xs text-ink-secondary">Проверка наличия черновика счета...</span>
      </div>
    );
  }

  if (invoiceExists === false) {
    return (
      <div className="border border-line rounded-xl bg-surface-1 p-5 text-center">
        <Icon name="file-invoice" size={30} className="text-ink-muted text-3xl mb-2" />
        <p className="text-xs text-ink-secondary">
          Черновик коммерческого предложения (счета) еще не сформирован.
        </p>
        <p className="text-[10px] text-ink-muted mt-1">
          Сначала выполните шаг 5 (Расчет цен и маржи) для генерации счета.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 border border-line rounded-xl bg-surface-1 p-5 shadow-sm">
      {/* Column 1: PDF Preview */}
      <div className="space-y-2 flex flex-col h-[500px]">
        <span className="text-xs font-bold uppercase tracking-wider text-ink-secondary flex items-center gap-1.5">
          <Icon name="eye" size={14} className="text-blue-600" /> Предварительный просмотр счета
        </span>
        <div className="flex-1 bg-surface-2 border border-line rounded-lg overflow-hidden relative">
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
          <span className="text-xs font-bold uppercase tracking-wider text-ink-secondary flex items-center gap-1.5 border-b border-line-subtle pb-2.5">
            <Icon name="paper-plane" size={14} className="text-blue-600" /> Доставка коммерческого предложения
          </span>

          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-ink-muted font-bold uppercase block mb-1">Канал доставки</label>
              <div className="flex gap-2">
                {(['email', 'telegram'] as const).map(ch => (
                  <button
                    key={ch}
                    onClick={() => {
                      setChannel(ch);
                      setRecipient('');
                    }}
                    className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold border transition-all ${
                      channel === ch 
                        ? 'bg-blue-50 border-blue-500 text-blue-700' 
                        : 'bg-surface-2 border-line text-ink-secondary hover:bg-state-hover'
                    }`}
                  >
                    {ch === 'email' ? 'Email' : 'Telegram'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-ink-muted font-bold uppercase block mb-1">Получатель</label>
              <input
                type="text"
                placeholder={channel === 'email' ? 'client@example.com' : channel === 'telegram' ? 'ID чата Telegram' : 'client@example.com или ID чата'}
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="w-full bg-surface-2 border border-line rounded-lg px-3 py-2 text-xs text-ink-primary outline-none focus:border-accent-primary font-sans"
              />
            </div>

            {error && <InlineAlert type="danger" message={error} />}
            {sendResult && <InlineAlert type="success" message={sendResult} />}

            <ActionButton
              variant="primary"
              icon="paper-plane"
              onClick={handleSend}
              loading={sending}
              className="w-full justify-center py-2"
            >
              Отправить счет клиенту
            </ActionButton>
          </div>
        </div>

        {/* Delivery Logs */}
        <div className="space-y-2 pt-4 border-t border-line-subtle">
          <span className="text-[10px] text-ink-muted font-bold uppercase tracking-wider block">История отправок</span>
          {deliveryLogs.length === 0 ? (
            <div className="text-[10px] text-ink-muted italic py-4 text-center">
              Счет еще не отправлялся.
            </div>
          ) : (
            <div className="max-h-[180px] overflow-y-auto space-y-2 pr-1">
              {deliveryLogs.map((log) => (
                <div key={log.message_id} className="bg-surface-2 border border-line-subtle rounded-lg p-2.5 text-xs flex justify-between items-start">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-ink-secondary uppercase">{log.channel}</span>
                      <span className="text-[10px] text-ink-muted truncate w-32" title={log.recipient}>
                        {log.recipient}
                      </span>
                    </div>
                    {log.last_error && (
                      <span className="text-[10px] text-red-600 block">{log.last_error}</span>
                    )}
                    <span className="text-[9px] text-ink-muted block mt-0.5">
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
