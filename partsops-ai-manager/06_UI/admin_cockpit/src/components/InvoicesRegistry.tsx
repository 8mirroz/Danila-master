import React, { useState } from 'react';
import { ActionButton, SearchField, DataTable } from './Primitives';

type Invoice = {
  invoice_id: string;
  request_id: string;
  customer_name: string;
  total_price: number;
  created_at: string;
  status: string;
  order_status?: string;
};

const isOrderClosed = (status?: string) => {
  return ['CLOSED', 'CANCELLED', 'EXPIRED', 'FAILED', 'CLIENT_REJECTED'].includes(status ?? '');
};

const getOrderStage = (status?: string) => {
  if (!status) return 'Статус заказа не получен';
  if (isOrderClosed(status)) return 'Закрыт';
  return status;
};

interface InvoicesRegistryProps {
  invoices: Invoice[];
  onSelectRequest?: (requestId: string) => void;
}

export const InvoicesRegistry: React.FC<InvoicesRegistryProps> = ({
  invoices,
  onSelectRequest,
}) => {
  const [viewMode, setViewMode] = useState<'list' | 'folders' | 'grid'>('list');
  const [folderGroupBy, setFolderGroupBy] = useState<'customer' | 'status'>('customer');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterOrderType, setFilterOrderType] = useState<string>('all'); // all | open | closed
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc'>('date_desc');

  // 1. Statistics Calculations
  const totalBilled = invoices.reduce((sum, inv) => sum + inv.total_price, 0);
  const paidCount = invoices.filter(inv => inv.status === 'PAID').length;
  const paidSum = invoices.filter(inv => inv.status === 'PAID').reduce((sum, inv) => sum + inv.total_price, 0);
  const pendingCount = invoices.filter(inv => ['DRAFT', 'SENT'].includes(inv.status)).length;
  const pendingSum = invoices.filter(inv => ['DRAFT', 'SENT'].includes(inv.status)).reduce((sum, inv) => sum + inv.total_price, 0);
  const avgInvoiceAmount = invoices.length > 0 ? Math.round(totalBilled / invoices.length) : 0;

  // 2. Filter and Search logic
  const filteredInvoices = invoices.filter((inv) => {
    const matchesSearch =
      inv.invoice_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inv.request_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inv.customer_name.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = filterStatus === 'all' || inv.status === filterStatus;
    
    const isClosed = isOrderClosed(inv.order_status);
    const matchesOrderType =
      filterOrderType === 'all' ||
      (filterOrderType === 'open' && !isClosed) ||
      (filterOrderType === 'closed' && isClosed);

    return matchesSearch && matchesStatus && matchesOrderType;
  });

  // 3. Sorting logic
  const sortedInvoices = [...filteredInvoices].sort((a, b) => {
    if (sortBy === 'date_desc') {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
    if (sortBy === 'date_asc') {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    }
    if (sortBy === 'amount_desc') {
      return b.total_price - a.total_price;
    }
    if (sortBy === 'amount_asc') {
      return a.total_price - b.total_price;
    }
    return 0;
  });

  // Helper for status classes
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'PAID':
        return 'bg-green-50 border-green-200 text-green-700';
      case 'SENT':
        return 'bg-blue-50 border-blue-200 text-blue-700';
      case 'DRAFT':
        return 'bg-amber-50 border-amber-200 text-amber-700';
      case 'CLOSED':
        return 'bg-slate-100 border-slate-200 text-slate-700';
      default:
        return 'bg-slate-50 border-slate-100 text-slate-600';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'PAID': return 'Оплачен';
      case 'SENT': return 'Отправлен';
      case 'DRAFT': return 'Черновик';
      case 'CLOSED': return 'Закрыт';
      default: return status;
    }
  };

  // Group into folders logic
  const renderFolders = () => {
    const groups: Record<string, Invoice[]> = {};
    
    sortedInvoices.forEach(inv => {
      const key = folderGroupBy === 'customer' ? inv.customer_name : getStatusLabel(inv.status);
      if (!groups[key]) groups[key] = [];
      groups[key].push(inv);
    });

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {Object.entries(groups).map(([groupName, groupInvoices]) => (
          <div key={groupName} className="border border-[var(--border-default)] rounded-lg p-4 bg-[var(--surface-1)] shadow-sm hover:shadow transition-all">
            <div className="flex items-center gap-3 mb-3 border-b border-[var(--border-subtle)] pb-2.5">
              <div className="w-10 h-10 rounded bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-500 text-lg">
                <i className="fas fa-folder-open"></i>
              </div>
              <div>
                <h4 className="text-xs font-bold text-[var(--text-primary)] truncate max-w-[160px]">{groupName}</h4>
                <span className="text-[10px] text-[var(--text-muted)] font-semibold">{groupInvoices.length} документов</span>
              </div>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar pr-1">
              {groupInvoices.map(inv => (
                <div 
                  key={inv.invoice_id}
                  className="flex justify-between items-center text-[10px] p-2 hover:bg-[var(--surface-2)] rounded border border-[var(--border-subtle)] transition-all cursor-pointer"
                  onClick={() => onSelectRequest && onSelectRequest(inv.request_id)}
                >
                  <div className="font-mono font-bold text-[var(--accent-primary)]">{inv.invoice_id}</div>
                  <div className="font-bold text-[var(--text-primary)]">{inv.total_price.toLocaleString()} ₽</div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {Object.keys(groups).length === 0 && (
          <div className="col-span-full py-10 text-center text-xs text-[var(--text-muted)] italic">
            Нет доступных папок с документами
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* 1. Statistics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg p-3.5 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold block mb-1">Всего выставлено</span>
          <div className="text-lg font-black text-[var(--text-primary)]">{totalBilled.toLocaleString()} ₽</div>
          <span className="text-[10px] text-[var(--text-secondary)] font-medium mt-1 block">{invoices.length} счетов</span>
        </div>
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg p-3.5 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold block mb-1">Оплачено счетов</span>
          <div className="text-lg font-black text-[var(--accent-success)]">{paidSum.toLocaleString()} ₽</div>
          <span className="text-[10px] text-[var(--text-secondary)] font-medium mt-1 block">{paidCount} документов</span>
        </div>
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg p-3.5 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold block mb-1">В ожидании оплаты</span>
          <div className="text-lg font-black text-[var(--accent-warning)]">{pendingSum.toLocaleString()} ₽</div>
          <span className="text-[10px] text-[var(--text-secondary)] font-medium mt-1 block">{pendingCount} черновиков/отправленных</span>
        </div>
        <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg p-3.5 shadow-sm">
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold block mb-1">Средний чек</span>
          <div className="text-lg font-black text-[var(--accent-info)]">{avgInvoiceAmount.toLocaleString()} ₽</div>
          <span className="text-[10px] text-[var(--text-secondary)] font-medium mt-1 block">на один коммерческий пакет</span>
        </div>
      </div>

      {/* 2. Controls, Search and Filtering Registry Panel */}
      <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg p-4 shadow-sm space-y-3.5">
        <div className="flex flex-col md:flex-row justify-between items-stretch md:items-center gap-3">
          
          {/* View Modes switcher */}
          <div className="flex items-center gap-1.5 bg-[var(--surface-2)] p-1 rounded-md border border-[var(--border-default)] self-start">
            <button 
              onClick={() => setViewMode('list')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${viewMode === 'list' ? 'bg-[var(--surface-1)] text-[var(--accent-primary)] shadow-sm' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
            >
              <i className="fas fa-list-ul mr-1"></i> Список
            </button>
            <button 
              onClick={() => setViewMode('folders')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${viewMode === 'folders' ? 'bg-[var(--surface-1)] text-[var(--accent-primary)] shadow-sm' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
            >
              <i className="fas fa-folder mr-1"></i> Папки
            </button>
            <button 
              onClick={() => setViewMode('grid')}
              className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${viewMode === 'grid' ? 'bg-[var(--surface-1)] text-[var(--accent-primary)] shadow-sm' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
            >
              <i className="fas fa-grip-horizontal mr-1"></i> Плитка
            </button>
          </div>

          {/* Search bar */}
          <div className="flex-1 max-w-sm">
            <SearchField 
              placeholder="Поиск счета, клиента, ID заказа..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full"
            />
          </div>

          {/* Sort selection */}
          <div className="flex items-center gap-2">
            <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Сортировка</label>
            <select
              value={sortBy}
              onChange={(e: any) => setSortBy(e.target.value)}
              className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded px-2.5 py-1.5 text-xs outline-none text-[var(--text-primary)]"
            >
              <option value="date_desc">Сначала новые</option>
              <option value="date_asc">Сначала старые</option>
              <option value="amount_desc">По убыванию цены</option>
              <option value="amount_asc">По возрастанию цены</option>
            </select>
          </div>
        </div>

        {/* 3. Detailed Filters row */}
        <div className="flex flex-wrap items-center gap-4 bg-[var(--surface-2)] p-2.5 rounded border border-[var(--border-default)] text-xs">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Статус счёта:</span>
            <div className="flex gap-1">
              {['all', 'DRAFT', 'SENT', 'PAID'].map((status) => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={`px-2 py-0.5 rounded border font-medium text-[10px] transition-all ${
                    filterStatus === status 
                      ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]' 
                      : 'bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-slate-50'
                  }`}
                >
                  {status === 'all' ? 'Все' : getStatusLabel(status)}
                </button>
              ))}
            </div>
          </div>

          <div className="h-4 w-px bg-slate-300"></div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Заказ:</span>
            <div className="flex gap-1">
              {[
                { id: 'all', label: 'Все' },
                { id: 'open', label: 'Открытые' },
                { id: 'closed', label: 'Закрытые/В архиве' }
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setFilterOrderType(t.id)}
                  className={`px-2 py-0.5 rounded border font-medium text-[10px] transition-all ${
                    filterOrderType === t.id 
                      ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]' 
                      : 'bg-[var(--surface-1)] border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-slate-50'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {viewMode === 'folders' && (
            <>
              <div className="h-4 w-px bg-slate-300"></div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider">Группировка:</span>
                <select
                  value={folderGroupBy}
                  onChange={(e: any) => setFolderGroupBy(e.target.value)}
                  className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded px-1.5 py-0.5 text-[10px] font-bold outline-none"
                >
                  <option value="customer">По клиентам</option>
                  <option value="status">По статусам</option>
                </select>
              </div>
            </>
          )}
        </div>

        {/* 4. Document Render Section based on selected view mode */}
        <div className="pt-2">
          {viewMode === 'list' && (
            <DataTable headers={["Номер счёта", "ID Заказа", "Имя клиента", "Стадия заказа", "Итоговая сумма", "Дата создания", "Статус счёта"]}>
              {sortedInvoices.map((inv) => (
                <tr 
                  key={inv.invoice_id} 
                  className="border-b border-[var(--border-subtle)] hover:bg-[var(--surface-2)] transition-all text-xs cursor-pointer"
                  onClick={() => onSelectRequest && onSelectRequest(inv.request_id)}
                >
                  <td className="px-4 py-3 font-mono font-bold text-[var(--accent-primary)]">{inv.invoice_id}</td>
                  <td className="px-4 py-3 font-mono font-semibold">{inv.request_id}</td>
                  <td className="px-4 py-3 font-bold">{inv.customer_name}</td>
                  <td className="px-4 py-3 font-semibold text-[var(--text-secondary)]">
                    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${isOrderClosed(inv.order_status) ? 'bg-slate-400' : inv.order_status ? 'bg-green-500' : 'bg-amber-400'}`}></span>
                    {getOrderStage(inv.order_status)}
                  </td>
                  <td className="px-4 py-3 font-black">{inv.total_price.toLocaleString()} ₽</td>
                  <td className="px-4 py-3 text-[var(--text-muted)]">{new Date(inv.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadgeClass(inv.status)}`}>
                      {getStatusLabel(inv.status)}
                    </span>
                  </td>
                </tr>
              ))}
              {sortedInvoices.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-[var(--text-muted)] italic text-xs">
                    Счета не найдены по заданным критериям фильтрации
                  </td>
                </tr>
              )}
            </DataTable>
          )}

          {viewMode === 'folders' && renderFolders()}

          {viewMode === 'grid' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {sortedInvoices.map((inv) => {
                const isClosed = isOrderClosed(inv.order_status);
                return (
                  <div key={inv.invoice_id} className="border border-[var(--border-default)] rounded-lg p-3 bg-[var(--surface-1)] shadow-sm hover:shadow-md transition-all flex flex-col justify-between gap-3 h-52 relative group">
                    <div className="absolute top-2 right-2">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${getStatusBadgeClass(inv.status)}`}>
                        {getStatusLabel(inv.status)}
                      </span>
                    </div>

                    {/* PDF Document Visual Representation */}
                    <div className="flex-1 flex gap-3.5 items-start">
                      <div className="w-12 h-16 rounded border border-red-200 bg-red-50/50 flex flex-col justify-between p-1.5 shadow-sm text-center shrink-0 group-hover:bg-red-50 transition-all select-none">
                        <span className="text-[7px] text-red-500 font-extrabold uppercase leading-none">PDF</span>
                        <i className="fas fa-file-pdf text-red-500 text-lg"></i>
                        <span className="text-[6px] text-slate-400 font-mono font-bold leading-none truncate">{inv.invoice_id.slice(-5)}</span>
                      </div>
                      <div className="space-y-1.5 min-w-0">
                        <h4 className="text-xs font-black text-[var(--text-primary)] truncate font-mono">{inv.invoice_id}</h4>
                        <p className="text-[10px] text-[var(--text-muted)] truncate font-medium">{inv.customer_name}</p>
                        <p className="text-[9px] text-[var(--text-secondary)] font-bold">
                          Заказ: <span className="font-mono">{inv.request_id}</span>
                        </p>
                        <p className="text-[9px] text-[var(--text-muted)] font-semibold">
                          Стадия: <span className={`font-bold ${isClosed ? 'text-slate-600' : inv.order_status ? 'text-green-600' : 'text-amber-600'}`}>{getOrderStage(inv.order_status)}</span>
                        </p>
                      </div>
                    </div>

                    <div className="border-t border-[var(--border-subtle)] pt-2.5 flex justify-between items-center">
                      <span className="text-xs font-black text-[var(--text-primary)]">{inv.total_price.toLocaleString()} ₽</span>
                      <ActionButton 
                        variant="secondary" 
                        icon="fa-eye" 
                        className="py-1 px-2.5 text-[9px] font-bold"
                        onClick={() => onSelectRequest && onSelectRequest(inv.request_id)}
                      >
                        Просмотреть
                      </ActionButton>
                    </div>
                  </div>
                );
              })}
              {sortedInvoices.length === 0 && (
                <div className="col-span-full py-10 text-center text-xs text-[var(--text-muted)] italic">
                  Счета не найдены по заданным критериям фильтрации
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
