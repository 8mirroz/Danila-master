import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { StatusBadge } from './Primitives';

type Request = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  created_at: string;
  parts_json: string;
  priority?: string;
  vehicle_make?: string;
  vehicle_model?: string;
};

type CompletedOrdersHistoryProps = {
  selectedRequestId: string | null;
  onSelectRequest: (req: Request) => void;
  fetchTrigger: number;
};

export const CompletedOrdersHistory = ({
  selectedRequestId,
  onSelectRequest,
  fetchTrigger,
}: CompletedOrdersHistoryProps) => {
  const [completedOrders, setCompletedOrders] = useState<Request[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/requests');
      if (res.ok) {
        const data: Request[] = await res.json();
        // Filter for completed/archived orders
        const completedStates = ['APPROVED', 'CANCELLED', 'INVOICE_DRAFTED', 'CLOSED', 'FULFILLED', 'PAID', 'CLIENT_REJECTED'];
        const filtered = data.filter((req) => completedStates.includes(req.status.toUpperCase()));

        // Sort newest first
        filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setCompletedOrders(filtered);
      }
    } catch (e) {
      console.error("Error fetching completed orders", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [fetchTrigger]);

  // Helper to format date groups
  const formatDateGroup = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  const formatYearGroup = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.getFullYear().toString();
  };

  // Group orders by date (YYYY-MM-DD)
  const groupedOrders: Record<string, Request[]> = {};
  completedOrders.forEach(order => {
    const dateKey = new Date(order.created_at).toISOString().split('T')[0];
    if (!groupedOrders[dateKey]) {
      groupedOrders[dateKey] = [];
    }
    groupedOrders[dateKey].push(order);
  });

  return (
    <div className="panel-card-tight p-5 flex flex-col h-[650px]">
      <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[var(--text-secondary)] border-b border-[var(--border-subtle)] pb-3">
        <i className="fas fa-archive text-[var(--accent-primary)]"></i> История завершенных заказов
      </h3>

      {loading ? (
        <div className="text-xs text-[var(--text-secondary)] py-12 text-center flex-1 flex flex-col items-center justify-center gap-2">
          <i className="fas fa-spinner animate-spin text-lg text-[var(--accent-primary)]"></i>
          <span>Загрузка истории...</span>
        </div>
      ) : completedOrders.length === 0 ? (
        <div className="text-xs text-[var(--text-muted)] py-12 text-center flex-1 flex items-center justify-center">
          История завершенных заказов пуста.
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto pr-1 space-y-6 relative custom-scrollbar">
          {Object.keys(groupedOrders).map((dateKey) => {
            const ordersInGroup = groupedOrders[dateKey];
            const firstOrder = ordersInGroup[0];
            const dateDisplay = formatDateGroup(firstOrder.created_at);
            const yearDisplay = formatYearGroup(firstOrder.created_at);

            return (
              <div key={dateKey} className="grid grid-cols-[80px_1fr] gap-4 relative">
                {/* Sticky Calendar Timeline Point */}
                <div className="sticky-calendar-card self-start flex flex-col items-center justify-center bg-gradient-to-b from-emerald-50 to-slate-100 border border-emerald-200/50 rounded-xl p-2.5 text-center shadow-sm w-[72px] h-[72px]">
                  <span className="text-[10px] uppercase font-bold text-emerald-800 tracking-wider">
                    {dateDisplay.split(' ')[1]}
                  </span>
                  <span className="text-2xl font-black text-slate-800 leading-none my-0.5">
                    {dateDisplay.split(' ')[0]}
                  </span>
                  <span className="text-[9px] font-semibold text-slate-400">
                    {yearDisplay}
                  </span>
                </div>

                {/* Vertical connecting line inside timeline */}
                <div className="absolute left-[35px] top-[74px] bottom-[-24px] w-[2px] bg-slate-200/60 z-0 hidden last:hidden sm:block"></div>

                {/* Compact orders list for this date */}
                <div className="space-y-3 z-10">
                  {ordersInGroup.map((order) => {
                    const isSelected = selectedRequestId === order.request_id;
                    let partsList = '';
                    try {
                      const parsed = JSON.parse(order.parts_json || '[]');
                      partsList = parsed.map((p: any) => p.name).join(', ');
                    } catch {
                      partsList = 'Детали не указаны';
                    }

                    return (
                      <article
                        key={order.id}
                        onClick={() => onSelectRequest(order)}
                        className={`border rounded-xl p-3.5 cursor-pointer transition-all shadow-sm flex flex-col gap-2 ${
                          isSelected
                            ? 'bg-[var(--surface-3)] border-[var(--accent-primary)] ring-1 ring-[var(--accent-primary)]'
                            : 'bg-[var(--surface-1)] border-[var(--border-default)] hover:border-[var(--text-muted)] hover:shadow-md'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h4 className="text-xs font-bold text-[var(--text-primary)] truncate">
                              {order.customer_name}
                            </h4>
                            <p className="text-[11px] text-[var(--text-secondary)] truncate mt-0.5 font-medium leading-relaxed">
                              {partsList}
                            </p>
                          </div>
                          <StatusBadge status={order.status} />
                        </div>

                        <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] border-t border-[var(--border-subtle)] pt-2 font-mono mt-1">
                          <span className="font-semibold">ID: {order.request_id}</span>
                          <span>
                            {new Date(order.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
