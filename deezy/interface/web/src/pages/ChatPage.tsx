import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Mic, Paperclip, Bot, Loader2, X, Check, AlertTriangle, Copy, ThumbsUp, ThumbsDown, Volume2, VolumeX, MicOff } from 'lucide-react';
import { useTasks, useConversations, useTaskEvents } from '../hooks/useApi';
import { useSpeechRecognition, useSpeechSynthesis } from '../utils/voice';
import type { ChatMessage, Task, TaskStep } from '../types';
import { format } from 'date-fns';

export function ChatPage() {
  const params = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const conversationId = params.conversationId;
  const { createTask, getTask } = useTasks();
  const { getConversation, addConversationMessage } = useConversations();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<Task | null>(null);
  const [showTaskPanel, setShowTaskPanel] = useState(false);
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load conversation messages when conversationId changes
  useEffect(() => {
    if (conversationId) {
      const loadConversation = async () => {
        try {
          const conv = await getConversation(conversationId);
          if (conv.messages && conv.messages.length > 0) {
            setMessages(conv.messages.map(m => ({ ...m, id: m.id || `msg_${Date.now()}` })) as ChatMessage[]);
          } else {
            setMessages([]);
          }
        } catch (e) {
          console.error('Failed to load conversation:', e);
          setMessages([]);
        }
      };
      loadConversation();
    } else {
      setMessages([]);
    }
  }, [conversationId, getConversation]);

  // Voice recording
  const {
    state: recordingState,
    transcript,
    start: startRecording,
    stop: stopRecording,
    abort: abortRecording,
    isSupported: isSTTSupported,
  } = useSpeechRecognition({
    language: 'en-US',
    continuous: false,
    interimResults: true,
    onResult: (result) => {
      if (result.isFinal && result.transcript.trim()) {
        setInput(result.transcript.trim());
      }
    },
    onError: (error) => {
      console.error('Speech recognition error:', error);
    },
    onEnd: () => {
      // Recording ended
    },
  });

  // Voice playback (TTS)
  const {
    state: speakingState,
    speak,
    cancel: cancelSpeaking,
    isSupported: isTTSSupported,
  } = useSpeechSynthesis({
    onStart: () => {
      // Started speaking
    },
    onEnd: () => {
      // Finished speaking
    },
    onError: (error) => {
      console.error('Speech synthesis error:', error);
    },
  });

  // Task events via WebSocket hook
  const { plan, currentStep, completed, failed } = useTaskEvents(currentTask?.id || null);

  // Sync task state with WebSocket events
  useEffect(() => {
    if (plan) {
      setCurrentTask(prev => prev ? {
        ...prev,
        steps: plan.plan.map((p, i) => ({
          step_id: p.step_id,
          description: p.description,
          tool: p.tool,
          params: {},
          verified: false,
          risk_level: p.risk_level as 'low' | 'medium' | 'high',
          status: i === 0 ? 'running' : 'pending',
        })),
        status: 'running',
      } : null);
    }
  }, [plan]);

  useEffect(() => {
    if (currentStep) {
      setCurrentTask(prev => prev ? {
        ...prev,
        steps: prev.steps.map(s =>
          s.step_id === currentStep.step.step_id
            ? { ...s, status: 'running' as const }
            : s
        ),
      } : null);
    }
  }, [currentStep]);

  useEffect(() => {
    if (currentStep && currentStep.type === 'step_completed') {
      setCurrentTask(prev => prev ? {
        ...prev,
        steps: prev.steps.map(s =>
          s.step_id === currentStep.step.step_id
            ? { ...s, ...currentStep.step, status: 'completed' as const, verified: true }
            : s
        ),
      } : null);
    }
  }, [currentStep]);

  useEffect(() => {
    if (currentStep && currentStep.type === 'step_failed') {
      setCurrentTask(prev => prev ? {
        ...prev,
        steps: prev.steps.map(s =>
          s.step_id === currentStep.step.step_id
            ? { ...s, ...currentStep.step, status: 'failed' as const, error: currentStep.error }
            : s
        ),
      } : null);
    }
  }, [currentStep]);

  useEffect(() => {
    if (completed) {
      setCurrentTask(prev => prev ? { ...prev, status: 'completed' as const, result: completed.result } : null);
      setIsLoading(false);
      if (completed.result?.message) {
        setMessages(prev => [...prev, {
          id: `msg_${Date.now()}`,
          role: 'assistant',
          content: completed.result.message,
          timestamp: new Date().toISOString(),
        }]);
      }
    }
  }, [completed]);

  useEffect(() => {
    if (failed) {
      setCurrentTask(prev => prev ? { ...prev, status: 'failed' as const } : null);
      setIsLoading(false);
      setMessages(prev => [...prev, {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: `Task failed: ${failed.error || 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [failed]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentTask]);

  const sendMessage = async () => {
    const text = input.trim() || transcript.trim();
    if (!text || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Cancel any ongoing TTS when user sends new message
    cancelSpeaking();

    try {
      const taskResult = await createTask(text);
      setCurrentTask({
        id: taskResult.task_id,
        objective: text,
        user_input: '',
        status: 'planning',
        created_at: new Date().toISOString(),
        steps: [],
        current_step_index: 0,
        plan_version: 1,
        risk_level: 'low',
      });
      setShowTaskPanel(true);
    } catch (error) {
      setIsLoading(false);
      setMessages(prev => [...prev, {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const formatTime = (isoString: string) => {
    try {
      return format(new Date(isoString), 'HH:mm');
    } catch {
      return '';
    }
  };

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto w-full">
      {/* Chat Messages */}
      <div className="flex flex-col h-full">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                message.role === 'user' 
                  ? 'bg-primary-light text-primary' 
                  : 'bg-secondary/10 text-secondary'
              }`}
            >
              {message.role === 'user' ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              ) : (
                <Bot className="w-4 h-4" />
              )}
            </div>
            <div
              className={`max-w-[75%] ${message.role === 'user' ? 'text-right' : ''}`}
            >
              <div
                className={`inline-block px-4 py-2 rounded-2xl ${
                  message.role === 'user'
                    ? 'bg-primary text-white rounded-tr-sm'
                    : 'bg-surface border border-border rounded-tl-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
              <div className="flex items-center gap-2 mt-1 px-1">
                <span className="text-xs text-muted">{formatTime(message.timestamp)}</span>
                {message.role === 'assistant' && (
                  <>
                    <button
                      onClick={() => copyToClipboard(message.content)}
                      className="p-1 hover:bg-background rounded transition"
                      aria-label="Copy message"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    <button className="p-1 hover:bg-background rounded transition" aria-label="Good response">
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </button>
                    <button className="p-1 hover:bg-background rounded transition" aria-label="Bad response">
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary/10 flex items-center justify-center">
              <Bot className="w-4 h-4 text-secondary" />
            </div>
            <div className="bg-surface border border-border rounded-2xl rounded-tl-sm p-4">
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                <span className="text-sm text-muted">Deezy is thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Task Execution Panel */}
      {currentTask && showTaskPanel && (
        <TaskPanel
          task={currentTask}
          onClose={() => setShowTaskPanel(false)}
        />
      )}

      {/* Input Area */}
      <div className="border-t border-border bg-surface/50 backdrop-blur-sm sticky bottom-0">
        <div className="max-w-4xl mx-auto p-4">
          {/* Voice Recording Indicator */}
          {recordingState === 'recording' && (
            <div className="flex items-center gap-3 px-4 py-2 mb-3 bg-primary/10 border border-primary/20 rounded-lg animate-pulse">
              <Mic className="w-5 h-5 text-primary" />
              <span className="text-sm font-medium text-primary">Listening...</span>
              <span className="text-xs text-muted flex-1 text-right">
                {transcript || 'Speak now...'}
              </span>
              <button
                onClick={abortRecording}
                className="p-1.5 rounded hover:bg-background transition text-muted"
                aria-label="Cancel recording"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {recordingState === 'processing' && (
            <div className="flex items-center gap-2 px-4 py-2 mb-3 bg-warning/10 border border-warning/20 rounded-lg">
              <Loader2 className="w-4 h-4 animate-spin text-warning" />
              <span className="text-sm text-warning">Processing speech...</span>
            </div>
          )}

          <div className="flex items-end gap-2">
            <button
              className="p-2 rounded hover:bg-background transition"
              aria-label="Attach file"
            >
              <Paperclip className="w-5 h-5 text-muted" />
            </button>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={recordingState === 'recording' ? 'Listening...' : 'Ask Deezy anything...'}
              className="flex-1 min-h-[44px] max-h-48 px-4 py-3 bg-background border border-border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary-light text-sm"
              rows={1}
              aria-label="Message input"
              disabled={isLoading || recordingState === 'recording'}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading || recordingState === 'recording'}
              className="p-2.5 rounded-xl bg-primary text-white hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition flex-shrink-0"
              aria-label="Send message"
            >
              <Send className="w-5 h-5" />
            </button>
            {/* Voice Input Button */}
            <button
              onClick={recordingState === 'idle' ? startRecording : stopRecording}
              disabled={!isSTTSupported || isLoading || recordingState === 'processing'}
              className={`p-2.5 rounded-xl transition flex-shrink-0 ${
                recordingState === 'recording'
                  ? 'bg-danger/10 text-danger hover:bg-danger/20'
                  : 'bg-background hover:bg-secondary/10 text-muted'
              }`}
              aria-label={recordingState === 'recording' ? 'Stop recording' : 'Start voice input'}
              aria-pressed={recordingState === 'recording'}
            >
              {recordingState === 'recording' ? (
                <MicOff className="w-5 h-5" />
              ) : (
                <Mic className="w-5 h-5" />
              )}
            </button>
            {/* TTS Toggle */}
            <button
              onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
              disabled={!isTTSSupported}
              className={`p-2.5 rounded-xl transition flex-shrink-0 ${
                isVoiceEnabled
                  ? 'bg-background hover:bg-secondary/10 text-muted'
                  : 'bg-background hover:bg-secondary/10 text-muted opacity-50'
              }`}
              aria-label={isVoiceEnabled ? 'Disable voice playback' : 'Enable voice playback'}
              aria-pressed={isVoiceEnabled}
            >
              {isVoiceEnabled ? (
                <Volume2 className="w-5 h-5" />
              ) : (
                <VolumeX className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-muted text-center mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

interface TaskPanelProps {
  task: Task;
  onClose: () => void;
}

function TaskPanel({ task, onClose }: TaskPanelProps) {
  const getStepStatusIcon = (step: TaskStep) => {
    switch (step.status) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-primary" />;
      case 'completed':
        return <Check className="w-4 h-4 text-success" />;
      case 'failed':
        return <AlertTriangle className="w-4 h-4 text-danger" />;
      case 'cancelled':
        return <X className="w-4 h-4 text-muted" />;
      default:
        return <div className="w-4 h-4 border-2 border-border rounded-full" />;
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high': return 'text-danger bg-danger/10';
      case 'medium': return 'text-warning bg-warning/10';
      default: return 'text-success bg-success/10';
    }
  };

  return (
    <div className="border-t border-border bg-surface/50 backdrop-blur-sm">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <h3 className="font-semibold">Task Execution</h3>
            <span className={`px-2 py-0.5 text-xs rounded ${getRiskColor(task.steps[0]?.risk_level || 'low')}`}>
              {task.steps[0]?.risk_level || 'low'}
            </span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-background rounded transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="max-h-64 overflow-y-auto p-4 space-y-3">
          {task.steps.map((step, index) => (
            <div key={step.step_id} className="flex gap-3">
              <div className="flex-shrink-0 mt-1">
                {getStepStatusIcon(step)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium truncate">{step.description}</span>
                  <span className="px-1.5 py-0.5 text-xs bg-background rounded">{step.tool}</span>
                </div>
                {step.error && (
                  <p className="text-xs text-danger mt-1">{step.error}</p>
                )}
                {step.result && step.status === 'completed' && (
                  <details className="mt-1">
                    <summary className="text-xs text-muted cursor-pointer">View result</summary>
                    <pre className="mt-1 text-xs bg-background p-2 rounded overflow-auto max-h-32">
                      {JSON.stringify(step.result, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>

        {task.status === 'completed' && (
          <div className="p-4 border-t border-border bg-success/5">
            <div className="flex items-center gap-2 text-success">
              <Check className="w-5 h-5" />
              <span className="font-medium">Task completed successfully</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}