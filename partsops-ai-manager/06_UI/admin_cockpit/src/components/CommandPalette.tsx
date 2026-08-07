import { useEffect, useState, useRef, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { notify } from '../lib/notify';
import { Icon } from './Primitives';


type Command = {
  id: string;
  label: string;
  description: string;
  icon: string;
  shortcut?: string;
  action: () => void;
  category: string;
};

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (path: string) => void;
  requests: any[];
  suppliers: any[];
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigate,
  requests,
  suppliers,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [commands, setCommands] = useState<Command[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Build commands based on current state
  useEffect(() => {
    const cmdList: Command[] = [
      // Navigation
      {
        id: 'nav-dashboard',
        label: 'Панель управления',
        description: 'Обзор метрик и KPI',
        icon: 'chart-pie',
        shortcut: 'G D',
        action: () => onNavigate('dashboard'),
        category: 'Навигация',
      },
      {
        id: 'nav-kanban',
        label: 'Канбан-доска',
        description: 'Перетаскивание заказов между этапами',
        icon: 'table-columns',
        shortcut: 'G K',
        action: () => onNavigate('kanban'),
        category: 'Навигация',
      },
      {
        id: 'nav-suppliers',
        label: 'Каталог поставщиков',
        description: 'Управление поставщиками и прайс-листами',
        icon: 'truck-field',
        shortcut: 'G S',
        action: () => onNavigate('suppliers'),
        category: 'Навигация',
      },
      {
        id: 'nav-orders',
        label: 'Кастом',
        description: 'Загрузка файлов и создание новых запросов',
        icon: 'file-arrow-up',
        shortcut: 'G O',
        action: () => onNavigate('orders'),
        category: 'Навигация',
      },
      {
        id: 'nav-matching',
        label: 'Матрица подбора и цен',
        description: 'Сравнение офферов поставщиков, расчет маржи и калькуляция',
        icon: 'arrows-split-up-and-left',
        shortcut: 'G M',
        action: () => onNavigate('matching'),
        category: 'Навигация',
      },
      {
        id: 'nav-audit',
        label: 'Аудит и логи',
        description: 'История изменений и цепочка событий',
        icon: 'shield-halved',
        shortcut: 'G A',
        action: () => onNavigate('audit'),
        category: 'Навигация',
      },

      // Actions
      {
        id: 'action-new-request',
        label: 'Новый запрос',
        description: 'Создать запрос на закупку вручную',
        icon: 'plus',
        shortcut: '⌘ N',
        action: () => onNavigate('orders'),
        category: 'Действия',
      },
      {
        id: 'action-refresh',
        label: 'Обновить данные',
        description: 'Принудительно обновить очередь и метрики',
        icon: 'rotate',
        shortcut: '⌘ R',
        action: () => window.location.reload(),
        category: 'Действия',
      },
      {
        id: 'action-sync-erp',
        label: 'Статус ERP',
        description: 'Проверить health ERP (полный push — не one-click job)',
        icon: 'rotate',
        shortcut: '⌘ E',
        action: async () => {
          try {
            const res = await apiFetch('/api/admin/data-health');
            if (!res.ok) {
              notify.error(`ERP status: API ${res.status}`);
              return;
            }
            const data = await res.json();
            const failing = Boolean(data?.health_indicators?.erp_health?.currently_failing);
            const lastSync =
              data?.freshness?.last_erp_sync ??
              data?.freshness?.last_erp_sync_at ??
              null;
            const statusLabel = failing ? 'Сбой' : 'OK';
            const syncLabel = lastSync ? String(lastSync) : 'н/д';
            notify.info(
              `Статус ERP: ${statusLabel}, last sync: ${syncLabel}. ` +
                'Полный ERP push — не глобальная one-click job (доступен только invoice endpoint).',
            );
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            notify.error(`ERP status unavailable: ${msg}`);
          }
        },
        category: 'Действия',
      },

      // Requests - dynamic
      ...requests.slice(0, 10).map((req) => ({
        id: `req-${req.request_id}`,
        label: `Запрос: ${req.request_id}`,
        description: `${req.customer_name} • ${req.status} • ${req.parts_json?.length || 0} позиций`,
        icon: 'file-lines',
        action: () => onNavigate('matching'), // will select request
        category: 'Запросы',
      })),

      // Suppliers - dynamic
      ...suppliers.slice(0, 10).map((sup) => ({
        id: `sup-${sup.supplier_id}`,
        label: `Поставщик: ${sup.name}`,
        description: `${sup.city} • ${sup.status} • Надежность: ${Math.round(sup.reliability_score * 100)}%`,
        icon: 'truck-field',
        action: () => onNavigate('suppliers'),
        category: 'Поставщики',
      })),

      // Shortcuts help
      {
        id: 'help-shortcuts',
        label: 'Клавиатурные сокращения',
        description: 'Показать список всех горячих клавиш',
        icon: 'keyboard',
        shortcut: '⌘ ?',
        action: () =>
          alert(`
Горячие клавиши:
⌘ K — Открыть командную палитру
G D — Панель управления
G K — Канбан-доска
G S — Поставщики
G O — Импорт заказов
G M / G P — Матрица подбора и цен
G A — Аудит
⌘ N — Новый запрос
⌘ R — Обновить
⌘ E — Статус ERP (health, без fake push)
Esc — Закрыть палитру
`),
        category: 'Помощь',
      },
    ];

    setCommands(cmdList);
    setSelectedIndex(0);
  }, [requests, suppliers, onNavigate]);

  // Filter commands based on query
  const filteredCommands = commands
    .filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(query.toLowerCase()) ||
        cmd.description.toLowerCase().includes(query.toLowerCase()) ||
        cmd.category.toLowerCase().includes(query.toLowerCase()),
    )
    .sort((a, b) => {
      const aMatch = a.label.toLowerCase().startsWith(query.toLowerCase()) ? 0 : 1;
      const bMatch = b.label.toLowerCase().startsWith(query.toLowerCase()) ? 0 : 1;
      return aMatch - bMatch;
    });

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filteredCommands.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action();
          onClose();
        }
        break;
      case 'Escape':
        onClose();
        break;
    }
  }, [filteredCommands, selectedIndex, onClose]);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-surface-1 border border-line rounded-2xl shadow-2xl overflow-hidden animate-slide-down">
        <div className="relative">
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-muted">
            <Icon name="magnifying-glass" size={20} className="text-xl" />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Введите команду или поиск... (⌘K для открытия)"
            className="w-full px-12 py-4 text-base text-ink-primary bg-transparent border-none outline-none font-sans placeholder-ink-muted"
            autoComplete="off"
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-mono text-ink-muted bg-surface-2 px-2 py-0.5 rounded">
            ⌘K
          </div>
        </div>

        <div className="max-h-[500px] overflow-y-auto">
          {filteredCommands.length === 0 ? (
            <div className="p-8 text-center text-ink-muted">
              <Icon name="search" size={24} className="text-2xl mb-2 opacity-50" />
              <p>Ничего не найдено для «{query}»</p>
              <p className="text-[11px] mt-1">Попробуйте другие ключевые слова</p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-subtle)]">
              {['Навигация', 'Действия', 'Запросы', 'Поставщики', 'Помощь'].map((category) => {
                const categoryCommands = filteredCommands.filter((c) => c.category === category);
                if (categoryCommands.length === 0) return null;
                return (
                  <div key={category} className="p-3 bg-surface-2">
                    <h4 className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink-muted mb-2">{category}</h4>
                    <div className="space-y-1">
                      {categoryCommands.map((cmd, _idx) => {
                        const isSelected = filteredCommands.indexOf(cmd) === selectedIndex;
                        return (
                          <button
                            key={cmd.id}
                            onClick={() => {
                              cmd.action();
                              onClose();
                            }}
                            onMouseEnter={() => setSelectedIndex(filteredCommands.indexOf(cmd))}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all ${
                              isSelected
                                ? 'bg-[var(--state-selected)] text-ink-primary'
                                : 'hover:bg-surface-3 text-ink-secondary'
                            }`}
                          >
                            <Icon
                              name={cmd.icon}
                              size={18}
                              className={`w-6 shrink-0 ${
                                isSelected ? 'text-accent-primary' : 'text-ink-muted'
                              }`}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium truncate">{cmd.label}</span>
                                {cmd.shortcut && (
                                  <span className="ml-auto text-[10px] font-mono text-ink-muted bg-surface-2 px-1.5 py-0.5 rounded">
                                    {cmd.shortcut}
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] truncate text-ink-muted">{cmd.description}</p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
