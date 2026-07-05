import React from 'react';
import { getStatusBadgeClasses, getStatusLabel } from '../lib/workflow';

// ==========================================
// 1. AppFrame
// ==========================================
export const AppFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="h-screen w-screen flex flex-col bg-[var(--bg-app)] text-[var(--text-primary)] overflow-hidden">
      {children}
    </div>
  );
};

// ==========================================
// 2. TopCommandBar
// ==========================================
interface TopCommandBarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
  envName?: string;
  erpSyncTime?: string;
  onResetActive?: () => void;
}
export const TopCommandBar: React.FC<TopCommandBarProps> = ({
  searchQuery,
  onSearchChange,
  envName = "Копия Production",
  erpSyncTime = "38 сек. назад",
  onResetActive,
}) => {
  return (
    <header className="col-span-full h-14 border-b border-[var(--border-default)] bg-[var(--surface-1)] px-4 flex items-center justify-between gap-4 z-50 shadow-sm">
      {/* Brand logo & title */}
      <div 
        className="flex items-center gap-3 cursor-pointer select-none"
        onClick={onResetActive}
      >
        <div className="w-8 h-8 rounded-md bg-[var(--accent-primary)] text-white flex items-center justify-center font-bold text-lg shadow-sm">
          <i className="fas fa-wave-square text-sm"></i>
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-[var(--text-primary)]">PartsOps AI Manager</h1>
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">Операционный пульт закупок</span>
        </div>
      </div>

      {/* Global Search Field */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <i className="fas fa-magnifying-glass absolute left-3 top-2.5 text-[var(--text-muted)] text-xs"></i>
          <input
            type="text"
            placeholder="Глобальный поиск (CMD + K для действий)..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-[var(--surface-2)] border border-[var(--border-default)] rounded-md pl-9 pr-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[var(--accent-primary)] transition-all font-sans"
          />
        </div>
      </div>

      {/* Env control & Health info */}
      <div className="flex items-center gap-4 text-xs">
        <div className="hidden md:flex flex-col text-right border-l border-[var(--border-default)] pl-4">
          <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Среда</span>
          <span className="font-semibold text-[var(--text-secondary)]">{envName}</span>
        </div>
        <div className="hidden md:flex flex-col text-right border-l border-[var(--border-default)] pl-4">
          <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">ERP Синхронизация</span>
          <span className="font-semibold text-[var(--text-secondary)]">{erpSyncTime}</span>
        </div>
      </div>
    </header>
  );
};

// ==========================================
// 3. LeftNavRail
// ==========================================
interface LeftNavRailProps {
  activeTab: string;
  onChangeTab: (tab: string) => void;
  items: Array<{ id: string; label: string; icon: string }>;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}
export const LeftNavRail: React.FC<LeftNavRailProps> = ({
  activeTab,
  onChangeTab,
  items,
  isCollapsed,
  onToggleCollapse,
}) => {
  return (
    <aside 
      className={`sidebar-glass flex flex-col justify-between overflow-y-auto transition-all duration-300 ease-in-out select-none flex-shrink-0 ${
        isCollapsed ? 'w-16' : 'w-60'
      }`}
    >
      <div className="py-4 px-3 flex flex-col gap-1">
        {/* Sidebar Header & Toggle */}
        <div className={`flex items-center mb-4 ${isCollapsed ? 'justify-center' : 'justify-between px-3'}`}>
          {!isCollapsed && (
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider animate-fadeIn">
              Рабочий стол
            </span>
          )}
          <button 
            onClick={onToggleCollapse}
            className="w-7 h-7 rounded-full bg-emerald-950/40 border border-emerald-800/30 hover:bg-emerald-800/20 hover:border-emerald-700/50 flex items-center justify-center text-xs text-slate-300 transition-all duration-200 shadow-sm hover:scale-105 active:scale-95"
            title={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            <i className={`fas ${isCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'} text-[10px]`}></i>
          </button>
        </div>

        {/* Menu Items */}
        {items.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChangeTab(item.id)}
              className={`relative group w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-semibold transition-all duration-200 text-left ${
                isActive
                  ? 'sidebar-button-glass-active shadow-sm'
                  : 'sidebar-button-glass-inactive hover:bg-white/5'
              }`}
            >
              {/* Active vertical line indicator */}
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-full bg-[#10b981] shadow-[0_0_8px_#10b981]" />
              )}
              
              <i 
                className={`fas ${item.icon} w-4 text-center text-sm transition-transform duration-200 group-hover:scale-110 ${
                  isActive ? 'text-[#10b981]' : 'text-slate-400 group-hover:text-white'
                }`}
              />

              {!isCollapsed && (
                <span className="animate-fadeIn">{item.label}</span>
              )}

              {/* Premium Glassmorphism Tooltip for Collapsed State */}
              {isCollapsed && (
                <div className="absolute left-16 px-3 py-1.5 rounded-md bg-emerald-950/95 backdrop-blur-md text-emerald-100 text-[11px] font-bold tracking-wide border border-emerald-800/80 shadow-[0_4px_12px_rgba(4,47,31,0.4)] opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 translate-x-2 group-hover:translate-x-0 whitespace-nowrap z-50 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Sidebar Footer info */}
      {isCollapsed ? (
        <div className="p-4 border-t border-emerald-800/20 flex flex-col items-center gap-3 text-xs text-slate-400">
          <div title="ID Оператора: OP-4819" className="hover:text-white transition-colors cursor-help">
            <i className="fas fa-user-shield text-[13px]"></i>
          </div>
          <div title="Версия системы: v6.0.4" className="hover:text-white transition-colors cursor-help">
            <i className="fas fa-code-fork text-[13px]"></i>
          </div>
        </div>
      ) : (
        <div className="p-4 border-t border-emerald-800/20 text-[10px] text-slate-400 space-y-1.5 bg-emerald-950/20">
          <div className="flex justify-between">
            <span>ID Оператора:</span>
            <span className="font-semibold text-slate-300">OP-4819</span>
          </div>
          <div className="flex justify-between">
            <span>Версия системы:</span>
            <span className="font-semibold text-slate-300">v6.0.4</span>
          </div>
        </div>
      )}
    </aside>
  );
};

// ==========================================
// 4. RightQueueRail
// ==========================================
export const RightQueueRail: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <aside className="border-l border-[var(--border-default)] bg-[var(--surface-1)] flex flex-col h-full overflow-hidden">
      {children}
    </aside>
  );
};

// ==========================================
// 5. WorkspaceHeader
// ==========================================
interface WorkspaceHeaderProps {
  title: string;
  requestId: string;
  status: string;
  priority?: string;
  customerName?: string;
  customerPhone?: string;
  customerEmail?: string;
  vin?: string;
  vehicleMake?: string;
  vehicleModel?: string;
  onBack?: () => void;
}
export const WorkspaceHeader: React.FC<WorkspaceHeaderProps> = ({
  title,
  requestId,
  status,
  priority = "Normal",
  customerName,
  customerPhone,
  customerEmail,
  vin,
  vehicleMake,
  vehicleModel,
  onBack,
}) => {
  return (
    <div className="panel-card-tight mb-4 flex flex-col gap-3 p-4">
      {/* Top inline control bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="rounded-full border border-[var(--border-default)] bg-[var(--surface-2)] px-2.5 py-1 font-mono text-[10px] font-semibold text-[var(--text-secondary)] shrink-0">
            {requestId}
          </span>
          <h2 className="text-sm font-bold text-[var(--text-primary)] truncate max-w-[280px] md:max-w-[450px]">
            {title || customerName || "Постоянный клиент"}
          </h2>
          <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase shrink-0 ${
            priority.toLowerCase() === 'high' || priority.toLowerCase() === 'urgent'
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-slate-100 text-slate-700 border border-slate-200'
          }`}>
            {priority === 'high' || priority === 'Высокий' ? 'Высокий' : priority === 'urgent' || priority === 'Срочный' ? 'Срочный' : 'Обычный'}
          </span>
          {vehicleMake && (
            <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded font-medium shrink-0">
              <i className="fas fa-car mr-1 text-[9px]"></i>
              {vehicleMake} {vehicleModel || ''}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* AI Telemetry Badge (Inline stats) */}
          <div className="hidden lg:flex items-center gap-3 bg-[var(--surface-2)] border border-[var(--border-default)] px-2.5 py-0.5 rounded-md text-[10px] font-medium text-[var(--text-secondary)]">
            <span className="flex items-center gap-1 font-semibold text-[var(--accent-primary)]">
              <i className="fas fa-robot text-[9px]"></i> PartsOps-AI
            </span>
            <span className="text-[var(--border-strong)]">|</span>
            <span>Модель: <strong className="text-[var(--text-primary)]">Gemini 3.5</strong></span>
            <span className="text-[var(--border-strong)]">|</span>
            <span className="flex items-center gap-1">
              Уверенность: <strong className="text-green-600">94%</strong>
            </span>
            <span className="text-[var(--border-strong)]">|</span>
            <span>Задержка: <strong className="text-[var(--text-primary)]">1.2s</strong></span>
          </div>

          <StatusBadge status={status} />
          {onBack && (
            <button 
              onClick={onBack}
            className="flex shrink-0 items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--surface-1)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] transition-all hover:bg-[var(--surface-2)]"
            >
              <i className="fas fa-arrow-left text-[10px]"></i> Закрыть
            </button>
          )}
        </div>
      </div>

      {/* Second Line: Sub-metadata row (Contacts, VIN, dynamic details) */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-2 border-t border-[var(--border-subtle)] text-[11px] text-[var(--text-secondary)]">
        {/* Contact list */}
        <div className="flex items-center gap-3 text-[var(--text-muted)]">
          {customerEmail && (
            <span className="flex items-center gap-1">
              <i className="fas fa-envelope text-[10px]"></i>
              <span className="text-[var(--text-secondary)] font-medium">{customerEmail}</span>
            </span>
          )}
          {customerPhone && (
            <span className="flex items-center gap-1">
              <i className="fas fa-phone text-[10px]"></i>
              <span className="text-[var(--text-secondary)] font-medium">{customerPhone}</span>
            </span>
          )}
        </div>

        {/* VIN */}
        {vin && (
          <div className="flex items-center gap-1 font-mono text-[10px] text-[var(--text-muted)] bg-[var(--surface-2)] px-1.5 py-0.5 rounded border border-[var(--border-subtle)]">
            <span className="font-sans uppercase text-[9px] font-bold text-[var(--text-muted)]">VIN</span>
            <span className="text-[var(--text-secondary)] font-semibold">{vin}</span>
          </div>
        )}

        {/* Small screen telemetry fallback */}
        <div className="lg:hidden flex items-center gap-2 text-[10px]">
          <span className="font-semibold text-[var(--text-primary)] bg-slate-100 px-1.5 py-0.5 rounded">AI: Gemini 3.5 (94%)</span>
        </div>
      </div>
    </div>
  );
};

// ==========================================
// 6. SectionCard
// ==========================================
interface SectionCardProps {
  title?: string;
  icon?: string;
  headerActions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}
export const SectionCard: React.FC<SectionCardProps> = ({
  title,
  icon,
  headerActions,
  children,
  className = "",
}) => {
  return (
    <section className={`panel-card-tight overflow-hidden flex flex-col ${className}`}>
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-[var(--border-default)] px-5 py-4">
          <div className="flex items-center gap-2">
            {icon && <i className={`fas ${icon} text-[12px] text-[var(--accent-primary)]`}></i>}
            <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--text-secondary)]">{title}</h3>
          </div>
          {headerActions && <div>{headerActions}</div>}
        </div>
      )}
      <div className="flex-1 p-5">{children}</div>
    </section>
  );
};

