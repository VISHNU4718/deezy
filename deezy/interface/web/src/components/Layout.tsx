import React, { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { ConversationSidebar } from './ConversationSidebar';
import { Header } from './Header';

export function MainLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [convSidebarCollapsed, setConvSidebarCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Determine if we're on the chat page
  const isChatPage = location.pathname === '/' || location.pathname.startsWith('/chat');

  return (
    <div className="flex h-screen overflow-hidden">
      {isChatPage && (
        <ConversationSidebar
          collapsed={convSidebarCollapsed}
          onToggle={() => setConvSidebarCollapsed(!convSidebarCollapsed)}
          currentConversationId={location.pathname.startsWith('/chat/') ? location.pathname.split('/')[2] : undefined}
          onSelectConversation={(id) => navigate(`/chat/${id}`)}
        />
      )}
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          onMenuClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          sidebarCollapsed={sidebarCollapsed}
        />
        <main
          className="flex-1 overflow-y-auto p-4 md:p-6"
          style={{ 
            marginLeft: sidebarCollapsed ? '64px' : '280px', 
            transition: 'margin-left 200ms' 
          }}
          role="main"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}