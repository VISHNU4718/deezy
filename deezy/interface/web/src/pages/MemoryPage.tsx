/**
 * Memory Page - View, add, edit, delete, and manage long-term memories.
 */

import React, { useState, useEffect, useMemo } from "react";
import { Plus, Search, Filter, Trash2, Edit2, Download, Upload, Loader2, AlertTriangle, CheckCircle, X, Brain, Tag, FileText, Clock, Eye, MoreVertical } from "lucide-react";
import { useMemories } from "../hooks/useApi";
import type { Memory, MemoryCategory, MemoryCreate, MemoryUpdate } from "../types";
import { format, formatDistanceToNow } from "date-fns";

const MEMORY_CATEGORIES: { value: MemoryCategory; label: string; icon: React.ReactNode }[] = [
  { value: "fact", label: "Fact", icon: <Brain className="w-4 h-4" /> },
  { value: "preference", label: "Preference", icon: <Tag className="w-4 h-4" /> },
  { value: "project", label: "Project", icon: <FileText className="w-4 h-4" /> },
  { value: "task", label: "Task", icon: <Clock className="w-4 h-4" /> },
  { value: "decision", label: "Decision", icon: <CheckCircle className="w-4 h-4" /> },
  { value: "observation", label: "Observation", icon: <Eye className="w-4 h-4" /> },
  { value: "conversation", label: "Conversation", icon: <FileText className="w-4 h-4" /> },
];

const CATEGORY_COLORS: Record<MemoryCategory, string> = {
  fact: "bg-blue-500/10 text-blue-500",
  preference: "bg-purple-500/10 text-purple-500",
  project: "bg-green-500/10 text-green-500",
  task: "bg-orange-500/10 text-orange-500",
  decision: "bg-indigo-500/10 text-indigo-500",
  observation: "bg-teal-500/10 text-teal-500",
  conversation: "bg-gray-500/10 text-gray-500",
};