// ==========================================
// 7. SubnavPills
// ==========================================
interface SubnavPillsProps {
  activeTab: string;
  onChangeTab: (id: any) => void;
  tabs: Array<{ id: string; label: string; icon: string; badge?: string }>;
}
export const SubnavPills: React.FC<SubnavPillsProps> = ({
  activeTab,
  onChangeTab,
  tabs,
}) => {
  return (
    <div className="flex items-center border border-[var(--border-default)] bg-[var(--surface-1)] p-1 rounded-lg gap-1 shadow-sm">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChangeTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 py-1.5 px-3 rounded-md text-xs font-semibold transition-all ${
              isActive
                ? 'bg-[var(--state-selected)] text-[var(--accent-primary)] border border-blue-200'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-2)] border border-transparent'
            }`}
          >
            <i className={`fas ${tab.icon} text-xs`}></i>
            <span>{tab.label}</span>
            {tab.badge && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-700">
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

// ==========================================
// 8. DataTable
// ==========================================
interface DataTableProps {
  headers: string[];
  children: React.ReactNode;
}
export const DataTable: React.FC<DataTableProps> = ({ headers, children }) => {
  return (
    <div className="w-full overflow-x-auto rounded-[18px] border border-[var(--border-default)] bg-[var(--surface-1)]">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-[var(--border-default)] bg-[var(--surface-2)] text-[var(--text-secondary)] font-semibold select-none">
            {headers.map((h, idx) => (
              <th key={idx} className="px-4 py-3 uppercase tracking-[0.14em] text-[10px]">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {children}
        </tbody>
      </table>
    </div>
  );
};

// ==========================================
// 9. MetricTile
// ==========================================
interface MetricTileProps {
  label: string;
  value: string | number;
  delta?: string;
  tone?: 'emerald' | 'amber' | 'cyan' | 'violet' | 'danger' | 'neutral';
}
export const MetricTile: React.FC<MetricTileProps> = ({
  label,
  value,
  delta,
  tone = 'neutral',
}) => {
  const getToneClasses = () => {
    switch (tone) {
      case 'emerald': return 'bg-green-50 text-green-700 border-green-200';
      case 'amber': return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'cyan': return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'violet': return 'bg-sky-50 text-sky-700 border-sky-200';
      case 'danger': return 'bg-red-50 text-red-700 border-red-200';
      default: return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="panel-card-tight min-h-[108px] overflow-hidden p-4">
      <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">{label}</span>
      <div className="mt-4 flex items-end justify-between gap-2">
        <strong className="text-[32px] font-bold tracking-[-0.04em] text-[var(--text-primary)]">{value}</strong>
        {delta && (
          <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${getToneClasses()}`}>
            {delta}
          </span>
        )}
      </div>
    </div>
  );
};

