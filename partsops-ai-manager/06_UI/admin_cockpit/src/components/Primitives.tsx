import React from 'react';
import { gsap } from 'gsap';
import {
  Archive,
  ArrowCounterClockwise,
  ArrowLeft,
  ArrowRight,
  ArrowsClockwise,
  ArrowsOut,
  Barcode,
  Bell,
  BookOpen,
  Brain,
  Bug,
  Calculator,
  Car,
  CaretDown,
  CaretLeft,
  CaretRight,
  CaretUp,
  ChartLine,
  ChartPie,
  ChatCircle,
  Check,
  CheckCircle,
  ClipboardText,
  Clock,
  CloudArrowUp,
  Columns,
  Cpu,
  Cube,
  CurrencyDollar,
  DownloadSimple,
  Envelope,
  Eye,
  File as FileIcon,
  FileCode,
  FilePdf,
  FileText,
  FlowArrow,
  Folder,
  FolderOpen,
  Funnel,
  Gauge,
  Gear,
  GitBranch,
  Graph,
  GridFour,
  Info,
  Keyboard,
  Lightning,
  Link,
  List,
  ListChecks,
  Lock,
  LockOpen,
  MagicWand,
  MagnifyingGlass,
  MicrosoftExcelLogo,
  Minus,
  Package,
  PaperPlaneRight,
  Paperclip,
  Path,
  Pause,
  PenNib,
  PencilSimple,
  Phone,
  Play,
  Plus,
  Pulse,
  Receipt,
  Robot,
  Scales,
  ShieldCheck,
  ShoppingCart,
  Shuffle,
  SpinnerGap,
  Stop,
  Table,
  Terminal,
  Trash,
  Tray,
  TreeStructure,
  Truck,
  UploadSimple,
  User,
  UserCheck,
  Warning,
  WarningDiamond,
  Waveform,
  X,
  XCircle,
  type Icon as PhosphorIcon,
} from '@phosphor-icons/react';
import { getStatusBadgeClasses, getStatusLabel, getTrafficLight, getTrafficLightLabel } from '../lib/workflow';
import { useFocusTrap, useKeydown } from '../lib/focus';
import { useUIMode } from '../lib/useUIMode';
import { LottieMotion } from './LottieMotion';

