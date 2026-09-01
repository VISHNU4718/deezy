/**
 * Speech-to-Text and Text-to-Speech utilities using Web Speech API.
 * Free, browser-native, no API keys required.
 */

import { useState, useEffect, useCallback, useRef } from "react";

export type VoiceRecordingState = "idle" | "recording" | "processing";
export type VoiceSpeakingState = "idle" | "speaking" | "paused";

export interface SpeechRecognitionResult {
  transcript: string;
  isFinal: boolean;
}

export interface UseSpeechRecognitionOptions {
  language?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onResult?: (result: SpeechRecognitionResult) => void;
  onError?: (error: Error) => void;
  onEnd?: () => void;
  onStart?: () => void;
}

export interface UseSpeechRecognitionReturn {
  state: VoiceRecordingState;
  transcript: string;
  interimTranscript: string;
  isSupported: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

export interface UseSpeechSynthesisOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: Error) => void;
  onPause?: () => void;
  onResume?: () => void;
}

export interface UseSpeechSynthesisReturn {
  state: VoiceSpeakingState;
  isSupported: boolean;
  speak: (text: string, options?: SpeechSynthesisUtteranceOptions) => void;
  cancel: () => void;
  pause: () => void;
  resume: () => void;
}

export interface SpeechSynthesisUtteranceOptions {
  lang?: string;
  rate?: number;
  pitch?: number;
  volume?: number;
  voice?: SpeechSynthesisVoice | null;
}

// --- Web Speech API Type Declarations ---

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  readonly [index: number]: SpeechRecognitionResultItem;
}

interface SpeechRecognitionResultItem {
  readonly isFinal: boolean;
  readonly [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

// SpeechRecognition constructor type
interface SpeechRecognitionConstructor {
  new (): SpeechRecognition;
}

interface SpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: ((this: SpeechRecognition, ev: Event) => any) | null;
  onend: ((this: SpeechRecognition, ev: Event) => any) | null;
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => any) | null;
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => any) | null;
}

// Get SpeechRecognition constructor
function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null;
  return window.speechSynthesis;
}

// --- Speech Recognition Hook ---

export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionReturn {
  const {
    language = "en-US",
    continuous = false,
    interimResults = true,
    onResult,
    onError,
    onEnd,
    onStart,
  } = options;

  const [state, setState] = useState<VoiceRecordingState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isSupported] = useState(() => getSpeechRecognition() !== null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const isListeningRef = useRef(false);

  useEffect(() => {
    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition) return;

    recognitionRef.current = new SpeechRecognition();
    const recognition = recognitionRef.current;

    recognition.lang = language;
    recognition.continuous = continuous;
    recognition.interimResults = interimResults;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setState("recording");
      isListeningRef.current = true;
      onStart?.();
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      let interim = "";

      const results = event.results;
      const resultsLength = results ? Array.from({ length: 100 }, (_, i) => results[i]).filter(r => r !== undefined).length : 0;
      
      for (let i = event.resultIndex; i < resultsLength; i++) {
        const result = results[i];
        if (result && result.isFinal) {
          finalTranscript += result[0].transcript;
        } else if (result) {
          interim += result[0].transcript;
        }
      }

      if (finalTranscript) {
        setTranscript((prev) => prev + finalTranscript);
        onResult?.({ transcript: finalTranscript, isFinal: true });
      }
      if (interim) {
        setInterimTranscript(interim);
        onResult?.({ transcript: interim, isFinal: false });
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error("[STT] Recognition error:", event.error);
      const error = new Error(event.error);
      onError?.(error);
      setState("idle");
      isListeningRef.current = false;
    };

    recognition.onend = () => {
      isListeningRef.current = false;
      if (state === "recording") {
        setState("processing");
        setTimeout(() => setState("idle"), 300);
      }
      setInterimTranscript("");
      onEnd?.();
    };

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
      }
    };
  }, [language, continuous, interimResults, onResult, onError, onEnd, onStart, state]);

  const start = useCallback(() => {
    if (!recognitionRef.current || isListeningRef.current) return;
    setTranscript("");
    setInterimTranscript("");
    try {
      recognitionRef.current?.start();
    } catch (e) {
      console.error("[STT] Failed to start:", e);
    }
  }, []);

  const stop = useCallback(() => {
    if (!recognitionRef.current || !isListeningRef.current) return;
    try {
      recognitionRef.current?.stop();
    } catch (e) {
      console.error("[STT] Failed to stop:", e);
    }
  }, []);

  const abort = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current?.abort();
    } catch (e) {
      console.error("[STT] Failed to abort:", e);
    }
    setState("idle");
    isListeningRef.current = false;
  }, []);

  return {
    state,
    transcript,
    interimTranscript,
    isSupported,
    start,
    stop,
    abort,
  };
}

