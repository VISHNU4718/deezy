"""
LLM Provider Abstraction for Deezy.
Supports multiple providers: local (Ollama), OpenAI-compatible, Anthropic, etc.
"""
import os
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    finish_reason: str = ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get("model", "llama3.2:3b")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4000)
        self.timeout = config.get("timeout", 60)
        self.max_retries = config.get("max_retries", 3)

    @abstractmethod
    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> LLMResponse:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def chat_stream(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request."""
        pass

    def _prepare_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert Message objects to provider format."""
        result = []
        for msg in messages:
            m = {"role": msg.role.value, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.name:
                m["name"] = msg.name
            result.append(m)
        return result

    def _prepare_tools(self, tools: Optional[List[Dict]]) -> Optional[List[Dict]]:
        """Prepare tools for provider."""
        if not tools:
            return None
        return tools

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry."""
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    import time
                    wait_time = (2 ** attempt) * 1.0  # 1s, 2s, 4s...
                    time.sleep(wait_time)
                else:
                    raise last_exception


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        provider_settings = config.get("provider_settings", {})
        ollama_config = provider_settings.get("local", {})

        self.base_url = ollama_config.get("base_url", "http://localhost:11434")
        self.api_key = ollama_config.get("api_key", "ollama")  # Not needed for Ollama

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Ollama API."""
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/v1/chat/completions"

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = self._prepare_tools(tools)
            payload["tool_choice"] = "auto"

        def do_request():
            return self._make_request(payload)

        data = self._retry_with_backoff(do_request)

        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                ))

        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=data.get("model", self.model),
            finish_reason=choice.get("finish_reason", "")
        )

    async def chat_stream(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> AsyncGenerator[str, None]:
        """Stream chat completion (not fully implemented for Ollama)."""
        response = self.chat(messages, tools)
        yield response.content


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (OpenRouter, OpenAI, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        provider_settings = config.get("provider_settings", {})

        # Determine which provider config to use
        provider_name = config.get("provider", "openrouter")
        provider_config = provider_settings.get(provider_name, {})

        self.api_key = provider_config.get("api_key") or os.environ.get(f"{provider_name.upper()}_API_KEY")
        self.base_url = provider_config.get("base_url", "https://openrouter.ai/api/v1")

        if not self.api_key and provider_name != "local":
            raise ValueError(f"{provider_name} API key required. Set {provider_name.upper()}_API_KEY or provide in config.")

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter" in self.base_url:
            headers["HTTP-Referer"] = "https://deeztop.com"
            headers["X-Title"] = "Deezy"

        url = f"{self.base_url}/chat/completions"

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = self._prepare_tools(tools)
            payload["tool_choice"] = "auto"

        def do_request():
            return self._make_request(payload)

        data = self._retry_with_backoff(do_request)

        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                ))

        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=data.get("model", self.model),
            finish_reason=choice.get("finish_reason", "")
        )

    async def chat_stream(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> AsyncGenerator[str, None]:
        import requests
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        if tools:
            payload["tools"] = self._prepare_tools(tools)
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter" in self.base_url:
            headers["HTTP-Referer"] = "https://deeztop.com"
            headers["X-Title"] = "Deezy"

        url = f"{self.base_url}/chat/completions"

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


class MockProvider(LLMProvider):
    """Mock provider for testing without API keys."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.responses = config.get("mock_responses", [])
        self.response_index = 0
        self._plan_cache = {}

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> LLMResponse:
        if self.responses and self.response_index < len(self.responses):
            resp = self.responses[self.response_index]
            self.response_index += 1
            return LLMResponse(
                content=resp.get("content", "Mock response"),
                tool_calls=[ToolCall(**tc) for tc in resp.get("tool_calls", [])],
                usage={"prompt_tokens": 100, "completion_tokens": 50},
                model=self.model,
                finish_reason="stop"
            )

        # Check if this is a planning request (system prompt contains planner instructions)
        system_content = ""
        for msg in messages:
            if msg.role.value == "system":
                system_content = msg.content
                break

        if "task planner" in system_content.lower() or "create a plan" in system_content.lower():
            # Return a valid plan for common test objectives
            user_content = messages[-1].content if messages else ""
            return self._generate_mock_plan(user_content)

        # Default: if tools available, make a tool call
        if tools:
            for tool in tools:
                if tool.get("function", {}).get("name") == "search_products":
                    return LLMResponse(
                        content="I'll search for products for you.",
                        tool_calls=[ToolCall(
                            id="call_1",
                            name="search_products",
                            arguments={"query": "desk", "limit": 10}
                        )],
                        usage={"prompt_tokens": 100, "completion_tokens": 50},
                        model=self.model,
                        finish_reason="tool_calls"
                    )

        return LLMResponse(
            content="Task completed.",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model=self.model,
            finish_reason="stop"
        )

    def _generate_mock_plan(self, user_prompt: str) -> LLMResponse:
        """Generate a mock plan based on the objective."""
        prompt_lower = user_prompt.lower()

        # Extract objective from the prompt (format: "Objective: <objective>\n\nContext:...")
        objective = ""
        if "objective:" in prompt_lower:
            obj_start = prompt_lower.index("objective:") + len("objective:")
            obj_end = prompt_lower.find("\n", obj_start)
            if obj_end == -1:
                obj_end = len(prompt_lower)
            objective = prompt_lower[obj_start:obj_end].strip()
        else:
            objective = prompt_lower

        if "desk lamp" in objective or "lamp" in objective:
            plan = [
                {
                    "description": "Search for desk lamps",
                    "tool": "search_products",
                    "params": {"query": "desk lamp", "limit": 10},
                    "expected_result": "List of desk lamps",
                    "risk_level": "low",
                    "requires_approval": False
                },
                {
                    "description": "Evaluate top desk lamp",
                    "tool": "evaluate_product",
                    "params": {"asin": "{{step_1_result[0].asin}}", "criteria": "relevance,price,quality"},
                    "expected_result": "Product evaluation",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]
        elif "cpu" in objective or "system" in objective:
            plan = [
                {
                    "description": "Get system information",
                    "tool": "get_system_info",
                    "params": {"detail_level": "basic"},
                    "expected_result": "System specifications",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]
        elif "app" in objective or "running" in objective:
            plan = [
                {
                    "description": "List running applications",
                    "tool": "list_running_apps",
                    "params": {"limit": 20, "sort_by": "cpu"},
                    "expected_result": "List of running applications",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]
        elif "time" in objective or "date" in objective:
            plan = [
                {
                    "description": "Get current time and date",
                    "tool": "get_current_time",
                    "params": {},
                    "expected_result": "Current time and date",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]
        elif "window" in objective:
            plan = [
                {
                    "description": "Get active window",
                    "tool": "get_active_window",
                    "params": {},
                    "expected_result": "Active window info",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]
        elif "fakeapp" in objective or "fake" in objective:
            # For testing invalid apps - minimal plan
            plan = [
                {
                    "description": "Open application: fakeapp",
                    "tool": "open_application",
                    "params": {"app": "fakeapp"},
                    "expected_result": "Application launched",
                    "risk_level": "medium",
                    "requires_approval": True
                }
            ]
        else:
            plan = [
                {
                    "description": "Search for information",
                    "tool": "search_products",
                    "params": {"query": objective[:50], "limit": 5},
                    "expected_result": "Search results",
                    "risk_level": "low",
                    "requires_approval": False
                }
            ]

        # Cache the plan
        self._plan_cache[objective] = plan

        import json
        return LLMResponse(
            content=json.dumps(plan),
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model=self.model,
            finish_reason="stop"
        )

    async def chat_stream(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> AsyncGenerator[str, None]:
        response = self.chat(messages, tools)
        yield response.content


# Provider registry
_PROVIDERS = {
    "ollama": OllamaProvider,
    "openrouter": OpenAICompatibleProvider,
    "openai": OpenAICompatibleProvider,
    "local": OllamaProvider,  # Local uses Ollama
    "anthropic": None,  # Not implemented yet
    "mock": MockProvider,
}


def get_provider(provider_name: str = None, config: Dict[str, Any] = None) -> LLMProvider:
    """Get an LLM provider instance with cost guard and fallback."""
    from deezy.config import get_settings

    settings = get_settings()

    # Cost guard - check MAX_MONTHLY_COST
    max_cost = settings.app.get("max_monthly_cost", 0)
    paid_providers = {"openrouter", "openai", "anthropic"}

    if provider_name is None:
        provider_name = settings.llm.provider

    provider_name = provider_name.lower()

    # If max_cost is 0 and provider is paid, force local or mock
    if max_cost == 0 and provider_name in paid_providers:
        if "ollama" in _PROVIDERS or "local" in _PROVIDERS:
            print(f"[COST GUARD] MAX_MONTHLY_COST=0, switching from '{provider_name}' to 'local'")
            provider_name = "local"
        else:
            print(f"[COST GUARD] MAX_MONTHLY_COST=0, switching from '{provider_name}' to 'mock'")
            provider_name = "mock"

    # Fallback chain for unavailable providers
    fallback_chain = [
        provider_name,
        "local",
        "mock",
    ]

    last_error = None
    for fallback in fallback_chain:
        if fallback not in _PROVIDERS:
            continue
        try:
            provider_class = _PROVIDERS[fallback]
            if provider_class is None:
                continue

            if config is None:
                config = {
                    "model": settings.llm.model,
                    "temperature": settings.llm.temperature,
                    "max_tokens": settings.llm.max_tokens,
                    "timeout": settings.llm.timeout,
                    "max_retries": settings.llm.max_retries,
                    "provider_settings": settings.llm.provider_settings,
                }

            provider = provider_class(config)

            # Test the provider with a quick health check
            test_response = provider.chat([
                Message(role=MessageRole.USER, content="ping")
            ])
            if test_response:
                if fallback != provider_name:
                    print(f"[FALLBACK] Using '{fallback}' instead of '{provider_name}'")
                return provider
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}. "
        f"Checked: {', '.join(f for f in fallback_chain if f in _PROVIDERS)}"
    )


def register_provider(name: str, provider_class: type):
    """Register a custom provider."""
    if not issubclass(provider_class, LLMProvider):
        raise ValueError("Provider must inherit from LLMProvider")
    _PROVIDERS[name.lower()] = provider_class


__all__ = [
    "LLMProvider",
    "Message",
    "MessageRole",
    "ToolCall",
    "LLMResponse",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "MockProvider",
    "get_provider",
    "register_provider",
]