export const UIModeSwitcher: React.FC = () => {
  const { isAutopilot, toggle } = useUIMode();
  return (
    <button
      type="button"
      onClick={toggle}
      title="Переключить режим интерфейса (Shift + D)"
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold transition-all duration-200 active:scale-95 ${
        isAutopilot
          ? 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
          : 'border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100'
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${isAutopilot ? 'bg-emerald-500 animate-pulse' : 'bg-blue-600'}`} />
      <span>{isAutopilot ? 'Автопилот' : 'Режим Эксперт'}</span>
      <span className="hidden sm:inline-block font-mono text-[9px] opacity-70 bg-black/5 px-1 rounded">Shift+D</span>
    </button>
  );
};

// =========================================
// 0. Icon system (typed, Phosphor + FA aliases)
// =========================================
const ICON_MAP = {
  // Core / nav
  'wave-square': Waveform,
  'magnifying-glass': MagnifyingGlass,
  search: MagnifyingGlass,
  'magnifying-glass-chart': MagnifyingGlass,
  'chevron-left': CaretLeft,
  'chevron-right': CaretRight,
  'chevron-up': CaretUp,
  'chevron-down': CaretDown,
  'arrow-left': ArrowLeft,
  'arrow-right': ArrowRight,
  'arrow-rotate-right': ArrowsClockwise,
  rotate: ArrowsClockwise,
  'arrows-rotate': ArrowsClockwise,
  sync: ArrowsClockwise,
  'sync-alt': ArrowsClockwise,
  'rotate-left': ArrowCounterClockwise,
  spinner: SpinnerGap,
  'circle-notch': SpinnerGap,
  stop: Stop,
  play: Play,
  pause: Pause,
  clock: Clock,
  minus: Minus,
  plus: Plus,
  list: List,
  'list-ul': List,
  'list-check': ListChecks,
  'grip-horizontal': GridFour,
  download: DownloadSimple,
  upload: UploadSimple,
  archive: Archive,
  keyboard: Keyboard,
  terminal: Terminal,
  eye: Eye,
  user: User,
  'user-check': UserCheck,
  'user-shield': ShieldCheck,
  car: Car,
  robot: Robot,
  microchip: Cpu,
  brain: Brain,
  cpu: Cpu,
  envelope: Envelope,
  phone: Phone,
  paperclip: Paperclip,
  'paper-plane': PaperPlaneRight,
  pencil: PencilSimple,
  trash: Trash,
  'trash-can': Trash,
  check: Check,
  'check-circle': CheckCircle,
  'square-check': CheckCircle,
  'circle-check': CheckCircle,
  'x-mark': X,
  times: X,
  xmark: X,
  'circle-xmark': XCircle,
  'exclamation-triangle': Warning,
  'triangle-exclamation': Warning,
  warning: Warning,
  radiation: WarningDiamond,
  'circle-info': Info,
  info: Info,
  shield: ShieldCheck,
  'shield-halved': ShieldCheck,
  'shield-check': ShieldCheck,
  'file-shield': ShieldCheck,
  lock: Lock,
  'lock-open': LockOpen,
  link: Link,
  barcode: Barcode,
  table: Table,
  'table-list': Table,
  'table-columns': Columns,
  folder: Folder,
  'folder-open': FolderOpen,
  'book-open': BookOpen,
  bell: Bell,
  inbox: Tray,
  tray: Tray,
  funnel: Funnel,
  // Files / docs
  'cloud-arrow-up': CloudArrowUp,
  'file-arrow-up': CloudArrowUp,
  'file-import': CloudArrowUp,
  'file-lines': FileText,
  document: FileText,
  'file-invoice': Receipt,
  'file-invoice-dollar': Receipt,
  'file-signature': PenNib,
  'file-code': FileCode,
  'file-pdf': FilePdf,
  'file-excel': MicrosoftExcelLogo,
  'file-csv': FileText,
  receipt: Receipt,
  // Commerce / ops
  calculator: Calculator,
  'clipboard-check': ClipboardText,
  'money-bill-wave': CurrencyDollar,
  'cart-shopping': ShoppingCart,
  'box-check': Package,
  package: Package,
  truck: Truck,
  'truck-field': Truck,
  'truck-fast': Truck,
  gears: Gear,
  gear: Gear,
  gauge: Gauge,
  'gauge-high': Gauge,
  route: Path,
  path: Path,
  sitemap: TreeStructure,
  'tree-structure': TreeStructure,
  'diagram-project': Graph,
  graph: Graph,
  'flow-arrow': FlowArrow,
  shuffle: Shuffle,
  'code-fork': GitBranch,
  'git-branch': GitBranch,
  'arrows-split-up-and-left': ArrowsOut,
  'arrows-out': ArrowsOut,
  cube: Cube,
  lightning: Lightning,
  pulse: Pulse,
  scales: Scales,
  'scale-balanced': Scales,
  'bug-slash': Bug,
  bug: Bug,
  // Charts
  'chart-pie': ChartPie,
  'chart-line': ChartLine,
  // AI / magic
  'wand-magic-sparkles': MagicWand,
  'magic-wand': MagicWand,
  'comment-dots': ChatCircle,
  chat: ChatCircle,
} as const;

export type IconName = keyof typeof ICON_MAP;

export interface IconProps {
  name: string;
  size?: number;
  weight?: 'thin' | 'light' | 'regular' | 'bold' | 'fill' | 'duotone';
  className?: string;
}

/** Normalizes legacy Font Awesome names (`fa-*`, `fas *`, `fa-solid *`) to Phosphor map keys. */
const normalizeIconName = (raw: string): string => {
  const cleaned = raw
    .trim()
    .replace(/^fa-(solid|regular|light|brands)\s+/i, '')
    .replace(/^fa[srbld]?\s+/i, '')
    .replace(/^fa-/, '')
    .replace(/\s+fa-spin\b/g, '')
    .replace(/\s+text-red-\d+/g, '')
    .replace(/\s+text-\[.*?\]/g, '')
    .split(/\s+/)[0]
    ?.replace(/^fa-/, '') ?? '';
  return cleaned;
};

export const Icon: React.FC<IconProps> = ({ name, size = 16, weight = 'regular', className }) => {
  const key = normalizeIconName(name) as IconName;
  const Cmp: PhosphorIcon = ICON_MAP[key] ?? FileIcon;
  return <Cmp size={size} weight={weight} className={className} aria-hidden="true" />;
};

// =========================================
// 1. AppFrame
// =========================================
export const AppFrame: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="h-screen w-screen flex flex-col bg-app-bg text-ink-primary overflow-hidden">
    {children}
  </div>
);

// =========================================
// 2. Button (canonical) + ActionButton (compat alias)
// =========================================
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'success' | 'warning' | 'ghost';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: string;
  loading?: boolean;
  size?: 'sm' | 'md';
}

const getButtonVariantClass = (variant: ButtonVariant, disabled?: boolean): string => {
  if (disabled) return 'cursor-not-allowed border-line bg-surface-3 text-ink-muted';
  switch (variant) {
    case 'primary':
      return 'border-transparent bg-accent-primary text-white shadow-[0_8px_20px_-8px_rgba(37,99,235,0.55)] hover:bg-accent-strong';
    case 'danger':
      return 'border-transparent bg-[var(--accent-danger)] text-white hover:bg-accent-danger';
    case 'success':
      return 'border-transparent bg-[var(--accent-success)] text-white hover:bg-accent-success';
    case 'warning':
      return 'border-transparent bg-[var(--accent-warning)] text-white hover:bg-accent-warning';
    case 'ghost':
      return 'border-transparent bg-transparent text-ink-secondary hover:bg-state-hover';
    default:
      return 'border-line bg-surface-1 text-ink-secondary hover:bg-surface-2 hover:text-ink-primary';
  }
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  icon,
  loading = false,
  size = 'md',
  children,
  className = '',
  disabled,
  ...props
}) => {
  const sizing = size === 'sm' ? 'px-3 py-1.5 text-[11px]' : 'px-4 py-2.5 text-xs';
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-control border font-semibold transition-all ${sizing} ${getButtonVariantClass(variant, disabled)} ${className}`}
      {...props}
    >
      {loading ? <Icon name="spinner" size={14} className="animate-spin" /> : icon ? <Icon name={icon} size={14} /> : null}
      {children != null && <span>{children}</span>}
    </button>
  );
};

/** @deprecated Back-compat alias for Button. */
export const ActionButton = Button;

// =========================================
// 3. IconButton (icon-only, requires aria-label)
// =========================================
interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: string;
  label: string;
  size?: number;
  variant?: 'default' | 'ghost' | 'onDark';
}

