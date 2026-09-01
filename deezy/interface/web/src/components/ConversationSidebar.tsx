import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  Search,
  Download,
  Eye,
  Edit2,
  Trash2,
  Loader2,
  ChevronLeft,
  ChevronRight,
  X,
  Check,
  Upload,
  GitBranch,
} from 'lucide-react';
import { useConversations } from '../hooks/useApi';
import type { Conversation, ConversationBase } from '../types';
import { format, formatDistanceToNow } from 'date-fns';

interface ConversationSidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
  currentConversationId?: string;
  onSelectConversation?: (id: string) => void;
}

export function ConversationSidebar({ 
  collapsed = false, 
  onToggle,
  currentConversationId,
  onSelectConversation 
}: ConversationSidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { 
    conversations, 
    loading, 
    error, 
    loadConversations, 
    createConversation, 
    deleteConversation, 
    updateConversation,
    exportConversation,
    importConversation,
    createBranch
  } = useConversations();

  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newConvTitle, setNewConvTitle] = useState('');
  const [editingConv, setEditingConv] = useState<Conversation | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const filteredConversations = conversations.filter(conv => 
    conv.title.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreateConversation = async () => {
    if (!newConvTitle.trim()) return;
    try {
      const result = await createConversation(newConvTitle);
      setNewConvTitle('');
      setShowCreateModal(false);
      if (onSelectConversation && result?.id) {
        onSelectConversation(result.id);
        navigate(`/chat/${result.id}`);
      }
    } catch (e) {
      console.error('Failed to create conversation:', e);
    }
  };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;
    try {
      await deleteConversation(id);
      if (currentConversationId === id) {
        onSelectConversation?.('');
        navigate('/');
      }
    } catch (e) {
      console.error('Failed to delete conversation:', e);
    }
  };

  const handleEditConversation = (conv: ConversationBase) => {
    setEditingConv(conv as Conversation);
    setEditTitle(conv.title);
  };

  const handleSaveEdit = async () => {
    if (!editingConv || !editTitle.trim()) return;
    try {
      await updateConversation(editingConv.id, editTitle);
      setEditingConv(null);
      setEditTitle('');
    } catch (e) {
      console.error('Failed to update conversation:', e);
    }
  };

  const handleCancelEdit = () => {
    setEditingConv(null);
    setEditTitle('');
  };

  const handleExportConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const data = await exportConversation(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation-${data.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to export conversation:', e);
    }
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setImportFile(file);
  };

  const handleImportConversation = async () => {
    if (!importFile) return;
    try {
      const text = await importFile.text();
      const data = JSON.parse(text);
      await importConversation(data);
      setImportFile(null);
    } catch (e) {
      console.error('Failed to import conversation:', e);
    }
  };

  const handleCreateBranch = async (convId: string) => {
    try {
      const result = await createBranch(convId, 1, `Branch of ${conversations.find(c => c.id === convId)?.title || 'Conversation'}`);
      if (result?.conversation_id) {
        onSelectConversation?.(result.conversation_id);
        navigate(`/chat/${result.conversation_id}`);
      }
    } catch (e) {
      console.error('Failed to create branch:', e);
    }
  };

  const isActive = (id: string) => currentConversationId === id;

  return (
    <aside
      className={`flex flex-col bg-surface border-r border-border transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-80'
      }`}
      style={{ width: collapsed ? '64px' : '320px' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between h-[60px] px-4 border-b border-border">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <MessageSquare className="w-6 h-6 text-primary" />
            <span className="font-semibold text-lg">Deezy</span>
          </div>
        )}
        {collapsed && (
          <MessageSquare className="w-6 h-6 text-primary mx-auto" />
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

      {!collapsed && (
        <>
          {/* Search */}
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input
                type="search"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search conversations..."
                className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
              />
            </div>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto divide-y divide-border">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-32 text-danger">
                Failed to load conversations
              </div>
            ) : filteredConversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-muted">
                <MessageSquare className="w-10 h-10 mb-4 opacity-50" />
                <p className="text-sm">{search ? 'No conversations found' : 'No conversations yet'}</p>
                {!search && (
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="mt-2 px-4 py-1.5 text-xs bg-primary text-white rounded hover:bg-primary-hover transition"
                  >
                    Create First Conversation
                  </button>
                )}
              </div>
            ) : (
              <div className="divide-y divide-border">
                {filteredConversations.map(conv => (
                  <div key={conv.id}>
                    {editingConv?.id === conv.id ? (
                      <div className="flex items-center gap-2 px-2 py-1.5">
                        <input
                          type="text"
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleSaveEdit()}
                          onBlur={handleCancelEdit}
                          autoFocus
                          className="flex-1 px-2 py-1 text-sm bg-background border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary"
                        />
                        <button
                          onClick={handleSaveEdit}
                          className="p-1 text-success hover:bg-success/10 rounded"
                          aria-label="Save"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="p-1 text-muted hover:bg-background rounded"
                          aria-label="Cancel"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          onSelectConversation?.(conv.id);
                          navigate(`/chat/${conv.id}`);
                        }}
                        className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg transition ${
                          isActive(conv.id)
                            ? 'bg-primary/10 text-primary'
                            : 'text-text-secondary hover:bg-background hover:text-text'
                        }`}
                        title={collapsed ? conv.title : undefined}
                      >
                        <div className="flex-1 min-w-0 text-left">
                          <p className="font-medium text-sm truncate">{conv.title}</p>
                          <p className="text-xs text-muted truncate">
                            {conv.message_count || 0} messages
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                          <button
                            onClick={e => { e.stopPropagation(); handleExportConversation(conv.id, e); }}
                            className="p-1.5 rounded hover:bg-background transition text-muted"
                            aria-label="Export"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleEditConversation(conv); }}
                            className="p-1.5 rounded hover:bg-background transition"
                            aria-label="Rename"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleCreateBranch(conv.id); }}
                            className="p-1.5 rounded hover:bg-background transition"
                            aria-label="Create branch"
                          >
                            <GitBranch className="w-4 h-4" />
                          </button>
                          <button
                            onClick={e => { e.stopPropagation(); handleDeleteConversation(conv.id, e); }}
                            className="p-1.5 rounded hover:bg-danger/10 text-danger transition"
                            aria-label="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="p-3 border-t border-border space-y-2">
            <button
              onClick={() => setShowCreateModal(true)}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition"
            >
              <Plus className="w-4 h-4" />
              New Conversation
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => document.getElementById('import-conv-input')?.click()}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-background rounded-lg border border-border transition"
              >
                <Upload className="w-4 h-4" />
                Import
              </button>
              <input
                id="import-conv-input"
                type="file"
                accept=".json"
                onChange={handleImportFile}
                className="hidden"
              />
            </div>
          </div>
        </>
      )}

      {/* Collapsed footer */}
      {collapsed && onToggle && (
        <div className="flex-1 flex flex-col items-center justify-end p-2">
          <button
            onClick={onToggle}
            className="p-2 rounded hover:bg-background transition"
            aria-label="Expand sidebar"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Create Conversation Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">New Conversation</h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <textarea
              value={newConvTitle}
              onChange={e => setNewConvTitle(e.target.value)}
              placeholder="Conversation title"
              className="w-full min-h-[100px] px-4 py-3 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light resize-none mb-4"
              rows={4}
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => { setShowCreateModal(false); setNewConvTitle(''); }}
                className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateConversation}
                disabled={!newConvTitle.trim()}
                className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50"
              >
                Create Conversation
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}