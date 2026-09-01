/**
 * API client and WebSocket utilities for Deezy Web UI.
 */

import type {
  Task,
  TaskCreateResponse,
  ConversationBase,
  Conversation,
  ConversationCreate,
  ConversationUpdate,
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
  SubscribeTaskMessage,
  SubscribedMessage,
} from "../types";

const API_BASE = "/api";
const WS_BASE = typeof window !== "undefined" 
  ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`
  : "";

// --- Generic API Client ---

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // --- Settings ---
  async getSettings(): Promise<Settings> {
    return this.request<Settings>("/settings");
  }

  async updateSettings(update: Partial<Settings>): Promise<Settings> {
    return this.request<Settings>("/settings", {
      method: "PUT",
      body: JSON.stringify(update),
    });
  }

  // --- Tasks ---
  async getTasks(status?: string): Promise<Task[]> {
    const params = status ? `?status=${encodeURIComponent(status)}` : "";
    return this.request<Task[]>(`/tasks${params}`);
  }

  async createTask(objective: string): Promise<TaskCreateResponse> {
    return this.request<TaskCreateResponse>("/tasks", {
      method: "POST",
      body: JSON.stringify({ objective }),
    });
  }

  async getTask(id: number): Promise<Task> {
    return this.request<Task>(`/tasks/${id}`);
  }

  // --- Conversations ---
  async getConversations(): Promise<ConversationBase[]> {
    return this.request<ConversationBase[]>("/conversations");
  }

  async createConversation(title: string): Promise<ConversationBase> {
    return this.request<ConversationBase>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  async getConversation(id: string): Promise<Conversation> {
    return this.request<Conversation>(`/conversations/${id}`);
  }

  async updateConversation(id: string, title: string): Promise<ConversationBase> {
    return this.request<ConversationBase>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  }

  async deleteConversation(id: string): Promise<void> {
    return this.request<void>(`/conversations/${id}`, {
      method: "DELETE",
    });
  }

  async addConversationMessage(id: string, message: ConversationMessage): Promise<void> {
    return this.request<void>(`/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify(message),
    });
  }

  async exportConversation(id: string): Promise<ConversationExport> {
    return this.request<ConversationExport>(`/conversations/${id}/export`);
  }

  async importConversation(data: ConversationImport): Promise<ConversationBase> {
    return this.request<ConversationBase>("/conversations/import", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async createBranch(id: string, messageIndex: number, title: string): Promise<ConversationBranchResult> {
    return this.request<ConversationBranchResult>(`/conversations/${id}/branch`, {
      method: "POST",
      body: JSON.stringify({ conversation_id: id, message_index: messageIndex, title }),
    });
  }

  // --- Memories ---
  async getMemories(category?: string): Promise<Memory[]> {
    const params = category ? `?category=${encodeURIComponent(category)}` : "";
    return this.request<Memory[]>(`/memories${params}`);
  }

  async createMemory(memory: MemoryCreate): Promise<Memory> {
    return this.request<Memory>("/memories", {
      method: "POST",
      body: JSON.stringify(memory),
    });
  }

  async updateMemory(id: number, update: MemoryUpdate): Promise<Memory> {
    return this.request<Memory>(`/memories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    });
  }

  async deleteMemory(id: number): Promise<void> {
    return this.request<void>(`/memories/${id}`, {
      method: "DELETE",
    });
  }

  async clearMemories(category?: string): Promise<void> {
    const params = category ? `?category=${encodeURIComponent(category)}` : "";
    return this.request<void>(`/memories${params}`, {
      method: "DELETE",
    });
  }

  // --- Tools ---
  async getTools(): Promise<ToolSchema[]> {
    return this.request<ToolSchema[]>("/tools");
  }

  // --- History ---
  async getHistory(): Promise<Task[]> {
    return this.request<Task[]>("/history");
  }

  // --- Health ---
  async healthCheck(): Promise<{ status: string; version: string }> {
    return this.request<{ status: string; version: string }>("/health");
  }
}

// Export singleton instance
export const api = new ApiClient();

// --- WebSocket Client ---

type WSMessageHandler = (message: WebSocketMessage) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private clientId: string;
  private handlers: Set<WSMessageHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(clientId?: string) {
    this.clientId = clientId || `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      const wsUrl = `${WS_BASE}/${this.clientId}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[WS] Connected");
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handlers.forEach((handler) => handler(message));
        } catch (e) {
          console.error("[WS] Failed to parse message:", e);
        }
      };

      this.ws.onclose = () => {
        console.log("[WS] Disconnected");
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("[WS] Error:", error);
        if (this.ws?.readyState === WebSocket.CONNECTING) {
          reject(error);
        }
      };
    });
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log("[WS] Max reconnect attempts reached");
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    setTimeout(() => {
      console.log(`[WS] Reconnecting (attempt ${this.reconnectAttempts})...`);
      this.connect().catch(() => {});
    }, delay);
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(message: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("[WS] Cannot send: not connected");
    }
  }

  subscribe(handler: WSMessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  // Convenience methods
  subscribeToTask(taskId: number): void {
    this.send({ type: "subscribe_task", task_id: taskId } as SubscribeTaskMessage);
  }
}

// Export singleton WebSocket client
export const wsClient = new WebSocketClient();

// --- Helper Functions ---

export async function createWebSocket(clientId?: string): Promise<WebSocketClient> {
  const client = new WebSocketClient(clientId);
  await client.connect();
  return client;
}

export function subscribeToConversation(ws: WebSocketClient, conversationId: string): void {
  // Could be used for conversation-specific subscriptions
  ws.send({ type: "subscribe_conversation", conversation_id: conversationId });
}

export function unsubscribeFromConversation(ws: WebSocketClient, conversationId: string): void {
  ws.send({ type: "unsubscribe_conversation", conversation_id: conversationId });
}