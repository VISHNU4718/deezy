import React from 'react';
import { Menu, Bell, Moon, Sun, User, LogOut, Search, Settings } from 'lucide-react';

interface HeaderProps {
  onMenuClick: () => void;
  sidebarCollapsed: boolean;
}

export function Header({ onMenuClick, sidebarCollapsed }: HeaderProps) {
  const [darkMode, setDarkMode] = React.useState(false);
  const [showUserMenu, setShowUserMenu] = React.useState(false);

  return (
    <header
      className="flex items-center justify-between h-[60px] px-4 bg-surface border-b border-border sticky top-0 z-40"
      style={{ marginLeft: sidebarCollapsed ? '64px' : '280px', transition: 'margin-left 200ms' }}
      role="banner"
    >
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="p-2 rounded hover:bg-background transition lg:hidden"
          aria-label="Toggle menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="search"
            placeholder="Search conversations, tasks..."
            className="w-64 pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
            aria-label="Search"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-2 rounded hover:bg-background transition"
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        <button
          className="p-2 rounded hover:bg-background transition relative"
          aria-label="Notifications"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-danger rounded-full" />
        </button>

        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 p-1.5 rounded hover:bg-background transition"
            aria-label="User menu"
            aria-expanded={showUserMenu}
          >
            <div className="w-8 h-8 rounded-full bg-primary-light flex items-center justify-center">
              <User className="w-4 h-4 text-primary" />
            </div>
            {!sidebarCollapsed && (
              <>
                <span className="text-sm font-medium hidden sm:block">User</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </>
            )}
          </button>

          {showUserMenu && (
            <div
              className="absolute right-0 mt-2 w-48 bg-surface border border-border rounded-lg shadow-lg py-1 z-50"
              role="menu"
            >
              <div className="px-4 py-2 border-b border-border">
                <p className="text-sm font-medium">User</p>
                <p className="text-xs text-muted">user@deezy.local</p>
              </div>
              <button className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-background" role="menuitem">
                <User className="w-4 h-4" />
                Profile
              </button>
              <button className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-background" role="menuitem">
                <Settings className="w-4 h-4" />
                Settings
              </button>
              <hr className="my-1 border-border" />
              <button className="w-full flex items-center gap-2 px-4 py-2 text-sm text-danger hover:bg-background" role="menuitem">
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