export const IconButton: React.FC<IconButtonProps> = ({
  icon,
  label,
  size = 16,
  variant = 'default',
  className = '',
  ...props
}) => {
  const variantClass =
    variant === 'onDark'
      ? 'border-white/15 bg-white/5 text-white/80 hover:bg-white/12 hover:text-white'
      : variant === 'ghost'
        ? 'border-transparent bg-transparent text-ink-muted hover:bg-state-hover hover:text-ink-primary'
        : 'border-line bg-surface-1 text-ink-secondary hover:bg-surface-2 hover:text-ink-primary';
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-control border transition-all ${variantClass} ${className}`}
      {...props}
    >
      <Icon name={icon} size={size} />
    </button>
  );
};

// =========================================
// 4. Card (canonical) + SectionCard (compat alias)
// =========================================
interface CardProps {
  title?: string;
  icon?: string;
  headerActions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}

export const Card: React.FC<CardProps> = ({
  title,
  icon,
  headerActions,
  children,
  className = '',
  padded = true,
}) => (
  <section className={`panel-card-tight overflow-hidden flex flex-col ${className}`}>
    {title && (
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div className="flex items-center gap-2">
          {icon && <Icon name={icon} size={14} className="text-accent-primary" />}
          <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-secondary">{title}</h3>
        </div>
        {headerActions && <div>{headerActions}</div>}
      </div>
    )}
    <div className={`flex-1 ${padded ? 'p-5' : ''}`}>{children}</div>
  </section>
);

/** @deprecated Back-compat alias for Card. */
export const SectionCard = Card;

// =========================================
// 5. TopCommandBar (64px, burger slot for drawers)
// =========================================
interface TopCommandBarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
  envName?: string;
  erpSyncTime?: string;
  onResetActive?: () => void;
  roleSwitcherNode?: React.ReactNode;
  onOpenNavDrawer?: () => void;
  onOpenQueueDrawer?: () => void;
}

export const TopCommandBar: React.FC<TopCommandBarProps> = ({
  searchQuery,
  onSearchChange,
  envName = 'Копия Production',
  erpSyncTime,
  onResetActive,
  roleSwitcherNode,
  onOpenNavDrawer,
  onOpenQueueDrawer,
}) => (
  <header className="col-span-full h-16 border-b border-line bg-surface-1 px-4 flex items-center justify-between gap-3 z-50 shadow-ds-sm">
    <div className="flex items-center gap-2 min-w-0">
      {onOpenNavDrawer && (
        <IconButton icon="list" label="Открыть меню навигации" className="lg:hidden" onClick={onOpenNavDrawer} />
      )}
      <div className="flex items-center gap-3 cursor-pointer select-none min-w-0" onClick={onResetActive}>
        <div className="w-9 h-9 rounded-[14px] bg-[linear-gradient(135deg,#1d4ed8,#3b82f6)] text-white flex items-center justify-center shadow-[0_10px_24px_-10px_rgba(37,99,235,0.7)] shrink-0">
          <Icon name="wave-square" size={18} weight="bold" />
        </div>
        <LottieMotion />
        <div className="min-w-0">
          <h1 className="text-sm font-bold tracking-tight text-ink-primary truncate">PartsOps AI Manager</h1>
          <span className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold">Операционный пульт закупок</span>
        </div>
      </div>
    </div>

    <div className="flex-1 max-w-md hidden sm:block">
      <div className="relative">
        <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
        <input
          type="text"
          placeholder="Глобальный поиск (CMD + K для действий)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full bg-surface-2 border border-line rounded-control pl-9 pr-3 py-2 text-xs text-ink-primary placeholder-ink-muted outline-none focus:border-accent-primary transition-all font-sans"
        />
      </div>
    </div>

    <div className="flex items-center gap-3 text-xs shrink-0">
      <UIModeSwitcher />
      {roleSwitcherNode && <div className="hidden md:flex border-r border-line pr-3">{roleSwitcherNode}</div>}
      <div className="hidden xl:flex flex-col text-right border-l border-line pl-3 shrink-0 whitespace-nowrap">
        <span className="text-[10px] text-ink-muted uppercase tracking-wider font-bold">Среда</span>
        <span className="font-semibold text-ink-secondary">{envName}</span>
      </div>
      {erpSyncTime && (
        <div className="hidden xl:flex flex-col text-right border-l border-line pl-3 shrink-0 whitespace-nowrap">
          <span className="text-[10px] text-ink-muted uppercase tracking-wider font-bold">ERP Синхронизация</span>
          <span className="font-semibold text-ink-secondary">{erpSyncTime}</span>
        </div>
      )}
      {onOpenQueueDrawer && (
        <IconButton icon="bell" label="Открыть очередь запросов" className="xl:hidden" onClick={onOpenQueueDrawer} />
      )}
    </div>
  </header>
);

// =========================================
// 6. LeftNavRail (deep-blue gradient + drawer mode)
// =========================================
interface NavItem { id: string; label: string; icon: string; group?: 'main' | 'admin' | 'bottom'; }

interface LeftNavRailProps {
  activeTab: string;
  onChangeTab: (tab: string) => void;
  items: NavItem[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  drawerOpen?: boolean;
  onCloseDrawer?: () => void;
}

export const LeftNavRail: React.FC<LeftNavRailProps> = ({
  activeTab,
  onChangeTab,
  items,
  isCollapsed,
  onToggleCollapse,
  drawerOpen = false,
  onCloseDrawer,
}) => {
  const drawerRef = React.useRef<HTMLElement | null>(null);
  const bottomActionRef = React.useRef<HTMLDivElement | null>(null);
  useFocusTrap(drawerRef, drawerOpen);
  useKeydown('Escape', () => { if (drawerOpen && onCloseDrawer) onCloseDrawer(); }, [drawerOpen, onCloseDrawer]);

  React.useLayoutEffect(() => {
    if (!bottomActionRef.current) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      if (reduceMotion) {
        gsap.set(bottomActionRef.current, { opacity: 1, y: 0 });
        return;
      }
      gsap.fromTo(
        bottomActionRef.current,
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.42, delay: 0.08, ease: 'power3.out' },
      );
    }, bottomActionRef.current);
    return () => ctx.revert();
  }, [isCollapsed, drawerOpen]);

  const railBody = (inDrawer: boolean) => {
    const mainItems = items.filter((item) => !item.group || item.group === 'main');
    const adminItems = items.filter((item) => item.group === 'admin');
    const bottomItems = items.filter((item) => item.group === 'bottom');
    const collapsedView = isCollapsed && !inDrawer;

    const renderButton = (item: NavItem) => {
      const isActive = activeTab === item.id;
      return (
        <button
          key={item.id}
          type="button"
          aria-label={item.label}
          aria-current={isActive ? 'page' : undefined}
          onClick={() => { onChangeTab(item.id); if (inDrawer && onCloseDrawer) onCloseDrawer(); }}
          className={`relative group w-full flex items-center gap-3 px-3 py-2.5 rounded-[14px] text-xs font-semibold transition-all duration-200 text-left ${isActive ? 'sidebar-button-glass-active' : 'sidebar-button-glass-inactive'}`}
        >
          <Icon name={item.icon} size={16} className={`shrink-0 transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-white' : 'text-[var(--sidebar-muted)] group-hover:text-white'}`} />
          {!collapsedView && <span className="animate-fadeIn truncate">{item.label}</span>}
          {collapsedView && (
            <div className="absolute left-16 px-3 py-1.5 rounded-[10px] bg-ink-primary/95 backdrop-blur-md text-white/90 text-[11px] font-bold tracking-wide border border-white/15 shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 translate-x-2 group-hover:translate-x-0 whitespace-nowrap z-50 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-300" />
              {item.label}
            </div>
          )}
        </button>
      );
    };

    return (
      <>
        <div className="py-4 px-3 flex flex-col gap-1 flex-1 overflow-y-auto min-h-0">
          <div className={`flex items-center mb-4 ${isCollapsed && !inDrawer ? 'justify-center' : 'justify-between px-3'}`}>
            {(!isCollapsed || inDrawer) && (
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--sidebar-muted)] animate-fadeIn">Рабочий стол</span>
            )}
            {inDrawer ? (
              <IconButton icon="x-mark" label="Закрыть меню" variant="onDark" onClick={onCloseDrawer} />
            ) : (
              <button
                onClick={onToggleCollapse}
                aria-label={isCollapsed ? 'Развернуть меню' : 'Свернуть меню'}
                title={isCollapsed ? 'Развернуть меню' : 'Свернуть меню'}
                className="w-7 h-7 rounded-full bg-white/10 border border-white/15 hover:bg-white/20 flex items-center justify-center text-white/80 transition-all duration-200 hover:scale-105 active:scale-95"
              >
                <Icon name={isCollapsed ? 'chevron-right' : 'chevron-left'} size={12} />
              </button>
            )}
          </div>

          <div className="flex flex-col gap-1">
            {mainItems.map(renderButton)}
          </div>

          {adminItems.length > 0 && (
            <>
              {collapsedView ? (
                <div className="w-8 border-t border-white/10 my-3 mx-auto" />
              ) : (
                <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--sidebar-muted)] animate-fadeIn mt-6 mb-2 px-3">
                  Админ
                </div>
              )}
              <div className="flex flex-col gap-1">
                {adminItems.map(renderButton)}
              </div>
            </>
          )}
        </div>

        {bottomItems.length > 0 && (
          <div ref={bottomActionRef} className={`px-3 pb-3 shrink-0 ${collapsedView ? 'flex justify-center' : ''}`}>
            {bottomItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => { onChangeTab(item.id); if (inDrawer && onCloseDrawer) onCloseDrawer(); }}
                  aria-current={isActive ? 'page' : undefined}
                  aria-label={`Открыть ${item.label}`}
                  title={item.label}
                  className={`hermes-nav-button group relative flex items-center gap-3 rounded-2xl border text-left transition-all duration-300 ${collapsedView ? 'h-11 w-11 justify-center px-0' : 'w-full px-3 py-3'} ${isActive ? 'hermes-nav-button--active' : ''}`}
                >
                  <span className="hermes-nav-button__glow" aria-hidden="true" />
                  <span className="hermes-nav-button__icon" aria-hidden="true">
                    <Icon name={item.icon} size={18} weight={isActive ? 'fill' : 'regular'} />
                  </span>
                  {!collapsedView && (
                    <span className="hermes-nav-button__copy min-w-0 animate-fadeIn">
                      <span className="hermes-nav-button__eyebrow">AI assistant</span>
                      <span className="hermes-nav-button__label">{item.label}</span>
                    </span>
                  )}
                  {collapsedView && (
                    <span className="hermes-nav-button__tooltip pointer-events-none absolute left-14 z-50 whitespace-nowrap rounded-xl px-3 py-2 text-[11px] font-bold opacity-0 shadow-xl transition-all duration-200 group-hover:translate-x-1 group-hover:opacity-100">
                      {item.label}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {isCollapsed && !inDrawer ? (
          <div className="p-4 border-t border-white/10 shrink-0 flex flex-col items-center gap-3 text-xs text-[var(--sidebar-muted)]">
            <div title="ID Оператора: OP-4819" className="hover:text-white transition-colors cursor-help">
              <Icon name="user-shield" size={14} />
            </div>
            <div title="Версия системы: v6.0.4" className="hover:text-white transition-colors cursor-help text-[10px] font-bold">v6</div>
          </div>
        ) : (
          <div className="p-4 border-t border-white/10 shrink-0 text-[10px] text-[var(--sidebar-muted)] space-y-1.5">
            <div className="flex justify-between"><span>ID Оператора:</span><span className="font-semibold text-white/80">OP-4819</span></div>
            <div className="flex justify-between"><span>Версия системы:</span><span className="font-semibold text-white/80">v6.0.4</span></div>
          </div>
        )}
      </>
    );
  };

  return (
    <>
      <aside className={`sidebar-shell flex flex-col justify-between h-full transition-all duration-300 ease-in-out select-none flex-shrink-0 hidden lg:flex ${isCollapsed ? 'w-16' : 'w-60'}`}>
        {railBody(false)}
      </aside>
      {drawerOpen && (
        <>
          <div className="drawer-backdrop lg:hidden" onClick={onCloseDrawer} aria-hidden="true" />
          <aside
            ref={drawerRef as React.RefObject<HTMLElement>}
            role="dialog"
            aria-modal="true"
            aria-label="Меню навигации"
            className="drawer-panel drawer-panel-left sidebar-shell flex flex-col justify-between select-none lg:hidden w-72"
          >
            {railBody(true)}
          </aside>
        </>
      )}
    </>
  );
};

// =========================================
// 7. RightQueueRail (soft white rail + drawer mode)
// =========================================
interface RightQueueRailProps {
  children: React.ReactNode;
  drawerOpen?: boolean;
  onCloseDrawer?: () => void;
}

export const RightQueueRail: React.FC<RightQueueRailProps> = ({ children, drawerOpen = false, onCloseDrawer }) => {
  const drawerRef = React.useRef<HTMLElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);
  useFocusTrap(drawerRef, drawerOpen);
  useKeydown('Escape', () => { if (drawerOpen && onCloseDrawer) onCloseDrawer(); }, [drawerOpen, onCloseDrawer]);

  React.useLayoutEffect(() => {
    if (!contentRef.current) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      if (reduceMotion) {
        gsap.set(contentRef.current, { opacity: 1, x: 0 });
        return;
      }
      gsap.fromTo(
        contentRef.current,
        { opacity: 0, x: drawerOpen ? 24 : 10 },
        { opacity: 1, x: 0, duration: 0.34, ease: 'power3.out' }
      );
    }, contentRef.current);
    return () => ctx.revert();
  }, [drawerOpen]);

  return (
    <>
      <aside className="queue-rail hidden xl:flex border-l border-line bg-surface-1 flex-col h-full overflow-hidden w-[340px] flex-shrink-0">
        <div ref={contentRef} data-queue-rail-motion className="flex h-full min-h-0 min-w-0 flex-col">
          {children}
        </div>
      </aside>
      {drawerOpen && (
        <>
          <div className="drawer-backdrop" onClick={onCloseDrawer} aria-hidden="true" />
          <aside
            ref={drawerRef as React.RefObject<HTMLElement>}
            role="dialog"
            aria-modal="true"
            aria-label="Очередь запросов"
            onKeyDown={(event) => {
              if (event.key === 'Escape') onCloseDrawer?.();
            }}
            className="queue-rail drawer-panel drawer-panel-right flex flex-col overflow-hidden"
          >
            <div className="flex items-center justify-end px-4 py-2 border-b border-line">
              <span className="sr-only">Очередь запросов</span>
              <IconButton icon="x-mark" label="Закрыть очередь" onClick={onCloseDrawer} />
            </div>
            <div ref={contentRef} className="flex-1 min-h-0 min-w-0 overflow-y-auto" data-queue-rail-motion>{children}</div>
          </aside>
        </>
      )}
    </>
  );
};

