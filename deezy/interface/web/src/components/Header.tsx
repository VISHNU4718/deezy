import React from 'react';
import { Menu } from 'lucide-react';
import { useHealth } from '../hooks/useApi';

interface HeaderProps {
  onMenuClick: () => void;
  sidebarCollapsed: boolean;
}

export function Header({ onMenuClick, sidebarCollapsed }: HeaderProps) {
  const { health } = useHealth();

  return (
    <header
      className="flex items-center justify-between h-[60px] px-4 bg-surface border-b border-border sticky top-0 z-40"
      style={{ marginLeft: sidebarCollapsed ? '64px' : '280px', transition: 'margin-left 200ms' }}
      role="banner"
    >
      <button
        onClick={onMenuClick}
        className="p-2 rounded hover:bg-background transition lg:hidden"
        aria-label="Toggle menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {health?.demo && (
        <p className="text-xs sm:text-sm text-muted" data-testid="demo-banner">
          <span className="font-medium text-warning">Demo.</span> The tools are simulated or sandboxed, there is no LLM,
          and data is temporary.
        </p>
      )}
      <span className="text-xs text-muted">{health ? `v${health.version}` : ''}</span>
    </header>
  );
}