// ==========================================
// 10. StatusBadge
// ==========================================
export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${getStatusBadgeClasses(status)}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      {getStatusLabel(status)}
    </span>
  );
};

// ==========================================
// 11. ActionButton
// ==========================================
interface ActionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'success';
  icon?: string;
  loading?: boolean;
}
export const ActionButton: React.FC<ActionButtonProps> = ({
  variant = 'secondary',
  icon,
  loading = false,
  children,
  className = "",
  disabled,
  ...props
}) => {
  const getVariantClass = () => {
    if (disabled) return 'cursor-not-allowed border-[var(--border-default)] bg-slate-100 text-slate-400';
    switch (variant) {
      case 'primary': return 'border-transparent bg-[var(--accent-primary)] text-white shadow-sm hover:bg-[var(--accent-primary-strong)]';
      case 'danger': return 'border-transparent bg-[var(--accent-danger)] text-white hover:bg-red-700';
      case 'success': return 'border-transparent bg-[var(--accent-success)] text-white hover:bg-emerald-700';
      default: return 'border-[var(--border-default)] bg-[var(--surface-1)] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]';
    }
  };

  return (
    <button
      disabled={disabled || loading}
      className={`flex items-center justify-center gap-1.5 rounded-[16px] border px-4 py-2.5 text-xs font-semibold transition-all ${getVariantClass()} ${className}`}
      {...props}
    >
      {loading ? (
        <i className="fas fa-spinner animate-spin text-xs"></i>
      ) : icon ? (
        <i className={`fas ${icon} text-xs`}></i>
      ) : null}
      <span>{children}</span>
    </button>
  );
};