// =========================================
// 8. WorkspaceHeader (compact; fake telemetry removed)
// =========================================
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
  priority = 'Normal',
  customerName,
  customerPhone,
  customerEmail,
  vin,
  vehicleMake,
  vehicleModel,
  onBack,
}) => {
  const isUrgent = ['high', 'urgent', 'высокий', 'срочный'].includes(priority.toLowerCase());
  const cleanTitle = (title && !title.startsWith('null'))
    ? title
    : customerName
    ? `${customerName} · План закупки запчастей`
    : `${requestId} · План закупки запчастей`;

  return (
    <div className="mb-4 rounded-panel border border-line bg-surface-1 p-5 text-ink-primary shadow-ds-md">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="shrink-0 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 font-mono text-xs font-bold text-accent-primary">
            {requestId}
          </span>
          <h2 className="max-w-[280px] truncate text-base font-bold text-ink-primary md:max-w-[500px]">
            {cleanTitle}
          </h2>
          <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-black uppercase tracking-wider shrink-0 border ${
            isUrgent
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-line bg-surface-3 text-ink-secondary'
          }`}>
            {isUrgent ? (priority.toLowerCase() === 'urgent' || priority === 'Срочный' ? 'Срочный' : 'Высокий') : 'Обычный'}
          </span>
          {vehicleMake && (
            <span className="shrink-0 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700">
              {vehicleMake} {vehicleModel || ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {onBack && (
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 rounded-control border border-line bg-surface-2 px-4 py-1.5 text-xs font-semibold text-ink-secondary transition hover:bg-surface-3 hover:text-ink-primary"
            >
              <Icon name="arrow-left" size={12} />
              Закрыть
            </button>
          )}
        </div>
      </div>

      {(customerEmail || customerPhone || vin) && (
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line pt-3 text-xs font-medium text-ink-secondary">
          {customerEmail && <span className="flex items-center gap-1.5"><Icon name="envelope" size={13} className="text-ink-muted" />{customerEmail}</span>}
          {customerPhone && <span className="flex items-center gap-1.5"><Icon name="phone" size={13} className="text-ink-muted" />{customerPhone}</span>}
          {vin && (
            <span className="rounded-lg border border-line bg-surface-2 px-2 py-0.5 font-mono text-[11px] font-bold text-ink-secondary">
              VIN: {vin}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

// =========================================
// 9. SubnavPills
// =========================================
interface SubnavPillsProps {
  activeTab: string;
  onChangeTab: (id: string) => void;
  tabs: Array<{ id: string; label: string; icon: string; badge?: string }>;
}

export const SubnavPills: React.FC<SubnavPillsProps> = ({ activeTab, onChangeTab, tabs }) => (
  <div className="flex items-center border border-line bg-surface-1 p-1 rounded-control gap-1 shadow-ds-sm">
    {tabs.map((tab) => {
      const isActive = activeTab === tab.id;
      return (
        <button
          key={tab.id}
          onClick={() => onChangeTab(tab.id)}
          className={`flex-1 flex items-center justify-center gap-2 py-1.5 px-3 rounded-[10px] text-xs font-semibold transition-all ${isActive ? 'bg-[var(--state-selected)] text-accent-primary border border-[rgba(37,99,235,0.25)]' : 'text-ink-secondary hover:text-ink-primary hover:bg-surface-2 border border-transparent'}`}
        >
          <Icon name={tab.icon} size={14} />
          <span>{tab.label}</span>
          {tab.badge && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-surface-4 text-ink-secondary">{tab.badge}</span>}
        </button>
      );
    })}
  </div>
);

// =========================================
// 10. DataTable (16px padding, hover, numeric right-align)
// =========================================
export interface TableColumn { key: string; label: string; numeric?: boolean; }

interface DataTableProps {
  headers?: string[];
  columns?: TableColumn[];
  children: React.ReactNode;
}

export const DataTable: React.FC<DataTableProps> = ({ headers, columns, children }) => {
  const cols: TableColumn[] = columns ?? (headers ?? []).map((h, i) => ({ key: `h${i}`, label: h }));
  return (
    <div className="w-full overflow-x-auto rounded-card border border-line bg-surface-1">
      <table className="table-base">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key} className={c.numeric ? 'cell-num' : ''} scope="col">{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
};

// =========================================
// 11. MetricTile (white default; gradient variant)
// =========================================
export type MetricGradient = 'blue' | 'violet' | 'teal' | 'amber';

interface MetricTileProps {
  label: string;
  value: string | number;
  delta?: string;
  tone?: 'emerald' | 'amber' | 'cyan' | 'violet' | 'danger' | 'neutral';
  gradient?: MetricGradient;
  icon?: string;
}

export const MetricTile: React.FC<MetricTileProps> = ({ label, value, delta, tone = 'neutral', gradient, icon }) => {
  const getToneClasses = () => {
    switch (tone) {
      case 'emerald': return 'bg-green-50 text-green-700 border-green-200';
      case 'amber': return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'cyan': return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'violet': return 'bg-sky-50 text-sky-700 border-sky-200';
      case 'danger': return 'bg-red-50 text-red-700 border-red-200';
      default: return 'bg-surface-2 text-ink-secondary border-line';
    }
  };

  if (gradient) {
    return (
      <div className={`kpi-gradient kpi-gradient-${gradient} min-h-[108px] p-4`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/75">{label}</span>
          {icon && <Icon name={icon} size={16} className="text-white/70" />}
        </div>
        <div className="mt-4 flex items-end justify-between gap-2">
          <strong className="text-[32px] font-bold tracking-[-0.04em] text-white">{value}</strong>
          {delta && <span className="rounded-full border border-white/25 bg-white/15 px-2.5 py-1 text-[10px] font-semibold text-white">{delta}</span>}
        </div>
      </div>
    );
  }

  return (
    <div className="panel-card-tight min-h-[108px] overflow-hidden p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted">{label}</span>
        {icon && <Icon name={icon} size={16} className="text-accent-primary" />}
      </div>
      <div className="mt-4 flex items-end justify-between gap-2">
        <strong className="text-[32px] font-bold tracking-[-0.04em] text-ink-primary">{value}</strong>
        {delta && (
          <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${getToneClasses()}`}>
            {delta}
          </span>
        )}
      </div>
    </div>
  );
};

