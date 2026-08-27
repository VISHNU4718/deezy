"""
Planner for Deezy.
Creates multi-step plans from objectives using LLM or heuristics.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from brain.models import TaskStatus, RiskLevel
import json
import re


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


class Planner:
    """Planner that creates plans from objectives using LLM or heuristics."""

    def __init__(self, llm_provider=None, available_tools: List[Dict] = None):
        self.llm_provider = llm_provider
        self.available_tools = available_tools or []

    def create_plan(self, objective: str, context: str = "") -> Plan:
        """Create a plan from an objective."""
        plan_id = f"plan_{int(datetime.now().timestamp())}"
        plan = Plan(plan_id=plan_id, objective=objective)

        # Check for simple queries that should use heuristic planner
        if self._is_simple_query(objective):
            steps = self._create_heuristic_plan(objective, context)
        # Try LLM-based planning first, fallback to heuristic
        elif self.llm_provider and self.available_tools:
            try:
                steps = self._create_llm_plan(objective, context)
            except Exception as e:
                print(f"[PLAN] LLM planning failed, falling back to heuristic: {e}")
                steps = self._create_heuristic_plan(objective, context)
        else:
            steps = self._create_heuristic_plan(objective, context)

        for i, step_data in enumerate(steps):
            step = PlanStep(
                step_id=f"step_{i+1}",
                description=step_data["description"],
                tool=step_data["tool"],
                params=step_data.get("params", {}),
                expected_result=step_data.get("expected_result", ""),
                risk_level=step_data.get("risk_level", "low"),
                requires_approval=step_data.get("requires_approval", False),
                depends_on=step_data.get("depends_on", []),
                verification_criteria=step_data.get("verification_criteria", "")
            )
            plan.steps.append(step)

        # Check if any step requires approval
        plan.requires_approval = any(s.requires_approval for s in plan.steps)

        return plan

    def _create_llm_plan(self, objective: str, context: str) -> List[Dict]:
        """Create a plan using the LLM."""
        from brain.provider import Message, MessageRole

        # Build tool descriptions for the LLM
        tool_descriptions = []
        for tool in self.available_tools:
            fn = tool.get("function", {})
            tool_descriptions.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
                "category": tool.get("category", "system"),
                "risk_level": tool.get("risk_level", "low")
            })

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
            "5. Chain steps logically - later steps can reference previous results with {step_N_result}\n"
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
            Message(role=MessageRole.USER, content=user_prompt)
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

    def _is_simple_query(self, objective: str) -> bool:
        """Check if objective is a simple query that should use heuristic planning."""
        obj_lower = objective.lower().strip()
        simple_patterns = [
            "what time", "what's the time", "whats the time", "current time",
            "tell me the time", "what is the time", "time is it",
            "what date", "what's the date", "whats the date", "today's date",
            "todays date", "what is the date", "current date", "today is",
            "system info", "system information", "hardware specs",
            "running apps", "running applications", "processes",
            "active window", "foreground window",
        ]
        return any(pattern in obj_lower for pattern in simple_patterns)

    def _create_heuristic_plan(self, objective: str, context: str) -> List[Dict]:
        """Create a simple heuristic-based plan."""
        obj_lower = objective.lower()

        # HIGH-CONFIDENCE ROUTING: Time/Date queries (must come FIRST)
        time_keywords = [
            "what time", "what's the time", "whats the time", "current time",
            "tell me the time", "what is the time", "time is it",
            "what date", "what's the date", "whats the date", "today's date",
            "todays date", "what is the date", "current date", "today is"
        ]
        if any(kw in obj_lower for kw in time_keywords):
            return [
                {
                    "description": f"Get current time and date for: {objective}",
                    "tool": "get_current_time",
                    "params": {},
                    "expected_result": "Current local date, time, timezone, and day of week",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "Current time returned with date, time, timezone, day of week"
                }
            ]

        # System info / apps
        if any(kw in obj_lower for kw in ["system", "computer", "hardware", "specs", "info"]):
            return [
                {
                    "description": f"Get system information for: {objective}",
                    "tool": "get_system_info",
                    "params": {"detail_level": "basic"},
                    "expected_result": "System specifications",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "System info returned with CPU, memory, disk, OS"
                }
            ]

        if any(kw in obj_lower for kw in ["running", "apps", "applications", "processes", "programs"]):
            return [
                {
                    "description": f"List running applications: {objective}",
                    "tool": "list_running_apps",
                    "params": {"limit": 20, "sort_by": "cpu"},
                    "expected_result": "List of running applications",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "Running apps returned with PID, name, CPU, memory"
                }
            ]

        if any(kw in obj_lower for kw in ["active", "window", "foreground", "focused"]):
            return [
                {
                    "description": f"Get active window: {objective}",
                    "tool": "get_active_window",
                    "params": {},
                    "expected_result": "Active window information",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "Active window returned with title, process, PID"
                }
            ]

        # Application control
        if any(kw in obj_lower for kw in ["open", "launch", "start", "run"]):
            app_name = objective.lower().replace("open", "").replace("launch", "").replace("start", "").replace("run", "").strip()
            return [
                {
                    "description": f"Open application: {app_name}",
                    "tool": "open_application",
                    "params": {"app": app_name},
                    "expected_result": "Application launched",
                    "risk_level": "medium",
                    "requires_approval": True,
                    "depends_on": [],
                    "verification_criteria": "Application launched successfully"
                }
            ]

        if any(kw in obj_lower for kw in ["close", "quit", "kill", "stop"]):
            app_name = objective.lower().replace("close", "").replace("quit", "").replace("kill", "").replace("stop", "").strip()
            return [
                {
                    "description": f"Close application: {app_name}",
                    "tool": "close_application",
                    "params": {"app": app_name, "confirm": True},
                    "expected_result": "Application closed",
                    "risk_level": "high",
                    "requires_approval": True,
                    "depends_on": [],
                    "verification_criteria": "Application process terminated"
                }
            ]

        # File operations
        if any(kw in obj_lower for kw in ["file", "folder", "directory", "organize"]):
            if "create" in obj_lower or "make" in obj_lower or "new" in obj_lower:
                if "folder" in obj_lower or "directory" in obj_lower:
                    return [
                        {
                            "description": f"Create folder: {objective}",
                            "tool": "create_folder",
                            "params": {"path": "~/Desktop/new_folder", "parents": True},
                            "expected_result": "Folder created",
                            "risk_level": "low",
                            "requires_approval": False,
                            "depends_on": [],
                            "verification_criteria": "Folder created at specified path"
                        }
                    ]
                else:
                    return [
                        {
                            "description": f"Create file: {objective}",
                            "tool": "create_file",
                            "params": {"path": "~/Desktop/new_file.txt", "content": ""},
                            "expected_result": "File created",
                            "risk_level": "medium",
                            "requires_approval": True,
                            "depends_on": [],
                            "verification_criteria": "File created at specified path"
                        }
                    ]

            if "read" in obj_lower:
                return [
                    {
                        "description": f"Read file: {objective}",
                        "tool": "read_file",
                        "params": {"path": "~/Desktop/test.txt"},
                        "expected_result": "File contents",
                        "risk_level": "low",
                        "requires_approval": False,
                        "depends_on": [],
                        "verification_criteria": "File contents returned"
                    }
                ]

            if "write" in obj_lower or "save" in obj_lower:
                return [
                    {
                        "description": f"Write file: {objective}",
                        "tool": "create_file",
                        "params": {"path": "~/Desktop/new_file.txt", "content": ""},
                        "expected_result": "File written",
                        "risk_level": "medium",
                        "requires_approval": True,
                        "depends_on": [],
                        "verification_criteria": "File written successfully"
                    }
                ]

            if any(kw in obj_lower for kw in ["rename", "move"]):
                return [
                    {
                        "description": f"Rename/move file: {objective}",
                        "tool": "rename_file",
                        "params": {"src": "~/Desktop/old.txt", "dst": "~/Desktop/new.txt"},
                        "expected_result": "File renamed/moved",
                        "risk_level": "medium",
                        "requires_approval": True,
                        "depends_on": [],
                        "verification_criteria": "File renamed/moved successfully"
                    }
                ]

            if "folder" in obj_lower or "directory" in obj_lower:
                return [
                    {
                        "description": f"Create folder: {objective}",
                        "tool": "create_folder",
                        "params": {"path": "~/Desktop/new_folder", "parents": True},
                        "expected_result": "Folder created",
                        "risk_level": "low",
                        "requires_approval": False,
                        "depends_on": [],
                        "verification_criteria": "Folder created at specified path"
                    }
                ]

            if "search" in obj_lower or "find" in obj_lower:
                return [
                    {
                        "description": f"Search for files: {objective}",
                        "tool": "search_files",
                        "params": {"path": "~/Desktop", "pattern": "*", "recursive": True},
                        "expected_result": "List of matching files",
                        "risk_level": "low",
                        "requires_approval": False,
                        "depends_on": [],
                        "verification_criteria": "Matching files returned"
                    }
                ]

        # Product research related
        if any(kw in obj_lower for kw in ["find", "search", "discover", "product", "lamp", "desk", "chair", "monitor", "research"]):
            return [
                {
                    "description": f"Search for products related to: {objective}",
                    "tool": "search_products",
                    "params": {"query": objective, "limit": 10},
                    "expected_result": "List of relevant products",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "Products returned with title, price, ASIN"
                },
                {
                    "description": "Evaluate found products against criteria",
                    "tool": "evaluate_product",
                    "params": {"asin": "{{step_1_result[0].asin}}", "criteria": "relevance,price,quality"},
                    "expected_result": "Product scores and recommendations",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": ["step_1"],
                    "verification_criteria": "Product evaluation returned with scores and recommendation"
                }
            ]

        # System info
        if any(kw in obj_lower for kw in ["system", "computer", "hardware", "specs", "cpu", "ram", "gpu", "disk"]):
            return [
                {
                    "description": f"Get system information for: {objective}",
                    "tool": "get_system_info",
                    "params": {"detail_level": "basic"},
                    "expected_result": "System specifications",
                    "risk_level": "low",
                    "requires_approval": False,
                    "depends_on": [],
                    "verification_criteria": "System info returned with CPU, memory, disk, OS"
                }
            ]

        # Application control
        if any(kw in obj_lower for kw in ["open", "launch", "start", "run", "app", "application"]):
            app_name = objective.lower().replace("open", "").replace("launch", "").replace("start", "").replace("run", "").strip()
            return [
                {
                    "description": f"Open application: {app_name}",
                    "tool": "open_application",
                    "params": {"app": app_name},
                    "expected_result": "Application launched",
                    "risk_level": "medium",
                    "requires_approval": True,
                    "depends_on": [],
                    "verification_criteria": "Application launched successfully"
                }
            ]

        # Default: search products
        return [
            {
                "description": f"Search for information about: {objective}",
                "tool": "search_products",
                "params": {"query": objective, "limit": 5},
                "expected_result": "Relevant information",
                "risk_level": "low",
                "requires_approval": False,
                "depends_on": [],
                "verification_criteria": "Search results returned"
            }
        ]

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

    def replan(
        self,
        current_plan: Plan,
        completed_step_ids: List[str],
        failed_step_id: str = None,
        failure_reason: str = None,
        context: str = ""
    ) -> Plan:
        """Create a new plan after a failure."""
        new_plan = Plan(
            plan_id=f"replan_{int(datetime.now().timestamp())}",
            objective=current_plan.objective
        )
        
        # Copy completed steps
        for step in current_plan.steps:
            if step.step_id in completed_step_ids:
                new_plan.steps.append(step)
            elif step.step_id == failed_step_id:
                # Replace failed step with alternative
                pass
            else:
                # Keep pending steps
                new_plan.steps.append(step)
        
        new_plan.version = current_plan.version + 1
        return new_plan


__all__ = ["Plan", "PlanStep", "Planner"]