/**
 * TypeScript type definitions for Deezy Web UI.
 * These types match the FastAPI backend contracts.
 */

// --- Base Types ---

export interface ApiResponse<T> {
  data: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// --- Settings Types ---

export interface LLMSettings {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface AgentSettings {
  max_iterations: number;
  max_tool_calls_per_iteration: number;
  enable_memory: boolean;
  memory_limit: number;
  approval_required_for_high_risk: boolean;
  approval_required_for_medium_risk: boolean;
  auto_approve_low_risk: boolean;
}

export interface VoiceSettings {
  enabled: boolean;
  stt_provider: "web_speech" | "whisper_local";
  tts_provider: "web_speech" | "local";
  language: string;
  auto_play: boolean;
  continuous: boolean;
  whisper_base_url?: string;
  whisper_model?: string;
}

export interface ApprovalSettings {
  risk_levels: Record<string, { auto_approve: boolean; actions: string[] }>;
  notification_methods: string[];
}

export interface Settings {
  llm: LLMSettings;
  agent: AgentSettings;
  voice: VoiceSettings;
  approval: ApprovalSettings;
}

// --- Task Types ---

export type TaskStatus = "pending" | "planning" | "running" | "waiting_for_approval" | "completed" | "failed" | "cancelled";

export type RiskLevel = "low" | "medium" | "high";

export interface TaskStep {
  step_id: string;
  description: string;
  tool: string;
  params: Record<string, any>;
  status: TaskStatus;
  risk_level: RiskLevel;
  verified: boolean;
  result?: any;
  error?: string;
}

export interface Task {
  id: number;
  objective: string;
  user_input: string;
  status: TaskStatus;
  created_at: string;
  completed_at?: string;
  steps: TaskStep[];
  current_step_index: number;
  plan_version: number;
  risk_level: RiskLevel;
  result?: {
    message?: string;
    data?: any;
  };
}

export interface TaskCreate {
  objective: string;
}

export interface TaskCreateResponse {
  task_id: number;
}

// --- Conversation Types ---

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  metadata?: Record<string, any>;
  timestamp: string;
}

export interface ConversationBase {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Conversation extends ConversationBase {
  messages: ConversationMessage[];
}

export interface ConversationCreate {
  title: string;
}

export interface ConversationUpdate {
  title: string;
}

export interface ConversationExport {
  id: string;
  title: string;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

export interface ConversationImport {
  title: string;
  messages: ConversationMessage[];
}

export interface ConversationBranch {
  conversation_id: string;
  message_index: number;
  title: string;
}

export interface ConversationBranchResult {
  conversation_id: string;
}

// --- Memory Types ---

export type MemoryCategory = "fact" | "preference" | "project" | "task" | "decision" | "observation" | "conversation";

export interface Memory {
  id: number;
  category: MemoryCategory;
  content: string;
  tags: string[];
  importance: number;
  source: "user" | "agent" | "system";
  access_count: number;
  last_accessed?: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryCreate {
  category: MemoryCategory;
  content: string;
  tags?: string[];
  importance?: number;
  source?: "user" | "agent" | "system";
}

export interface MemoryUpdate {
  category?: MemoryCategory;
  content?: string;
  tags?: string[];
  importance?: number;
}

// --- Tool Types ---

export interface ToolParameter {
  name: string;
  type: "string" | "integer" | "number" | "boolean" | "array" | "object";
  description: string;
  required?: boolean;
  default?: any;
}

export interface ToolSchema {
  name: string;
  description: string;
  category: string;
  risk_level: RiskLevel;
  parameters: {
    type: "object";
    properties: Record<string, any>;
    required: string[];
  };
}

// --- WebSocket Types ---

export interface WebSocketMessage {
  type: string;
  task_id?: number;
  [key: string]: any;
}

export interface TaskPlanEvent extends WebSocketMessage {
  type: "plan_created";
  plan: Array<{
    step_id: string;
    description: string;
    tool: string;
    params: Record<string, any>;
    risk_level: RiskLevel;
    requires_approval: boolean;
    depends_on: string[];
    verification_criteria: string;
  }>;
}

export interface TaskStepEvent extends WebSocketMessage {
  type: "step_started" | "step_completed" | "step_failed";
  step: TaskStep;
  error?: string;
}

export interface TaskCompletedEvent extends WebSocketMessage {
  type: "task_completed";
  result?: {
    message?: string;
    data?: any;
  };
}

export interface TaskFailedEvent extends WebSocketMessage {
  type: "task_failed";
  error?: string;
}

export interface SubscribeTaskMessage {
  type: "subscribe_task";
  task_id: number;
}

export interface SubscribedMessage {
  type: "subscribed";
  task_id: number;
}

// --- Chat Types ---

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// --- UI State Types ---

export type VoiceRecordingState = "idle" | "recording" | "processing";
export type VoiceSpeakingState = "idle" | "speaking" | "paused";

export interface SpeechRecognitionResult {
  transcript: string;
  isFinal: boolean;
}

export interface SpeechRecognitionOptions {
  language?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onResult?: (result: SpeechRecognitionResult) => void;
  onError?: (error: Error) => void;
  onEnd?: () => void;
}

export interface SpeechSynthesisOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: Error) => void;
}

// --- Hook Return Types ---

export interface UseTasksReturn {
  tasks: Task[];
  loading: boolean;
  error: string | null;
  loadTasks: () => Promise<void>;
  createTask: (objective: string) => Promise<TaskCreateResponse>;
  getTask: (id: number) => Promise<Task>;
}

export interface UseConversationsReturn {
  conversations: ConversationBase[];
  loading: boolean;
  error: string | null;
  loadConversations: () => Promise<void>;
  createConversation: (title: string) => Promise<ConversationBase>;
  deleteConversation: (id: string) => Promise<void>;
  updateConversation: (id: string, title: string) => Promise<ConversationBase>;
  getConversation: (id: string) => Promise<Conversation>;
  addConversationMessage: (id: string, message: ConversationMessage) => Promise<void>;
  exportConversation: (id: string) => Promise<ConversationExport>;
  importConversation: (data: ConversationImport) => Promise<ConversationBase>;
  createBranch: (id: string, messageIndex: number, title: string) => Promise<ConversationBranchResult>;
}

export interface UseMemoriesReturn {
  memories: Memory[];
  loading: boolean;
  error: string | null;
  loadMemories: (category?: string) => Promise<void>;
  createMemory: (memory: MemoryCreate) => Promise<Memory>;
  updateMemory: (id: number, update: MemoryUpdate) => Promise<Memory>;
  deleteMemory: (id: number) => Promise<void>;
  clearMemories: (category?: string) => Promise<void>;
}

export interface UseSettingsReturn {
  settings: Settings | null;
  loading: boolean;
  error: string | null;
  loadSettings: () => Promise<void>;
  updateSettings: (update: Partial<Settings>) => Promise<Settings>;
}

export interface UseApiReturn extends UseTasksReturn, UseConversationsReturn, UseMemoriesReturn, UseSettingsReturn {
  tools: ToolSchema[];
}