// --- Speech Synthesis Hook ---

export function useSpeechSynthesis(
  options: UseSpeechSynthesisOptions = {}
): UseSpeechSynthesisReturn {
  const { onStart, onEnd, onError, onPause, onResume } = options;

  const [state, setState] = useState<VoiceSpeakingState>("idle");
  const [isSupported] = useState(() => getSpeechSynthesis() !== null);

  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const synthesis = getSpeechSynthesis();

  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (!synthesis) return;

    const loadVoices = () => {
      const availableVoices = synthesis.getVoices();
      setVoices(availableVoices);
    };

    loadVoices();
    synthesis.onvoiceschanged = loadVoices;

    return () => {
      synthesis.onvoiceschanged = null;
    };
  }, [synthesis]);

  const speak = useCallback(
    (text: string, utteranceOptions: SpeechSynthesisUtteranceOptions = {}) => {
      if (!synthesis || !text.trim()) return;

      synthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = utteranceOptions.lang || "en-US";
      utterance.rate = utteranceOptions.rate ?? 1.0;
      utterance.pitch = utteranceOptions.pitch ?? 1.0;
      utterance.volume = utteranceOptions.volume ?? 1.0;
      utterance.voice = utteranceOptions.voice || null;

      utterance.onstart = () => {
        setState("speaking");
        onStart?.();
      };

      utterance.onend = () => {
        setState("idle");
        onEnd?.();
      };

      utterance.onerror = (event: SpeechSynthesisErrorEvent) => {
        console.error("[TTS] Synthesis error:", event.error);
        onError?.(new Error(event.error));
        setState("idle");
      };

      utterance.onpause = () => {
        setState("paused");
        onPause?.();
      };

      utterance.onresume = () => {
        setState("speaking");
        onResume?.();
      };

      utteranceRef.current = utterance;
      synthesis.speak(utterance);
    },
    [synthesis, onStart, onEnd, onError, onPause, onResume]
  );

  const cancel = useCallback(() => {
    if (synthesis) {
      synthesis.cancel();
      setState("idle");
    }
  }, [synthesis]);

  const pause = useCallback(() => {
    if (synthesis && state === "speaking") {
      synthesis.pause();
    }
  }, [synthesis, state]);

  const resume = useCallback(() => {
    if (synthesis && state === "paused") {
      synthesis.resume();
    }
  }, [synthesis, state]);

  return {
    state,
    isSupported,
    speak,
    cancel,
    pause,
    resume,
  };
}

// --- Speech Recognition Event Types ---
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

export function getAvailableVoices(): SpeechSynthesisVoice[] {
  const synthesis = getSpeechSynthesis();
  return synthesis ? synthesis.getVoices() : [];
}

export function getVoicesForLanguage(lang: string): SpeechSynthesisVoice[] {
  return getAvailableVoices().filter((v) => v.lang.startsWith(lang.split("-")[0]));
}

export function getDefaultVoice(lang: string = "en-US"): SpeechSynthesisVoice | null {
  const voices = getVoicesForLanguage(lang);
  const preferred = voices.find(
    (v) => v.name.includes("Google") || v.name.includes("Microsoft") || v.name.includes("Azure")
  );
  return preferred || voices[0] || null;
}

export function isSpeechRecognitionSupported(): boolean {
  return getSpeechRecognition() !== null;
}

export function isSpeechSynthesisSupported(): boolean {
  return getSpeechSynthesis() !== null;
}

export function checkMicrophonePermission(): Promise<PermissionState> {
  if (typeof navigator === "undefined" || !navigator.permissions) {
    return Promise.resolve("prompt" as PermissionState);
  }
  return navigator.permissions.query({ name: "microphone" as PermissionName }) as unknown as Promise<PermissionState>;
}