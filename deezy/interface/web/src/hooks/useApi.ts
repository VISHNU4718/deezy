/**
 * React hooks for Deezy API.
 * Provides typed, cached access to backend data.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "../utils/api";
import type {
  Task,
  ConversationBase,
  Conversation,
  ConversationMessage,
  ConversationExport,
  ConversationImport,
  ConversationBranch,
  ConversationBranchResult,
  Memory,
  MemoryCreate,
  MemoryUpdate,
  Settings,
  ToolSchema,
} from "../types";

// --- Generic Hook Helpers ---

function useAsync<T>(
  asyncFn: () => Promise<T>,
  deps: React.DependencyList = []
): { data: T | null; loading: boolean; error: string | null; refresh: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await asyncFn();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    execute();
  }, deps);

  return { data, loading, error, refresh: execute };
}

// --- Tasks Hook ---

export function useTasks() {
  const { data: tasks, loading, error, refresh: loadTasks } = useAsync(() => api.getTasks(), []);

  const createTask = useCallback(async (objective: string): Promise<Task> => {
    return api.createTask(objective);
  }, []);

  const approveTask = useCallback(async (id: number): Promise<Task> => api.approveTask(id), []);
  const rejectTask = useCallback(async (id: number): Promise<Task> => api.rejectTask(id), []);

  const getTask = useCallback(async (id: number): Promise<Task> => {
    return api.getTask(id);
  }, []);

  return {
    tasks: tasks || [],
    loading,
    error,
    loadTasks,
    createTask,
    approveTask,
    rejectTask,
    getTask,
  };
}

// --- Conversations Hook ---

export function useConversations() {
  const { data: conversations, loading, error, refresh: loadConversations } = useAsync(
    () => api.getConversations(),
    []
  );

  const createConversation = useCallback(async (title: string): Promise<ConversationBase> => {
    const result = await api.createConversation(title);
    loadConversations();
    return result;
  }, [loadConversations]);

  const deleteConversation = useCallback(async (id: string): Promise<void> => {
    await api.deleteConversation(id);
    loadConversations();
  }, [loadConversations]);

  const updateConversation = useCallback(
    async (id: string, title: string): Promise<ConversationBase> => {
      const result = await api.updateConversation(id, title);
      loadConversations();
      return result;
    },
    [loadConversations]
  );

  const getConversation = useCallback(async (id: string): Promise<Conversation> => {
    return api.getConversation(id);
  }, []);

  const addConversationMessage = useCallback(
    async (id: string, message: ConversationMessage): Promise<void> => {
      await api.addConversationMessage(id, message);
    },
    []
  );

  const exportConversation = useCallback(async (id: string): Promise<ConversationExport> => {
    return api.exportConversation(id);
  }, []);

  const importConversation = useCallback(async (data: ConversationImport): Promise<ConversationBase> => {
    const result = await api.importConversation(data);
    loadConversations();
    return result;
  }, [loadConversations]);

  const createBranch = useCallback(
    async (id: string, messageIndex: number, title: string): Promise<ConversationBranchResult> => {
      const result = await api.createBranch(id, messageIndex, title);
      loadConversations();
      return result;
    },
    [loadConversations]
  );

  return {
    conversations: conversations || [],
    loading,
    error,
    loadConversations,
    createConversation,
    deleteConversation,
    updateConversation,
    getConversation,
    addConversationMessage,
    exportConversation,
    importConversation,
    createBranch,
  };
}

// --- Memories Hook ---

export function useMemories() {
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  
  const { data: memories, loading, error, refresh: loadMemories } = useAsync(
    () => api.getMemories(categoryFilter),
    [categoryFilter]
  );

  const createMemory = useCallback(async (memory: MemoryCreate): Promise<Memory> => {
    const result = await api.createMemory(memory);
    loadMemories();
    return result;
  }, [loadMemories]);

  const updateMemory = useCallback(async (id: number, update: MemoryUpdate): Promise<Memory> => {
    const result = await api.updateMemory(id, update);
    loadMemories();
    return result;
  }, [loadMemories]);

  const deleteMemory = useCallback(async (id: number): Promise<void> => {
    await api.deleteMemory(id);
    loadMemories();
  }, [loadMemories]);

  const clearMemories = useCallback(async (category?: string): Promise<void> => {
    await api.clearMemories(category);
    loadMemories();
  }, [loadMemories]);

  const setCategory = useCallback((category?: string) => {
    setCategoryFilter(category);
  }, []);

  return {
    memories: memories || [],
    loading,
    error,
    loadMemories: setCategory,
    createMemory,
    updateMemory,
    deleteMemory,
    clearMemories,
  };
}

// --- Settings Hook ---

export function useSettings() {
  const { data: settings, loading, error, refresh: loadSettings } = useAsync(
    () => api.getSettings(),
    []
  );

  const updateSettings = useCallback(async (update: Partial<Settings>): Promise<Settings> => {
    const result = await api.updateSettings(update);
    loadSettings();
    return result;
  }, [loadSettings]);

  return {
    settings,
    loading,
    error,
    loadSettings,
    updateSettings,
  };
}

// --- Tools Hook ---

export function useTools() {
  const { data: tools, loading, error, refresh: loadTools } = useAsync(() => api.getTools(), []);

  return {
    tools: tools || [],
    loading,
    error,
    loadTools,
  };
}

// --- Combined Hook ---

export function useApi() {
  const tasks = useTasks();
  const conversations = useConversations();
  const memories = useMemories();
  const settings = useSettings();
  const tools = useTools();

  return {
    ...tasks,
    ...conversations,
    ...memories,
    ...settings,
    ...tools,
  };
}

// --- Health Hook ---

export function useHealth() {
  const { data, error } = useAsync(() => api.healthCheck(), []);
  return { health: data, error };
}