// ==========================================
// 12. SearchField
// ==========================================
interface SearchFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  placeholder?: string;
}
export const SearchField: React.FC<SearchFieldProps> = ({
  placeholder = "Поиск...",
  className = "",
  value,
  onChange,
  ...props
}) => {
  return (
    <div className={`relative ${className}`}>
      <i className="fas fa-magnifying-glass absolute left-3 top-2.5 text-[var(--text-muted)] text-xs"></i>
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        className="w-full rounded-[16px] border border-[var(--border-default)] bg-[var(--surface-1)] pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none transition-all focus:border-[var(--accent-primary)] font-sans"
        {...props}
      />
    </div>
  );
};

// ==========================================
// 13. Dropzone
// ==========================================
interface DropzoneProps {
  title: string;
  description: string;
  onImport: (text: string) => void;
  acceptLabel?: string;
}
export const Dropzone: React.FC<DropzoneProps> = ({
  title,
  description,
  onImport,
  acceptLabel = "Разрешены файлы JSON или TXT",
}) => {
  const [dragActive, setDragActive] = React.useState(false);
  const [pasteText, setPasteText] = React.useState('');

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          onImport(event.target.result as string);
        }
      };
      reader.readAsText(file);
    }
  };

  return (
    <div className="flex flex-col gap-4 text-xs">
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
          dragActive
            ? 'border-[var(--accent-primary)] bg-blue-50/50'
            : 'border-[var(--border-strong)] hover:border-[var(--text-muted)] bg-[var(--surface-2)]'
        }`}
      >
        <i className="fas fa-cloud-arrow-up text-2xl text-[var(--text-muted)] mb-3"></i>
        <strong className="text-xs text-[var(--text-primary)] font-semibold block mb-1">{title}</strong>
        <p className="text-[11px] text-[var(--text-secondary)] max-w-xs leading-relaxed">{description}</p>
        <span className="text-[9px] text-[var(--text-muted)] font-mono mt-3 uppercase tracking-wider block">{acceptLabel}</span>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold block">Или вставьте сырой текст</label>
        <textarea
          rows={4}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="Вставьте JSON поставщиков или текст запроса клиента..."
          className="w-full border border-[var(--border-default)] rounded-md p-2.5 bg-[var(--surface-1)] text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] font-mono"
        />
        <ActionButton 
          variant="primary" 
          icon="fa-paper-plane"
          disabled={!pasteText.trim()}
          onClick={() => {
            onImport(pasteText);
            setPasteText('');
          }}
        >
          Распознать и обработать
        </ActionButton>
      </div>
    </div>
  );
};

// ==========================================
// 14. ReviewPanel
// ==========================================
interface ReviewItem {
  name: string;
  quantity: number;
}
interface ReviewPanelProps {
  items: ReviewItem[];
  onChange: (items: ReviewItem[]) => void;
  onConfirm: () => void;
}
export const ReviewPanel: React.FC<ReviewPanelProps> = ({
  items,
  onChange,
  onConfirm,
}) => {
  const [editingIndex, setEditingIndex] = React.useState<number | null>(null);
  const [editName, setEditName] = React.useState('');
  const [editQty, setEditQty] = React.useState(1);
  const [newName, setNewName] = React.useState('');
  const [newQty, setNewQty] = React.useState(1);

  const startEdit = (idx: number, item: ReviewItem) => {
    setEditingIndex(idx);
    setEditName(item.name);
    setEditQty(item.quantity);
  };

  const saveEdit = (idx: number) => {
    const updated = [...items];
    updated[idx] = { name: editName, quantity: editQty };
    onChange(updated);
    setEditingIndex(null);
  };

  const deleteItem = (idx: number) => {
    const updated = items.filter((_, i) => i !== idx);
    onChange(updated);
  };

  const addItem = () => {
    if (!newName.trim()) return;
    onChange([...items, { name: newName, quantity: newQty }]);
    setNewName('');
    setNewQty(1);
  };

  return (
    <div className="flex flex-col gap-4 text-xs">
      <div className="border border-[var(--border-default)] rounded-lg overflow-hidden bg-[var(--surface-1)] shadow-sm">
        <div className="bg-[var(--surface-2)] border-b border-[var(--border-default)] px-4 py-2 flex items-center justify-between font-bold text-[11px] text-[var(--text-secondary)] uppercase tracking-wider">
          <span>Список распознанных деталей</span>
          <span>найдено {items.length} дет.</span>
        </div>
        
        {items.length === 0 ? (
          <div className="p-6 text-center text-[var(--text-secondary)]">Детали не найдены. Пожалуйста, добавьте детали вручную.</div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {items.map((item, idx) => {
              const isEditing = editingIndex === idx;
              return (
                <div key={idx} className="p-3 flex items-center justify-between gap-3 hover:bg-[var(--surface-2)] transition-all">
                  {isEditing ? (
                    <div className="flex-1 flex gap-2">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="flex-1 border border-[var(--border-strong)] rounded px-2 py-1 text-xs"
                      />
                      <input
                        type="number"
                        min="1"
                        value={editQty}
                        onChange={(e) => setEditQty(Number(e.target.value))}
                        className="w-16 border border-[var(--border-strong)] rounded px-2 py-1 text-xs"
                      />
                    </div>
                  ) : (
                    <div className="flex-1">
                      <div className="font-semibold text-[var(--text-primary)] text-sm">{item.name}</div>
                      <div className="text-[var(--text-secondary)] mt-0.5">Количество: <span className="font-semibold">{item.quantity}</span> шт.</div>
                    </div>
                  )}

                  <div className="flex items-center gap-1">
                    {isEditing ? (
                      <ActionButton variant="success" icon="fa-check" onClick={() => saveEdit(idx)} />
                    ) : (
                      <ActionButton icon="fa-pencil" onClick={() => startEdit(idx, item)} />
                    )}
                    <ActionButton icon="fa-trash text-red-500" onClick={() => deleteItem(idx)} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Manual part addition form */}
      <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-lg p-3 flex flex-col md:flex-row gap-3 items-end">
        <div className="flex-1 flex flex-col gap-1 w-full">
          <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Добавить деталь вручную</label>
          <input
            type="text"
            placeholder="например, Передние тормозные колодки OEM 34116852253"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="border border-[var(--border-default)] rounded-md px-2.5 py-1.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] bg-[var(--surface-1)]"
          />
        </div>
        <div className="w-full md:w-20 flex flex-col gap-1">
          <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold">Кол-во</label>
          <input
            type="number"
            min="1"
            value={newQty}
            onChange={(e) => setNewQty(Number(e.target.value))}
            className="border border-[var(--border-default)] rounded-md px-2.5 py-1.5 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] bg-[var(--surface-1)]"
          />
        </div>
        <ActionButton 
          variant="secondary" 
          icon="fa-plus" 
          disabled={!newName.trim()}
          onClick={addItem}
          className="w-full md:w-auto"
        >
          Добавить
        </ActionButton>
      </div>

      {/* Confirm Button */}
      <div className="flex justify-end pt-2 border-t border-[var(--border-subtle)]">
        <ActionButton variant="primary" icon="fa-square-check" onClick={onConfirm}>
          Подтвердить проверку и перейти к подбору
        </ActionButton>
      </div>
    </div>
  );
};

// ==========================================
// 15. SplitPane
// ==========================================
export const SplitPane: React.FC<{ left: React.ReactNode; right: React.ReactNode }> = ({ left, right }) => {
  return (
    <div className="grid grid-cols-[1fr_340px] h-full overflow-hidden">
      <div className="overflow-y-auto p-4">{left}</div>
      <div className="overflow-y-auto border-l border-[var(--border-default)] bg-[var(--surface-1)] p-4">{right}</div>
    </div>
  );
};

// ==========================================
// 16. EmptyState
// ==========================================
interface EmptyStateProps {
  title: string;
  description: string;
  icon?: string;
  actionNode?: React.ReactNode;
}
export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon = "fa-folder-open",
  actionNode,
}) => {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg min-h-[300px] shadow-sm select-none">
      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-4 text-[var(--text-muted)] text-xl border border-slate-200">
        <i className={`fas ${icon}`}></i>
      </div>
      <h3 className="text-sm font-bold text-[var(--text-primary)] block mb-1">{title}</h3>
      <p className="text-[11px] text-[var(--text-secondary)] max-w-xs leading-relaxed mb-4">{description}</p>
      {actionNode && <div>{actionNode}</div>}
    </div>
  );
};

// ==========================================
// 17. InlineAlert
// ==========================================
interface InlineAlertProps {
  message: string;
  type?: 'warning' | 'danger' | 'success' | 'info';
}
export const InlineAlert: React.FC<InlineAlertProps> = ({
  message,
  type = 'info',
}) => {
  const getAlertClasses = () => {
    switch (type) {
      case 'warning': return 'bg-amber-50 border-amber-200 text-amber-800 fa-exclamation-triangle';
      case 'danger': return 'bg-red-50 border-red-200 text-red-800 fa-radiation';
      case 'success': return 'bg-green-50 border-green-200 text-green-800 fa-circle-check';
      default: return 'bg-blue-50 border-blue-200 text-blue-800 fa-circle-info';
    }
  };

  const classes = getAlertClasses();

  return (
    <div className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 mb-4 shadow-sm ${classes.split(' ').slice(0, 3).join(' ')}`}>
      <i className={`fas ${classes.split(' ').slice(3).join(' ')} mt-0.5 text-sm`}></i>
      <span className="leading-normal font-medium">{message}</span>
    </div>
  );
};

