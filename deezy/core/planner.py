"""
Planner for Deezy.
Creates multi-step plans from objectives using LLM or heuristics.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in a plan."""

    step_id: str
    description: str
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    expected_result: str = ""
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    risk_level: str = "low"
    requires_approval: bool = False
    depends_on: List[str] = field(default_factory=list)
    verification_criteria: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool": self.tool,
            "params": self.params,
            "expected_result": self.expected_result,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "depends_on": self.depends_on,
            "verification_criteria": self.verification_criteria,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        names = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Plan:
    """A complete plan with multiple steps."""

    plan_id: str
    objective: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "status": self.status,
            "requires_approval": self.requires_approval,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        plan = cls(plan_id=data["plan_id"], objective=data["objective"], status=data.get("status", "pending"))
        plan.steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        plan.requires_approval = data.get("requires_approval", False)
        return plan


class Planner:
    """Planner that creates plans from objectives using LLM or heuristics."""

    def __init__(self, llm_provider=None, available_tools: List[Dict] = None):
        self.llm_provider = llm_provider
        self.available_tools = available_tools or []

    def create_plan(self, objective: str, context: str = "") -> Plan:
        """Create a plan from an objective."""
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        plan = Plan(plan_id=plan_id, objective=objective)

        if self._use_llm(objective):
            try:
                steps = self._create_llm_plan(objective, context)
            except Exception as e:
                logger.warning("LLM planning failed, using keyword plan: %s", e)
                steps = self._create_heuristic_plan(objective)
        else:
            steps = self._create_heuristic_plan(objective)

        for i, step_data in enumerate(steps):
            step = PlanStep(
                step_id=f"step_{i + 1}",
                description=step_data["description"],
                tool=step_data["tool"],
                params=step_data.get("params", {}),
                expected_result=step_data.get("expected_result", ""),
                risk_level=step_data.get("risk_level", "low"),
                requires_approval=step_data.get("requires_approval", False),
                depends_on=step_data.get("depends_on", []),
                verification_criteria=step_data.get("verification_criteria", ""),
            )
            plan.steps.append(step)

        # Check if any step requires approval
        plan.requires_approval = any(s.requires_approval for s in plan.steps)

        return plan

    def _create_llm_plan(self, objective: str, context: str) -> List[Dict]:
        """Create a plan using the LLM."""
        from deezy.brain.provider import Message, MessageRole

        # Build tool descriptions for the LLM
        tool_descriptions = []
        for tool in self.available_tools:
            fn = tool.get("function", {})
            tool_descriptions.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                    "category": tool.get("category", "system"),
                    "risk_level": tool.get("risk_level", "low"),
                }
            )

        tools_json = json.dumps(tool_descriptions, indent=2)

        system_prompt = (
            "You are a task planner for Deezy, a personal AI operator.\n"
            "Given an objective and available tools, create a step-by-step execution plan.\n\n"
            "Available Tools:\n"
            f"{tools_json}\n\n"
            "Rules:\n"
            "1. Use ONLY tools from the available list\n"
            "2. Each step must specify: description, tool, params, expected_result, risk_level (low/medium/high)\n"
            "3. risk_level determines approval: low=auto, medium=ask initially, high=always ask\n"
            "4. requires_approval = true for medium/high risk tools\n"
            "5. Chain steps logically - later steps can reference earlier results with {{step_1_result.field[0].subfield}}\n"
            "6. Add depends_on for explicit step dependencies using step IDs (step_1, step_2, etc.)\n"
            "7. Add verification_criteria to specify how to verify step completion\n"
            "7. Prefer fewer steps when possible\n"
            "8. Return ONLY valid JSON array of steps\n\n"
            "Example output:\n"
            "[\n"
            '  {"description": "Get system info", "tool": "get_system_info", "params": {"detail_level": "basic"}, "expected_result": "System specs", "risk_level": "low", "requires_approval": false, "depends_on": [], "verification_criteria": "System info returned with CPU, memory, disk"},\n'
            '  {"description": "Search for products", "tool": "search_products", "params": {"query": "laptop", "limit": 5}, "expected_result": "Product list", "risk_level": "low", "requires_approval": false, "depends_on": [], "verification_criteria": "Products returned with title, price, ASIN"}\n'
            "]"
        )

        user_prompt = f"Objective: {objective}\n\nContext:\n{context}\n\nCreate a plan as JSON array:"

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        response = self.llm_provider.chat(messages)
        content = response.content.strip()

        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        steps = json.loads(content)

        # Validate steps have required fields
        for step in steps:
            if "tool" not in step:
                raise ValueError("Step missing 'tool' field")
            if "description" not in step:
                step["description"] = f"Execute {step['tool']}"
            if "params" not in step:
                step["params"] = {}
            if "expected_result" not in step:
                step["expected_result"] = "Result from tool"
            if "risk_level" not in step:
                step["risk_level"] = "low"
            if "requires_approval" not in step:
                step["requires_approval"] = step["risk_level"] in ["medium", "high"]
            if "depends_on" not in step:
                step["depends_on"] = []
            if "verification_criteria" not in step:
                step["verification_criteria"] = f"Tool {step['tool']} returns success"

        return steps

    def _use_llm(self, objective: str) -> bool:
        """Use the LLM only when a real provider is configured."""
        from deezy.brain.provider import MockProvider

        if not self.llm_provider or not self.available_tools:
            return False
        return not isinstance(self.llm_provider, MockProvider)

    def _tool_names(self) -> set:
        return {t.get("function", {}).get("name") for t in self.available_tools}

    def _create_heuristic_plan(self, objective: str) -> List[Dict]:
        """
        Keyword-based planning over the registered tools. Not an LLM: it maps
        a handful of phrases to tools and falls back to a product search.
        """
        text = objective.lower()
        available = self._tool_names()

        def step(tool: str, description: str, params: Optional[Dict] = None, expected: str = "") -> Dict:
            return {
                "tool": tool,
                "description": description,
                "params": params or {},
                "expected_result": expected or description,
                "verification_criteria": f"{tool} returns data",
            }

        def has(*words: str) -> bool:
            return any(w in text for w in words)

        if has("time", "date", "day is it", "today"):
            plan = [step("get_current_time", "Get the current date and time")]
        elif has("system info", "system information", "hardware", "cpu", "memory usage", "specs"):
            plan = [step("get_system_info", "Get system information")]
        elif has("running app", "running process", "processes", "what is running", "what's running"):
            plan = [step("list_running_apps", "List running processes")]
        elif has("read file", "open file", "show file", "read the file", "cat ") or (
            re.search(r"\b(read|open|show|view|display)\b", text) and self._extract_path(objective)
        ):
            path = self._extract_path(objective) or "welcome.txt"
            plan = [step("read_file", f"Read {path}", {"path": path})]
        elif has("create file", "write file", "make a file", "save a file", "create a file", "new file") or (
            re.search(r"\b(create|write|make|save)\b", text) and self._extract_path(objective)
        ):
            path = self._extract_path(objective) or "note.txt"
            plan = [step("create_file", f"Create {path}", {"path": path, "content": self._extract_content(objective)})]
        elif has("find file", "search file", "list file", "files"):
            pattern = self._extract_glob(objective) or "*"
            plan = [step("search_files", f"Search for files matching {pattern}", {"pattern": pattern})]
        elif has(
            "add task", "add a task", "create task", "create a task", "remind me", "todo", "to-do", "add to my list"
        ):
            title = (
                re.sub(
                    r"^(please\s+)?(add|create)( a)? (task|todo|to-do)( to)?:?\s*|^remind me to\s*",
                    "",
                    objective.strip(),
                    flags=re.I,
                )
                or objective
            )
            plan = [step("create_task", "Add an item to the to-do list", {"title": title[:200]})]
        elif has("list task", "show task", "my tasks", "show my list", "todo list", "to-do list"):
            plan = [step("list_tasks", "List to-do items")]
        elif has("search the web", "web search", "google ", "look up online", "search online"):
            plan = [step("search_web", "Search the web (canned results)", {"query": objective[:200]})]
        else:
            params: Dict[str, Any] = {"query": objective[:200], "limit": 5}
            m = re.search(r"(?:under|below|less than|max(?:imum)?|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)", text)
            if m:
                params["max_price"] = float(m.group(1))
            plan = [
                step("search_products", "Search the product catalog", params, "Matching products"),
                step(
                    "evaluate_product",
                    "Evaluate the top result",
                    {"asin": "{{step_1_result.products[0].asin}}"},
                    "Score for the top product",
                ),
            ]
            plan[1]["depends_on"] = ["step_1"]

        missing = [p["tool"] for p in plan if p["tool"] not in available]
        if missing:
            raise ValueError(f"Tool not available in this deployment: {', '.join(missing)}")
        return plan

    @staticmethod
    def _extract_path(objective: str) -> Optional[str]:
        quoted = re.search(r"[\"'`]([^\"'`]+)[\"'`]", objective)
        if quoted and ("." in quoted.group(1) or "/" in quoted.group(1)):
            return quoted.group(1)
        m = re.search(r"([\w./\\-]+\.[A-Za-z0-9]{1,6})\b", objective)
        return m.group(1) if m else None

    @staticmethod
    def _extract_content(objective: str) -> str:
        m = re.search(r"(?:with (?:content|text)|containing)\s*:?\s*[\"']?(.+?)[\"']?$", objective, flags=re.I)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_glob(objective: str) -> Optional[str]:
        m = re.search(r"(\*\.[A-Za-z0-9]+|\*[\w.-]*\*?)", objective)
        if m:
            return m.group(1)
        m = re.search(r"\.([A-Za-z0-9]{2,5})\s+files|\b([a-z0-9]{2,5}) files", objective.lower())
        if m:
            ext = m.group(1) or m.group(2)
            if ext not in {"my", "the", "all", "some", "any", "find", "list", "text"}:
                return f"*.{ext}"
            if ext == "text":
                return "*.txt"
        return None

    def update_plan(self, plan: Plan, step_id: str, result: Any, error: str = None):
        """Update plan with step result."""
        for step in plan.steps:
            if step.step_id == step_id:
                if error:
                    step.status = "failed"
                    step.error = error
                else:
                    step.status = "completed"
                    step.result = result
                break
        plan.updated_at = datetime.now()
