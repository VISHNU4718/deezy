import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  History,
  Database,
  Settings,
  ChevronLeft,
  ChevronRight,
  Brain,
} from 'lucide-react';
import { useTools } from '../hooks/useApi';

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

const navItems = [
  { path: '/', label: 'Chat', icon: MessageSquare },
  { path: '/tasks', label: 'Tasks', icon: LayoutDashboard },
  { path: '/history', label: 'History', icon: History },
  { path: '/memory', label: 'Memory', icon: Database },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const location = useLocation();
  const { tools } = useTools();

  return (
    <aside
      className={`flex flex-col bg-surface border-r border-border transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-72'
      }`}
      style={{ width: collapsed ? '64px' : '280px' }}
    >
      <div className="flex items-center justify-between h-[60px] px-4 border-b border-border">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Brain className="w-6 h-6 text-primary" />
            <span className="font-semibold text-lg">Deezy</span>
          </div>
        )}
        {collapsed && (
          <Brain className="w-6 h-6 text-primary mx-auto" />
        )}
        {!collapsed && onToggle && (
          <button
            onClick={onToggle}
            className="p-1.5 rounded hover:bg-background transition"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}
      </div>

      <nav className="flex-1 py-3 px-2 overflow-y-auto" role="navigation" aria-label="Main navigation">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || 
              (item.path !== '/' && location.pathname.startsWith(item.path));
            const Icon = item.icon;
            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded transition ${
                    isActive
                      ? 'bg-primary-light text-primary'
                      : 'text-text-secondary hover:bg-background hover:text-text'
                  }`}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {!collapsed && <span className="font-medium">{item.label}</span>}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-3 border-t border-border">
        {!collapsed && (
          <div className="text-xs text-muted mb-2">Available Tools: {tools.length}</div>
        )}
        {onToggle && (
          <button
            onClick={onToggle}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-background rounded transition"
          >
            {collapsed ? (
              <>
                <ChevronRight className="w-4 h-4" />
                <span>Expand</span>
              </>
            ) : (
              <>
                <ChevronLeft className="w-4 h-4" />
                <span>Collapse</span>
              </>
            )}
          </button>
        )}
      </div>
    </aside>
  );
}