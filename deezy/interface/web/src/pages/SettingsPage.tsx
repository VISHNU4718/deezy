/**
 * Settings Page - LLM, Agent, Voice, and Approval configuration.
 */

import React, { useState, useEffect, useMemo } from "react";
import { Save, Loader2, AlertCircle, CheckCircle, Volume2, Mic, Brain, Shield, Bell, RotateCcw } from "lucide-react";
import { useSettings, useApi, useHealth } from "../hooks/useApi";
import type { Settings, LLMSettings, AgentSettings, VoiceSettings, ApprovalSettings } from "../types";

const LLM_PROVIDERS = [
  { value: "local", label: "Ollama (Local)" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "mock", label: "Mock (Testing)" },
];

const LLM_MODELS: Record<string, string[]> = {
  local: ["llama3.2:3b", "llama3.1:8b", "qwen2.5:7b", "gemma2:9b", "phi3:3.8b"],
  openrouter: ["openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.1-70b", "google/gemini-pro-1.5"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-3.5-sonnet", "claude-3.5-haiku", "claude-3-opus"],
  mock: ["mock-model"],
};

const LANGUAGES = [
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "es-ES", label: "Spanish" },
  { value: "fr-FR", label: "French" },
  { value: "de-DE", label: "German" },
  { value: "it-IT", label: "Italian" },
  { value: "ja-JP", label: "Japanese" },
  { value: "zh-CN", label: "Chinese (Simplified)" },
  { value: "ko-KR", label: "Korean" },
];

const RISK_LEVELS = [
  { value: "low", label: "Low Risk", description: "Auto-approve (read, search, analyze)" },
  { value: "medium", label: "Medium Risk", description: "Ask before execution (write, modify)" },
  { value: "high", label: "High Risk", description: "Always require approval (delete, publish, system changes)" },
];

