/**
 * API client for the Deezy web UI.
 */

import type {
  Task,
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
} from "../types";

const API_BASE = "/api";

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

  async createTask(objective: string): Promise<Task> {
    return this.request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify({ objective }),
    });
  }

  async approveTask(id: number): Promise<Task> {
    return this.request<Task>(`/tasks/${id}/approve`, { method: "POST" });
  }

  async rejectTask(id: number): Promise<Task> {
    return this.request<Task>(`/tasks/${id}/reject`, { method: "POST" });
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
  async healthCheck(): Promise<{ status: string; version: string; demo: boolean }> {
    return this.request<{ status: string; version: string; demo: boolean }>("/health");
  }
}

// Export singleton instance
export const api = new ApiClient();
