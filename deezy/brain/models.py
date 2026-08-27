"""
Brain models and data structures for Deezy.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod


class ToolCategory(str, Enum):
    PRODUCT_RESEARCH = "product_research"
    WEBSITE = "website"
    PINTEREST = "pinterest"
    ANALYTICS = "analytics"
    SYSTEM = "system"
    BROWSER = "browser"
    FILES = "files"
    WEB_RESEARCH = "web_research"
    PRODUCTIVITY = "productivity"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    PRODUCT_DISCOVERED = "product_discovered"
    AFFILIATE_LINK_INVALID = "affiliate_link_invalid"
    TRAFFIC_ANOMALY = "traffic_anomaly"
    PINTEREST_PERFORMANCE_CHANGE = "pinterest_performance_change"
    PRODUCT_POPULARITY_CHANGE = "product_popularity_change"
    SCHEDULED_TASK_DUE = "scheduled_task_due"
    PRODUCT_EVALUATED = "product_evaluated"
    CONTENT_GENERATED = "content_generated"
    WEBSITE_CHANGED = "website_changed"


@dataclass
class ToolParameter:
    name: str
    type: str  # string, integer, number, boolean, array, object
    description: str
    required: bool = False
    default: Any = None


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.SYSTEM
    risk_level: RiskLevel = RiskLevel.LOW
    parameters: List[ToolParameter] = field(default_factory=list)

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get OpenAI-compatible tool schema."""
        properties = {}
        required = []
        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_all(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")

        if tool.risk_level == RiskLevel.HIGH:
            # High-risk tools require explicit approval
            pass  # Approval handled at orchestration level

        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def register_tool(tool: BaseTool):
    registry = get_tool_registry()
    if tool.name not in registry._tools:
        registry.register(tool)


def create_tool_from_function(
    name: str,
    description: str,
    func,
    category: ToolCategory = ToolCategory.SYSTEM,
    risk_level: RiskLevel = RiskLevel.LOW,
    parameters: List[ToolParameter] = None
) -> BaseTool:
    """Create a tool from a function."""
    class FunctionTool(BaseTool):
        def __init__(self):
            self.name = name
            self.description = description
            self.category = category
            self.risk_level = risk_level
            self.parameters = parameters or []
            self._func = func

        def execute(self, **kwargs) -> ToolResult:
            try:
                result = self._func(**kwargs)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

    return FunctionTool()


def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.SYSTEM,
    risk_level: RiskLevel = RiskLevel.LOW,
    parameters: List[ToolParameter] = None
):
    """Decorator to create a tool from a function."""
    def decorator(func):
        tool_instance = create_tool_from_function(
            name, description, func, category, risk_level, parameters
        )
        register_tool(tool_instance)
        return tool_instance
    return decorator


__all__ = [
    "ToolCategory",
    "RiskLevel",
    "TaskStatus",
    "EventType",
    "ToolParameter",
    "ToolResult",
    "BaseTool",
    "ToolRegistry",
    "get_tool_registry",
    "register_tool",
    "create_tool_from_function",
    "tool",
]