// =========================================
// 12. StatusBadge
// =========================================
export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const label = getStatusLabel(status);
  return (
    <span
      title={label}
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-extrabold uppercase whitespace-nowrap tracking-wide ${getStatusBadgeClasses(status)}`}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
      <span>{label}</span>
    </span>
  );
};

export const TrafficDot: React.FC<{ status: string; showLabel?: boolean }> = ({ status, showLabel = false }) => {
  const light = getTrafficLight(status);
  const color = light === 'green' ? 'bg-emerald-500' : light === 'yellow' ? 'bg-amber-500' : 'bg-rose-500';
  const label = getTrafficLightLabel(status);
  return (
    <span className="inline-flex items-center gap-1.5" title={`${getStatusLabel(status)} (${label})`}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color} ${light !== 'green' ? 'animate-pulse' : ''}`} />
      {showLabel && <span className="text-xs font-semibold text-ink-secondary">{getStatusLabel(status)}</span>}
    </span>
  );
};

// =========================================
// 13. Input + SearchField
// =========================================
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Input: React.FC<InputProps> = ({ label, className = '', id, ...props }) => {
  const generatedId = React.useId();
  const inputId = id ?? generatedId;
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && (
        <label htmlFor={inputId} className="text-[10px] text-ink-muted uppercase tracking-wider font-bold">{label}</label>
      )}
      <input
        id={inputId}
        className="border border-line rounded-control px-3 py-2 text-xs text-ink-primary outline-none focus:border-accent-primary bg-surface-1 transition-all"
        {...props}
      />
    </div>
  );
};

