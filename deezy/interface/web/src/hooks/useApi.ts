/**
 * React hooks for Deezy API.
 * Provides typed, cached access to backend data.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  api,
  wsClient,
} from "../utils/api";
import type {
  Task,
  TaskCreateResponse,
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
  WebSocketMessage,
  TaskPlanEvent,
  TaskStepEvent,
  TaskCompletedEvent,
  TaskFailedEvent,
  TaskStep,
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

  const createTask = useCallback(async (objective: string): Promise<TaskCreateResponse> => {
    return api.createTask(objective);
  }, []);

  const getTask = useCallback(async (id: number): Promise<Task> => {
    return api.getTask(id);
  }, []);

  return {
    tasks: tasks || [],
    loading,
    error,
    loadTasks,
    createTask,
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
    loadMemories: (category?: string) => {
      if (category !== undefined) setCategoryFilter(category);
      loadMemories();
    },
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

// --- WebSocket Hook ---

export function useTaskWebSocket(taskId: number | null, onMessage?: (message: WebSocketMessage) => void) {
  const [connected, setConnected] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) return;

    let mounted = true;
    let client: WebSocket | null = null;

    const init = async () => {
      try {
        client = new WebSocket(`${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/client_${Date.now()}`);
        await new Promise<void>((resolve, reject) => {
          if (!client) return reject(new Error("No client"));
          client.onopen = () => resolve();
          client.onerror = () => reject(new Error("Connection failed"));
        });
        if (mounted) {
          setConnected(true);
          client.send(JSON.stringify({ type: "subscribe_task", task_id: taskId }));
          if (onMessage) {
            client.onmessage = (event) => {
              try {
                const message: WebSocketMessage = JSON.parse(event.data);
                onMessage(message);
              } catch (e) {
                console.error("[WS] Failed to parse message:", e);
              }
            };
          }
          setWs(client);
        }
      } catch (e) {
        console.error("[WS] Failed to connect:", e);
      }
    };

    init();

    return () => {
      mounted = false;
      if (client) {
        client.close();
      }
    };
  }, [taskId, onMessage]);

  return { connected };
}

// --- WebSocket Event Hooks ---

export function useWebSocketMessages() {
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);

  useEffect(() => {
    const ws = new WebSocket(`${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/client_${Date.now()}`);
    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev.slice(-99), message]);
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };
    return () => ws.close();
  }, []);

  return messages;
}

// --- Specific Event Hooks ---

export function useTaskEvents(taskId: number | null) {
  const [plan, setPlan] = useState<TaskPlanEvent | null>(null);
  const [currentStep, setCurrentStep] = useState<TaskStepEvent | null>(null);
  const [completed, setCompleted] = useState<TaskCompletedEvent | null>(null);
  const [failed, setFailed] = useState<TaskFailedEvent | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const ws = new WebSocket(`${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/client_${Date.now()}`);
    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data);
        if (msg.task_id !== taskId) return;

        switch (msg.type) {
          case "plan_created":
            setPlan(msg as TaskPlanEvent);
            break;
          case "step_started":
          case "step_completed":
          case "step_failed":
            setCurrentStep(msg as TaskStepEvent);
            break;
          case "task_completed":
            setCompleted(msg as TaskCompletedEvent);
            break;
          case "task_failed":
            setFailed(msg as TaskFailedEvent);
            break;
        }
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "subscribe_task", task_id: taskId }));
    };

    return () => ws.close();
  }, [taskId]);

  return { plan, currentStep, completed, failed };
}