// ==========================================
// 18. StepGate
// ==========================================
interface StepGateProps {
  currentStep: number;
  steps: string[];
  onStepClick?: (idx: number) => void;
}
export const StepGate: React.FC<StepGateProps> = ({
  currentStep,
  steps,
  onStepClick,
}) => {
  return (
    <div className="flex items-center w-full justify-between border border-[var(--border-default)] bg-[var(--surface-1)] p-2.5 rounded-lg mb-4 shadow-sm select-none">
      {steps.map((step, idx) => {
        const isCompleted = idx < currentStep;
        const isCurrent = idx === currentStep;
        const isClickable = onStepClick && idx <= currentStep; // can go backwards or switch to current

        return (
          <React.Fragment key={idx}>
            <div 
              onClick={() => isClickable && onStepClick && onStepClick(idx)}
              className={`flex items-center gap-2 px-2 py-1 rounded transition-all ${
                isClickable ? 'cursor-pointer hover:bg-slate-50' : 'cursor-default'
              }`}
            >
              {/* Circle Index Indicator */}
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all ${
                isCurrent 
                  ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)] shadow-sm'
                  : isCompleted 
                  ? 'bg-green-500 text-white border-green-500'
                  : 'bg-white text-[var(--text-muted)] border-[var(--border-strong)]'
              }`}>
                {isCompleted ? <i className="fas fa-check text-[8px]"></i> : idx + 1}
              </span>
              <span className={`text-[11px] font-semibold transition-all ${
                isCurrent ? 'text-[var(--accent-primary)] font-bold' : isCompleted ? 'text-green-700' : 'text-[var(--text-muted)]'
              }`}>
                {step}
              </span>
            </div>
            
            {/* Horizontal Line Connector */}
            {idx < steps.length - 1 && (
              <div className={`flex-1 h-[2px] mx-2 ${idx < currentStep ? 'bg-green-300' : 'bg-[var(--border-default)]'}`}></div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};