interface SearchFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  placeholder?: string;
}

export const SearchField: React.FC<SearchFieldProps> = ({ placeholder = 'Поиск...', className = '', value, onChange, ...props }) => (
  <div className={`relative ${className}`}>
    <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
    <input
      type="text"
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      className="w-full rounded-control border border-line bg-surface-1 pl-9 pr-3 py-2 text-xs text-ink-primary placeholder-ink-muted outline-none transition-all focus:border-accent-primary font-sans"
      {...props}
    />
  </div>
);

// =========================================
// 14. ModalShell (light 32px, focus-trap, Escape)
// =========================================
interface ModalShellProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  widthClass?: string;
}

export const ModalShell: React.FC<ModalShellProps> = ({ open, onClose, title, subtitle, children, footer, widthClass = 'max-w-2xl' }) => {
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  useFocusTrap(panelRef, open);
  useKeydown('Escape', () => { if (open) onClose(); }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal-panel relative z-[90] w-full ${widthClass} max-h-[88vh] flex flex-col overflow-hidden animate-fadeIn`}
      >
        <div className="flex items-start justify-between gap-4 px-7 pt-6 pb-4 border-b border-line-subtle">
          <div>
            <h2 className="text-base font-bold text-ink-primary">{title}</h2>
            {subtitle && <p className="text-[11px] text-ink-muted mt-1">{subtitle}</p>}
          </div>
          <IconButton icon="x-mark" label="Закрыть диалог" variant="ghost" onClick={onClose} />
        </div>
        <div className="flex-1 overflow-y-auto px-7 py-5">{children}</div>
        {footer && <div className="px-7 py-4 border-t border-line-subtle bg-surface-2">{footer}</div>}
      </div>
    </div>
  );
};

// =========================================
// 15. Dropzone
// =========================================
interface DropzoneProps {
  title: string;
  description: string;
  onImport: (text: string) => void;
  onFileUpload?: (file: File) => Promise<string>;
  acceptLabel?: string;
}

export const Dropzone: React.FC<DropzoneProps> = ({ title, description, onImport, onFileUpload, acceptLabel = 'Разрешены файлы JSON или TXT' }) => {
  const [dragActive, setDragActive] = React.useState(false);
  const [pasteText, setPasteText] = React.useState('');
  const [uploading, setUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState(0);

  const handleFile = async (file: File) => {
    if (!onFileUpload) {
      const reader = new FileReader();
      reader.onload = (event) => { if (event.target?.result) onImport(event.target.result as string); };
      reader.readAsText(file);
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      const progressInterval = setInterval(() => { setUploadProgress((p) => Math.min(p + 10, 90)); }, 100);
      await onFileUpload(file);
      clearInterval(progressInterval);
      setUploadProgress(100);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Ошибка загрузки файла';
      onImport(`[ОШИБКА загрузки ${file.name}]: ${errorMsg}`);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 500);
    }
  };

  return (
    <div className="flex flex-col gap-4 text-xs">
      <div
        onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
        onDrop={async (e) => { e.preventDefault(); setDragActive(false); if (e.dataTransfer.files[0]) await handleFile(e.dataTransfer.files[0]); }}
        className={`border-2 border-dashed rounded-card p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 ${dragActive ? 'border-accent-primary bg-[var(--state-selected)]' : 'border-line-strong hover:border-accent-primary/50 bg-surface-2'}`}
      >
        <CloudArrowUp size={28} className="text-accent-primary mb-3" aria-hidden="true" />
        <strong className="text-xs text-ink-primary font-semibold block mb-1">{title}</strong>
        <p className="text-[11px] text-ink-secondary max-w-xs leading-relaxed">{description}</p>
        <span className="text-[9px] text-ink-muted font-mono mt-3 uppercase tracking-wider block">{acceptLabel}</span>
        <input type="file" className="hidden" id="dropzone-file-input" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.json,.csv" onChange={async (e) => { if (e.target.files?.[0]) await handleFile(e.target.files[0]); }} disabled={uploading} />
        <label htmlFor="dropzone-file-input" className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-control border border-line bg-surface-1 text-xs font-medium text-ink-secondary hover:bg-surface-2 cursor-pointer transition-all">
          <Paperclip size={14} aria-hidden="true" /> Или выберите файл
        </label>
      </div>

      {uploading && (
        <div className="w-full">
          <div className="flex justify-between text-[10px] text-ink-muted mb-1"><span>Загрузка файла...</span><span>{uploadProgress}%</span></div>
          <div className="w-full h-2 bg-surface-3 rounded-full overflow-hidden">
            <div className="h-full bg-accent-primary transition-all duration-300 ease-out" style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-[10px] text-ink-muted uppercase tracking-wider font-extrabold block">Или вставьте сырой текст</label>
        <textarea
          rows={4}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="Вставьте JSON поставщиков или текст запроса клиента..."
          className="w-full border border-line rounded-control p-3 bg-surface-1 text-xs text-ink-primary outline-none focus:border-accent-primary focus:ring-1 focus:ring-[var(--accent-primary)]/20 font-mono transition-all duration-200"
          disabled={uploading}
        />
        <Button variant="primary" icon="paper-plane" disabled={!pasteText.trim() || uploading} onClick={() => { onImport(pasteText); setPasteText(''); }}>
          Распознать и обработать
        </Button>
      </div>
    </div>
  );
};

// =========================================
// 16. ReviewPanel
// =========================================
interface ReviewItem { name: string; quantity: number; }
interface ReviewPanelProps { items: ReviewItem[]; onChange: (items: ReviewItem[]) => void; onConfirm: () => void; }

export const ReviewPanel: React.FC<ReviewPanelProps> = ({ items, onChange, onConfirm }) => {
  const [editingIndex, setEditingIndex] = React.useState<number | null>(null);
  const [editName, setEditName] = React.useState('');
  const [editQty, setEditQty] = React.useState(1);
  const [newName, setNewName] = React.useState('');
  const [newQty, setNewQty] = React.useState(1);

  const saveEdit = (idx: number) => {
    const updated = [...items]; updated[idx] = { name: editName, quantity: editQty }; onChange(updated); setEditingIndex(null);
  };
  const deleteItem = (idx: number) => { onChange(items.filter((_, i) => i !== idx)); };
  const addItem = () => { if (!newName.trim()) return; onChange([...items, { name: newName, quantity: newQty }]); setNewName(''); setNewQty(1); };

  return (
    <div className="flex flex-col gap-4 text-xs">
      <div className="border border-line rounded-control overflow-hidden bg-surface-1 shadow-ds-sm">
        <div className="bg-surface-2 border-b border-line px-4 py-2 flex items-center justify-between font-bold text-[11px] text-ink-secondary uppercase tracking-wider">
          <span>Список распознанных деталей</span><span>найдено {items.length} дет.</span>
        </div>
        {items.length === 0 ? (
          <div className="p-6 text-center text-ink-secondary">Детали не найдены. Пожалуйста, добавьте детали вручную.</div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {items.map((item, idx) => {
              const isEditing = editingIndex === idx;
              return (
                <div key={idx} className="p-3 flex items-center justify-between gap-3 hover:bg-surface-2 transition-all">
                  {isEditing ? (
                    <div className="flex-1 flex gap-2">
                      <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className="flex-1 border border-line-strong rounded px-2 py-1 text-xs" />
                      <input type="number" min="1" value={editQty} onChange={(e) => setEditQty(Number(e.target.value))} className="w-16 border border-line-strong rounded px-2 py-1 text-xs" />
                    </div>
                  ) : (
                    <div className="flex-1">
                      <div className="font-semibold text-ink-primary text-sm">{item.name}</div>
                      <div className="text-ink-secondary mt-0.5">Количество: <span className="font-semibold">{item.quantity}</span> шт.</div>
                    </div>
                  )}
                  <div className="flex items-center gap-1">
                    {isEditing ? (
                      <Button variant="success" icon="check" size="sm" onClick={() => saveEdit(idx)} />
                    ) : (
                      <Button icon="pencil" size="sm" onClick={() => { setEditingIndex(idx); setEditName(item.name); setEditQty(item.quantity); }} />
                    )}
                    <Button variant="danger" icon="trash" size="sm" onClick={() => deleteItem(idx)} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-surface-2 border border-line rounded-control p-3 flex flex-col md:flex-row gap-3 items-end">
        <div className="flex-1 flex flex-col gap-1 w-full">
          <label className="text-[10px] text-ink-muted uppercase tracking-wider font-bold">Добавить деталь вручную</label>
          <input type="text" placeholder="например, Передние тормозные колодки OEM 34116852253" value={newName} onChange={(e) => setNewName(e.target.value)} className="border border-line rounded-control px-2.5 py-1.5 text-xs text-ink-primary outline-none focus:border-accent-primary bg-surface-1" />
        </div>
        <div className="w-full md:w-20 flex flex-col gap-1">
          <label className="text-[10px] text-ink-muted uppercase tracking-wider font-bold">Кол-во</label>
          <input type="number" min="1" value={newQty} onChange={(e) => setNewQty(Number(e.target.value))} className="border border-line rounded-control px-2.5 py-1.5 text-xs text-ink-primary outline-none focus:border-accent-primary bg-surface-1" />
        </div>
        <Button variant="secondary" icon="plus" disabled={!newName.trim()} onClick={addItem} className="w-full md:w-auto">Добавить</Button>
      </div>

      <div className="flex justify-end pt-2 border-t border-line-subtle">
        <Button variant="primary" icon="square-check" onClick={onConfirm}>Подтвердить проверку и перейти к подбору</Button>
      </div>
    </div>
  );
};

// =========================================
// 17. SplitPane
// =========================================
export const SplitPane: React.FC<{ left: React.ReactNode; right: React.ReactNode }> = ({ left, right }) => (
  <div className="grid grid-cols-[1fr_340px] h-full overflow-hidden">
    <div className="overflow-y-auto p-4">{left}</div>
    <div className="overflow-y-auto border-l border-line bg-surface-1 p-4">{right}</div>
  </div>
);

// =========================================
// 18. EmptyState
// =========================================
interface EmptyStateProps { title: string; description: string; icon?: string; actionNode?: React.ReactNode; }

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, icon = 'folder-open', actionNode }) => (
  <div className="flex flex-col items-center justify-center text-center p-8 bg-surface-1 border border-line rounded-card min-h-[300px] shadow-ds-sm select-none">
    <div className="w-12 h-12 rounded-full bg-surface-3 flex items-center justify-center mb-4 text-ink-muted border border-line">
      <Icon name={icon} size={24} />
    </div>
    <h3 className="text-sm font-bold text-ink-primary block mb-1">{title}</h3>
    <p className="text-[11px] text-ink-secondary max-w-xs leading-relaxed mb-4">{description}</p>
    {actionNode && <div>{actionNode}</div>}
  </div>
);

// =========================================
// 19. InlineAlert
// =========================================
interface InlineAlertProps { message: string | React.ReactNode; type?: 'warning' | 'danger' | 'success' | 'info'; }

export const InlineAlert: React.FC<InlineAlertProps> = ({ message, type = 'info' }) => {
  const getAlertClasses = () => {
    switch (type) {
      case 'warning': return { container: 'bg-amber-50 border-amber-200 text-amber-800', icon: 'exclamation-triangle' };
      case 'danger': return { container: 'bg-red-50 border-red-200 text-red-800', icon: 'radiation' };
      case 'success': return { container: 'bg-green-50 border-green-200 text-green-800', icon: 'circle-check' };
      default: return { container: 'bg-blue-50 border-blue-200 text-blue-800', icon: 'circle-info' };
    }
  };
  const { container, icon } = getAlertClasses();
  return (
    <div className={`p-3 rounded-control border text-xs flex items-start gap-2.5 mb-4 shadow-ds-sm ${container}`}>
      <Icon name={icon} size={16} className="mt-0.5 shrink-0" />
      <span className="leading-normal font-medium">{message}</span>
    </div>
  );
};

// =========================================
// 20. StepGate
// =========================================
interface StepGateProps { currentStep: number; steps: string[]; onStepClick?: (idx: number) => void; }

export const StepGate: React.FC<StepGateProps> = ({ currentStep, steps, onStepClick }) => (
  <div className="flex items-center w-full justify-between border border-line bg-surface-1 p-2.5 rounded-control mb-4 shadow-ds-sm select-none">
    {steps.map((step, idx) => {
      const isCompleted = idx < currentStep;
      const isCurrent = idx === currentStep;
      const isClickable = onStepClick && idx <= currentStep;
      return (
        <React.Fragment key={idx}>
          <div
            onClick={() => isClickable && onStepClick && onStepClick(idx)}
            className={`flex items-center gap-2 px-2 py-1 rounded transition-all ${isClickable ? 'cursor-pointer hover:bg-surface-2' : 'cursor-default'}`}
          >
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all ${isCurrent ? 'bg-accent-primary text-white border-accent-primary shadow-sm' : isCompleted ? 'bg-green-500 text-white border-green-500' : 'bg-surface-1 text-ink-muted border-line-strong'}`}>
              {isCompleted ? <Icon name="check" size={8} /> : idx + 1}
            </span>
            <span className={`text-[11px] font-semibold transition-all ${isCurrent ? 'text-accent-primary font-bold' : isCompleted ? 'text-green-700' : 'text-ink-muted'}`}>{step}</span>
          </div>
          {idx < steps.length - 1 && <div className={`flex-1 h-[2px] mx-2 ${idx < currentStep ? 'bg-green-300' : 'bg-[var(--border-default)]'}`} />}
        </React.Fragment>
      );
    })}
  </div>
);