export function MemoryPage() {
  const { memories, loading, error, loadMemories, createMemory, updateMemory, deleteMemory, clearMemories } = useMemories();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<MemoryCategory | "all">("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null);
  const [newMemory, setNewMemory] = useState<Partial<MemoryCreate>>({ category: "fact", content: "", tags: [] as string[], importance: 1.0 });
  const [editForm, setEditForm] = useState<Partial<MemoryUpdate>>({ tags: [] as string[] });
  const [confirmDelete, setConfirmDelete] = useState<Memory | null>(null);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [clearCategory, setClearCategory] = useState<MemoryCategory | "all">("all");

  // Load memories on mount
  useEffect(() => {
    loadMemories(categoryFilter !== "all" ? categoryFilter : undefined);
  }, [loadMemories, categoryFilter]);

  const filteredMemories = useMemo(() => {
    return memories.filter((m) => {
      const matchesSearch = m.content.toLowerCase().includes(search.toLowerCase()) ||
        (m.tags?.some((t) => t.toLowerCase().includes(search.toLowerCase())));
      const matchesCategory = categoryFilter === "all" || m.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [memories, search, categoryFilter]);

  const stats = useMemo(() => {
    const counts: Record<string, number> = {};
    memories.forEach((m) => {
      counts[m.category] = (counts[m.category] || 0) + 1;
    });
    return { total: memories.length, byCategory: counts };
  }, [memories]);

  const handleCreate = async () => {
    if (!newMemory.content?.trim()) return;
    try {
      await createMemory({
        category: (newMemory.category || "fact") as MemoryCategory,
        content: newMemory.content!.trim(),
        tags: newMemory.tags || [],
        importance: newMemory.importance ?? 1.0,
      });
      setShowCreateModal(false);
      setNewMemory({ category: "fact", content: "", tags: [], importance: 1.0 });
    } catch (e) {
      console.error("Failed to create memory:", e);
    }
  };

  const handleEdit = (memory: Memory) => {
    setEditingMemory(memory);
    setEditForm({
      category: memory.category,
      content: memory.content,
      tags: memory.tags || [],
      importance: memory.importance,
    });
  };

  const handleSaveEdit = async () => {
    if (!editingMemory || !editForm.content?.trim()) return;
    try {
      await updateMemory(editingMemory.id, {
        category: (editForm.category || editingMemory.category) as MemoryCategory,
        content: editForm.content.trim(),
        tags: editForm.tags || [],
        importance: editForm.importance ?? editingMemory.importance,
      });
      setEditingMemory(null);
      setEditForm({ tags: [] as string[] });
    } catch (e) {
      console.error("Failed to update memory:", e);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await deleteMemory(confirmDelete.id);
      setConfirmDelete(null);
    } catch (e) {
      console.error("Failed to delete memory:", e);
    }
  };

  const handleClear = async () => {
    try {
      await clearMemories(clearCategory === "all" ? undefined : clearCategory);
      setShowClearDialog(false);
    } catch (e) {
      console.error("Failed to clear memories:", e);
    }
  };

  const getImportanceColor = (importance: number) => {
    if (importance >= 0.8) return "text-danger";
    if (importance >= 0.5) return "text-warning";
    return "text-muted";
  };

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto w-full space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Memory</h1>
            <p className="text-muted text-sm">Manage long-term memories and knowledge</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover transition"
          >
            <Plus className="w-4 h-4" />
            Add Memory
          </button>
        </div>

        {/* Stats Bar */}
        <div className="flex flex-wrap gap-4 mt-4 text-sm">
          <span className="px-3 py-1 bg-primary/10 text-primary rounded-full">
            Total: {stats.total}
          </span>
          {MEMORY_CATEGORIES.map((cat) => (
            <span key={cat.value} className={`px-3 py-1 rounded-full ${CATEGORY_COLORS[cat.value]}`}>
              {cat.label}: {stats.byCategory[cat.value] || 0}
            </span>
          ))}
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search memories..."
            className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as MemoryCategory | "all")}
            className="px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          >
            <option value="all">All Categories</option>
            {MEMORY_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>{cat.label}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => { setClearCategory("all"); setShowClearDialog(true); }}
            className="px-3 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg border border-danger/20 transition"
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Clear All
          </button>
          <button
            onClick={() => { setClearCategory(categoryFilter === "all" ? "fact" : categoryFilter); setShowClearDialog(true); }}
            disabled={categoryFilter === "all"}
            className="px-3 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg border border-danger/20 transition disabled:opacity-50"
          >
            Clear Category
          </button>
        </div>
      </div>

      {/* Memory List */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64 text-danger">
            <AlertTriangle className="w-6 h-6 mr-2" />
            Failed to load memories: {error}
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted">
            <Brain className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg">{search || categoryFilter !== "all" ? "No memories found" : "No memories yet"}</p>
            <p className="text-sm">Add your first memory to get started</p>
            {!search && categoryFilter === "all" && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 px-4 py-2 text-sm bg-primary text-white rounded hover:bg-primary-hover transition"
              >
                Create Memory
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredMemories.map((memory) => (
              <MemoryCard
                key={memory.id}
                memory={memory}
                onEdit={handleEdit}
                onDelete={() => setConfirmDelete(memory)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create Memory Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">New Memory</h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Category</label>
                <select
                  value={newMemory.category || "fact"}
                  onChange={(e) => setNewMemory({ ...newMemory, category: e.target.value as MemoryCategory })}
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                >
                  {MEMORY_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Content</label>
                <textarea
                  value={newMemory.content || ""}
                  onChange={(e) => setNewMemory({ ...newMemory, content: e.target.value })}
                  placeholder="Enter memory content..."
                  className="w-full min-h-[100px] px-4 py-3 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light resize-none"
                  rows={4}
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
                <input
                  type="text"
                  value={newMemory.tags?.join(", ") || ""}
                  onChange={(e) => setNewMemory({ ...newMemory, tags: e.target.value.split(",").map(t => t.trim()).filter(Boolean) })}
                  placeholder="tag1, tag2, tag3"
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Importance: {newMemory.importance?.toFixed(1) || "1.0"}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={newMemory.importance ?? 1.0}
                  onChange={(e) => setNewMemory({ ...newMemory, importance: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => { setShowCreateModal(false); setNewMemory({ category: "fact", content: "", tags: [], importance: 1.0 }); }}
                className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newMemory.content?.trim()}
                className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50"
              >
                Create Memory
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Memory Modal */}
      {editingMemory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Edit Memory</h2>
              <button onClick={() => { setEditingMemory(null); setEditForm({}); }} className="p-1 hover:bg-background rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Category</label>
                <select
                  value={editForm.category || editingMemory.category}
                  onChange={(e) => setEditForm({ ...editForm, category: e.target.value as MemoryCategory })}
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                >
                  {MEMORY_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Content</label>
                <textarea
                  value={editForm.content || editingMemory.content}
                  onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                  className="w-full min-h-[100px] px-4 py-3 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light resize-none"
                  rows={4}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
                <input
                  type="text"
                  value={editForm.tags?.join(", ") || editingMemory.tags?.join(", ") || ""}
                  onChange={(e) => setEditForm({ ...editForm, tags: e.target.value.split(",").map(t => t.trim()).filter(Boolean) })}
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Importance: {editForm.importance?.toFixed(1) || editingMemory.importance.toFixed(1)}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={editForm.importance ?? editingMemory.importance}
                  onChange={(e) => setEditForm({ ...editForm, importance: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => { setEditingMemory(null); setEditForm({}); }}
                className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-2">Delete Memory</h2>
            <p className="text-sm text-muted mb-4">Are you sure you want to delete this memory? This cannot be undone.</p>
            <div className="p-3 bg-background border border-border rounded-lg text-sm mb-4">
              {confirmDelete.content.substring(0, 200)}...
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg">
                Cancel
              </button>
              <button onClick={handleDelete} className="px-4 py-2 text-sm bg-danger text-white rounded-lg hover:bg-danger-hover">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clear Memories Dialog */}
      {showClearDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-2">Clear Memories</h2>
            <p className="text-sm text-muted mb-4">
              This will permanently delete {clearCategory === "all" ? "all memories" : `all ${clearCategory} memories`}. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowClearDialog(false)} className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg">
                Cancel
              </button>
              <button onClick={handleClear} className="px-4 py-2 text-sm bg-danger text-white rounded-lg hover:bg-danger-hover">
                Clear
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Memory Card Component ---

interface MemoryCardProps {
  memory: Memory;
  onEdit: (memory: Memory) => void;
  onDelete: () => void;
}

function MemoryCard({ memory, onEdit, onDelete }: MemoryCardProps) {
  const categoryInfo = MEMORY_CATEGORIES.find((c) => c.value === memory.category);
  const categoryColor = CATEGORY_COLORS[memory.category] || "bg-gray-500/10 text-gray-500";

  return (
    <div className="p-4 hover:bg-background transition">
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${categoryColor}`}>
          {categoryInfo?.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`px-2 py-0.5 text-xs rounded ${categoryColor}`}>
              {categoryInfo?.label}
            </span>
            <span className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded">
              {memory.importance.toFixed(1)}
            </span>
            <span className="text-xs text-muted">{memory.source}</span>
          </div>
          <p className="text-sm text-text-secondary mb-2 line-clamp-3">{memory.content}</p>
          <div className="flex items-center gap-2 flex-wrap">
            {memory.tags?.map((tag) => (
              <span key={tag} className="px-2 py-0.5 text-xs bg-background border border-border rounded">
                {tag}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-4 mt-3 text-xs text-muted">
            <span>Created: {format(new Date(memory.created_at), "MMM d, yyyy")}</span>
            {memory.last_accessed && (
              <span>Last accessed: {formatDistanceToNow(new Date(memory.last_accessed), { addSuffix: true })}</span>
            )}
            <span>Accessed: {memory.access_count}x</span>
          </div>
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
          <button
            onClick={() => onEdit(memory)}
            className="p-1.5 rounded hover:bg-background transition text-muted"
            aria-label="Edit"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 rounded hover:bg-danger/10 text-danger transition"
            aria-label="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}