export function SettingsPage() {
  const { settings, loading, error, updateSettings } = useSettings();
  const { loadTools } = useApi();

  // Initialize with defaults to avoid partial type issues
  const defaultSettings: Settings = {
    llm: { provider: "local", model: "llama3.2:3b", temperature: 0.3, max_tokens: 4000 },
    agent: { max_iterations: 10, max_tool_calls_per_iteration: 3, enable_memory: true, memory_limit: 50, approval_required_for_high_risk: true, approval_required_for_medium_risk: false, auto_approve_low_risk: true },
    voice: { enabled: true, stt_provider: "web_speech", tts_provider: "web_speech", language: "en-US", auto_play: true, continuous: false },
    approval: { risk_levels: { low: { auto_approve: true, actions: [] }, medium: { auto_approve: false, actions: [] }, high: { auto_approve: false, actions: [] } }, notification_methods: ["cli"] },
  };

  const [localSettings, setLocalSettings] = useState<Settings>(defaultSettings);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [activeTab, setActiveTab] = useState<"llm" | "agent" | "voice" | "approval">("llm");

  // Sync local settings with loaded settings
  useEffect(() => {
    if (settings) {
      setLocalSettings({
        llm: { ...defaultSettings.llm, ...settings.llm },
        agent: { ...defaultSettings.agent, ...settings.agent },
        voice: { ...defaultSettings.voice, ...settings.voice },
        approval: { ...defaultSettings.approval, ...settings.approval },
      });
    }
  }, [settings]);

  const availableModels = useMemo(() => LLM_MODELS[localSettings.llm?.provider || "local"] || [], [localSettings.llm?.provider]);

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus("idle");
    try {
      await updateSettings(localSettings);
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch (e) {
      console.error("Failed to save settings:", e);
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (settings) {
      setLocalSettings({
        llm: { ...settings.llm },
        agent: { ...settings.agent },
        voice: { ...settings.voice },
        approval: { ...settings.approval },
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-danger">
        <AlertCircle className="w-6 h-6 mr-2" />
        Failed to load settings: {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto w-full space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted text-sm">Configure Deezy behavior and preferences</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface border border-border rounded-lg p-1">
        {([
          { id: "llm", label: "LLM", icon: Brain },
          { id: "agent", label: "Agent", icon: RotateCcw },
          { id: "voice", label: "Voice", icon: Mic },
          { id: "approval", label: "Approval", icon: Shield },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition ${
              activeTab === tab.id
                ? "bg-primary text-white"
                : "text-text-secondary hover:bg-background hover:text-text"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        {activeTab === "llm" && <LLMSettingsTab settings={localSettings.llm} onChange={(s) => setLocalSettings((p) => ({ ...p, llm: s }))} availableModels={availableModels} />}
        {activeTab === "agent" && <AgentSettingsTab settings={localSettings.agent} onChange={(s) => setLocalSettings((p) => ({ ...p, agent: s }))} />}
        {activeTab === "voice" && <VoiceSettingsTab settings={localSettings.voice} onChange={(s) => setLocalSettings((p) => ({ ...p, voice: s }))} />}
        {activeTab === "approval" && <ApprovalSettingsTab settings={localSettings.approval} onChange={(s) => setLocalSettings((p) => ({ ...p, approval: s }))} />}
      </div>

      {/* Save Bar */}
      <div className="flex items-center justify-between pt-4 border-t border-border">
        <div className="flex items-center gap-3">
          <button
            onClick={handleReset}
            disabled={saving}
            className="px-4 py-2 text-sm text-text-secondary hover:bg-background rounded-lg transition disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4 mr-1" />
            Reset
          </button>
          {saveStatus === "success" && (
            <span className="flex items-center gap-1 text-sm text-success">
              <CheckCircle className="w-4 h-4" />
              Settings saved
            </span>
          )}
          {saveStatus === "error" && (
            <span className="flex items-center gap-1 text-sm text-danger">
              <AlertCircle className="w-4 h-4" />
              Failed to save
            </span>
          )}
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50 transition"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          <span>{saving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    </div>
  );
}

// --- Sub-components ---

function LLMSettingsTab({ settings, onChange, availableModels }: { settings: LLMSettings; onChange: (s: LLMSettings) => void; availableModels: string[] }) {
  const { health } = useHealth();
  if (health?.demo) {
    return (
      <div className="p-6 space-y-2" data-testid="llm-demo-lock">
        <h3 className="font-semibold text-lg">LLM Provider</h3>
        <p className="text-sm text-muted">
          This hosted demo runs a deterministic planner with simulated tools, so no model is configured here.
          Run Deezy locally to use Ollama or OpenRouter.
        </p>
      </div>
    );
  }
  return (
    <div className="p-6 space-y-6">
      <div>
        <h3 className="font-semibold text-lg mb-2">LLM Provider</h3>
        <p className="text-sm text-muted">Choose your language model provider</p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Provider</label>
          <select
            value={settings.provider || "local"}
            onChange={(e) => onChange({ ...settings, provider: e.target.value, model: availableModels[0] })}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          >
            {LLM_PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Model</label>
          <select
            value={settings.model || availableModels[0]}
            onChange={(e) => onChange({ ...settings, model: e.target.value })}
            className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
          >
            {availableModels.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Temperature</label>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={settings.temperature ?? 0.3}
              onChange={(e) => onChange({ ...settings, temperature: parseFloat(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-muted mt-1">Current: {settings.temperature ?? 0.3}</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Max Tokens</label>
            <input
              type="number"
              min="100"
              max="8000"
              step="100"
              value={settings.max_tokens ?? 4000}
              onChange={(e) => onChange({ ...settings, max_tokens: parseInt(e.target.value) || 4000 })}
              className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
            />
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-border text-xs text-muted">
        <p>Changes take effect on next task. Local provider requires <code>ollama serve</code> running.</p>
      </div>
    </div>
  );
}

function AgentSettingsTab({ settings, onChange }: { settings: AgentSettings; onChange: (s: AgentSettings) => void }) {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h3 className="font-semibold text-lg mb-2">Agent Behavior</h3>
        <p className="text-sm text-muted">Configure how the agent plans and executes tasks</p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Max Iterations</label>
            <input
              type="number"
              min="1"
              max="50"
              value={settings.max_iterations ?? 10}
              onChange={(e) => onChange({ ...settings, max_iterations: parseInt(e.target.value) || 10 })}
              className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
            />
            <p className="text-xs text-muted mt-1">Maximum planning/execution cycles</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Max Tool Calls/Iteration</label>
            <input
              type="number"
              min="1"
              max="10"
              value={settings.max_tool_calls_per_iteration ?? 3}
              onChange={(e) => onChange({ ...settings, max_tool_calls_per_iteration: parseInt(e.target.value) || 3 })}
              className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
            />
            <p className="text-xs text-muted mt-1">Tools allowed per step</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Memory Limit</label>
            <input
              type="number"
              min="10"
              max="200"
              value={settings.memory_limit ?? 50}
              onChange={(e) => onChange({ ...settings, memory_limit: parseInt(e.target.value) || 50 })}
              className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
            />
            <p className="text-xs text-muted mt-1">Recent messages in context</p>
          </div>
        </div>

        <div className="space-y-3 pt-2 border-t border-border">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enable_memory ?? true}
              onChange={(e) => onChange({ ...settings, enable_memory: e.target.checked })}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm">Enable long-term memory</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.auto_approve_low_risk ?? true}
              onChange={(e) => onChange({ ...settings, auto_approve_low_risk: e.target.checked })}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm">Auto-approve low risk actions</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.approval_required_for_medium_risk ?? false}
              onChange={(e) => onChange({ ...settings, approval_required_for_medium_risk: e.target.checked })}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm">Require approval for medium risk</span>
          </label>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.approval_required_for_high_risk ?? true}
              onChange={(e) => onChange({ ...settings, approval_required_for_high_risk: e.target.checked })}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
            <span className="text-sm">Require approval for high risk</span>
          </label>
        </div>
      </div>
    </div>
  );
}

function VoiceSettingsTab({ settings, onChange }: { settings: VoiceSettings; onChange: (s: VoiceSettings) => void }) {
  const isSupported = typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h3 className="font-semibold text-lg mb-2">Voice Integration</h3>
        <p className="text-sm text-muted">Configure speech-to-text and text-to-speech</p>
      </div>

      {!isSupported && (
        <div className="p-4 bg-warning/10 border border-warning/20 rounded-lg text-warning text-sm">
          <p>⚠️ Web Speech API not supported in this browser. Voice features require Chrome, Edge, or Safari.</p>
        </div>
      )}

      <div className="space-y-6">
        <div className="pt-2 border-t border-border">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enabled ?? true}
              onChange={(e) => onChange({ ...settings, enabled: e.target.checked })}
              className="w-5 h-5 rounded border-border text-primary focus:ring-primary"
            />
            <div>
              <span className="font-medium">Enable Voice Features</span>
              <p className="text-xs text-muted">Speech-to-text and text-to-speech</p>
            </div>
          </label>
        </div>

        {settings.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">STT Provider</label>
                <select
                  value={settings.stt_provider || "web_speech"}
                  onChange={(e) => onChange({ ...settings, stt_provider: e.target.value as "web_speech" | "whisper_local" })}
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                >
                  <option value="web_speech">Web Speech API (Browser-native, Free)</option>
                  <option value="whisper_local">Whisper Local (Requires local server)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">TTS Provider</label>
                <select
                  value={settings.tts_provider || "web_speech"}
                  onChange={(e) => onChange({ ...settings, tts_provider: e.target.value as "web_speech" | "local" })}
                  className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                >
                  <option value="web_speech">Web Speech API (Browser-native, Free)</option>
                  <option value="local">Local TTS (Requires local server)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Language</label>
              <select
                value={settings.language || "en-US"}
                onChange={(e) => onChange({ ...settings, language: e.target.value })}
                className="w-full max-w-md px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>

            <div className="space-y-3 pt-2 border-t border-border">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.auto_play ?? true}
                  onChange={(e) => onChange({ ...settings, auto_play: e.target.checked })}
                  className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-sm">Auto-play assistant responses</span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.continuous ?? false}
                  onChange={(e) => onChange({ ...settings, continuous: e.target.checked })}
                  className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-sm">Continuous listening (keep mic active)</span>
              </label>
            </div>

            {(settings.stt_provider === "whisper_local" || settings.tts_provider === "local") && (
              <div className="p-4 bg-background border border-border rounded-lg space-y-3">
                <h4 className="font-medium">Local Server Configuration</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Whisper Base URL</label>
                    <input
                      type="text"
                      value={settings.whisper_base_url || "http://localhost:8000"}
                      onChange={(e) => onChange({ ...settings, whisper_base_url: e.target.value })}
                      className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                      placeholder="http://localhost:8000"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Whisper Model</label>
                    <select
                      value={settings.whisper_model || "base"}
                      onChange={(e) => onChange({ ...settings, whisper_model: e.target.value })}
                      className="w-full px-4 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-light"
                    >
                      <option value="tiny">Tiny (Fastest, least accurate)</option>
                      <option value="base">Base (Balanced)</option>
                      <option value="small">Small</option>
                      <option value="medium">Medium</option>
                      <option value="large">Large (Slowest, most accurate)</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ApprovalSettingsTab({ settings, onChange }: { settings: ApprovalSettings; onChange: (s: ApprovalSettings) => void }) {
  const riskLevels = settings.risk_levels || {
    low: { auto_approve: true, actions: ["research", "analysis", "generate_draft", "generate_recommendation"] },
    medium: { auto_approve: false, actions: ["update_content", "update_product"] },
    high: { auto_approve: false, actions: ["publish_product", "delete_product", "modify_website_settings", "publish_pinterest_content"] },
  };

  const notificationMethods = settings.notification_methods || ["cli"];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h3 className="font-semibold text-lg mb-2">Approval System</h3>
        <p className="text-sm text-muted">Configure when Deezy needs your permission</p>
      </div>

      <div className="space-y-4">
        {RISK_LEVELS.map((rl) => {
          const config = riskLevels[rl.value] || { auto_approve: false, actions: [] };
          return (
            <div key={rl.value} className="p-4 bg-background border border-border rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <span className="font-medium capitalize">{rl.value} Risk</span>
                  <p className="text-xs text-muted mt-1">{rl.description}</p>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.auto_approve}
                    onChange={(e) => onChange({
                      ...settings,
                      risk_levels: { ...riskLevels, [rl.value]: { ...config, auto_approve: e.target.checked } }
                    })}
                    className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                  />
                  <span className="text-sm">Auto-approve</span>
                </label>
              </div>
              <div className="text-xs text-muted space-y-1">
                <p>Actions: {config.actions.join(", ") || "None"}</p>
              </div>
            </div>
          );
        })}

        <div className="pt-4 border-t border-border">
          <h4 className="font-medium mb-3">Notification Methods</h4>
          <div className="space-y-2">
            {["cli", "email", "webhook"].map((method) => (
              <label key={method} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notificationMethods.includes(method)}
                  onChange={(e) => {
                    const newMethods = e.target.checked
                      ? [...notificationMethods, method]
                      : notificationMethods.filter((m) => m !== method);
                    onChange({ ...settings, notification_methods: newMethods });
                  }}
                  className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-sm capitalize">{method}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}