// =========================================
// 21. Skeleton
// =========================================
export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`skeleton rounded-control ${className}`} />
);

// =========================================
// 21b. SoftPollPill — subtle background-refresh indicator (no skeleton flash)
// =========================================
interface SoftPollPillProps {
  active?: boolean;
  label?: string;
  /** sm = compact list chrome; md = hero/status strip */
  size?: 'sm' | 'md';
  className?: string;
}

export const SoftPollPill: React.FC<SoftPollPillProps> = ({
  active = true,
  label = 'Обновление',
  size = 'sm',
  className = '',
}) => {
  if (!active) return null;
  const sizeCls =
    size === 'md'
      ? 'gap-1.5 px-2.5 py-1 text-[9px]'
      : 'gap-1 px-2 py-0.5 text-[9px]';
  const dotCls = size === 'md' ? 'h-1.5 w-1.5' : 'h-1.5 w-1.5';
  return (
    <span
      className={`inline-flex items-center rounded-full border border-line bg-surface-2 font-bold uppercase tracking-wide text-ink-secondary ${sizeCls} ${className}`}
      role="status"
      aria-live="polite"
    >
      <span className={`${dotCls} animate-pulse rounded-full bg-sky-500`} aria-hidden />
      {label}
    </span>
  );
};

// =========================================
// 22. ErrorState
// =========================================
interface ErrorStateProps { title?: string; message: string; onRetry?: () => void; }

export const ErrorState: React.FC<ErrorStateProps> = ({ title = 'Ошибка загрузки данных', message, onRetry }) => (
  <div className="flex flex-col items-center justify-center text-center p-8 bg-red-50/50 border border-red-200 rounded-card min-h-[200px] select-none">
    <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4 text-red-500 border border-red-200">
      <Icon name="exclamation-triangle" size={24} />
    </div>
    <h3 className="text-sm font-bold text-red-800 block mb-1">{title}</h3>
    <p className="text-[11px] text-red-700 max-w-xs leading-relaxed mb-4">{message}</p>
    {onRetry && <Button variant="primary" icon="arrow-rotate-right" size="sm" onClick={onRetry}>Повторить</Button>}
  </div>
);
