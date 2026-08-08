import { useState, useEffect, useCallback } from 'react';

export function useKeyboardNavigation<T>(
  items: T[],
  onSelect?: (item: T) => void,
  onAction?: (item: T) => void,
  enabled: boolean = true
) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  useEffect(() => {
    if (selectedIndex >= items.length && items.length > 0) {
      setSelectedIndex(items.length - 1);
    }
  }, [items.length, selectedIndex]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!enabled || items.length === 0) return;

    // Игнорируем ввод в полях ввода
    const target = e.target as HTMLElement;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.min(prev + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (items[selectedIndex] && onSelect) {
        onSelect(items[selectedIndex]);
      }
    } else if (e.key === ' ') {
      e.preventDefault();
      if (items[selectedIndex] && onAction) {
        onAction(items[selectedIndex]);
      }
    }
  }, [enabled, items, selectedIndex, onSelect, onAction]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    selectedIndex,
    setSelectedIndex,
    selectedItem: items[selectedIndex] || null,
  };
}
