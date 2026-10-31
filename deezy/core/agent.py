"""
Core agent for Deezy.

Loop: observe (memory) -> plan -> approve (risk gated) -> execute -> verify ->
report. Approval is delegated to a callback so the same agent runs from the CLI
(prompting on stdin) and from the web API (plan first, run after the user
approves in the UI).
"""

import difflib
import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from deezy.brain import get_tool_registry
from deezy.brain.models import RiskLevel, ToolResult
from deezy.brain.provider import get_provider
from deezy.config import get_settings
from deezy.core.planner import Plan, Planner, PlanStep
from deezy.memory import get_db, get_memory_manager

logger = logging.getLogger(__name__)

MAX_OBJECTIVE_LENGTH = 500
MAX_STEPS = 8

EventCallback = Callable[[str, Dict[str, Any]], None]
Approver = Callable[[Plan], bool]


class UnresolvedReference(Exception):
    """A step parameter referenced data an earlier step did not produce."""


_TOKEN = re.compile(r"\.?([A-Za-z_]\w*)|\[(\d+)\]")


def _lookup(data: Any, path: str) -> Any:
    """Follow a path such as ``products[0].asin`` through dicts and lists."""
    pos = 0
    while pos < len(path):
        m = _TOKEN.match(path, pos)
        if not m:
            raise UnresolvedReference(path)
        pos = m.end()
        if m.group(1) is not None:
            if not isinstance(data, dict) or m.group(1) not in data:
                raise UnresolvedReference(path)
            data = data[m.group(1)]
        else:
            idx = int(m.group(2))
            if not isinstance(data, list) or idx >= len(data):
                raise UnresolvedReference(path)
            data = data[idx]
    return data


def resolve_params(params: Dict[str, Any], step_results: Dict[str, Any]) -> Dict[str, Any]:
    """Replace ``{{step_N_result.path}}`` references with earlier step data."""
    pattern = re.compile(r"\{\{\s*step_(\d+)_result((?:\.\w+|\[\d+\])*)\s*\}\}")

    def resolve_value(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        whole = pattern.fullmatch(value.strip())

        def fetch(m: "re.Match") -> Any:
            step_id = f"step_{m.group(1)}"
            if step_results.get(step_id) is None:
                raise UnresolvedReference(m.group(0))
            return _lookup(step_results[step_id], m.group(2)) if m.group(2) else step_results[step_id]

        if whole:
            return fetch(whole)
        return pattern.sub(lambda m: str(fetch(m)), value)

    return {k: resolve_value(v) for k, v in params.items()}


def summarize_plan(plan: Plan) -> str:
    """Plain-language summary of what a plan run produced."""
    lines: List[str] = []
    for step in plan.steps:
        if step.status == "skipped":
            lines.append(f"Skipped: {step.description} ({step.error})")
            continue
        if step.status == "failed":
            lines.append(f"Failed: {step.description}: {step.error}")
            continue
        data = step.result
        if step.status != "completed" or not isinstance(data, dict):
            continue
        tool = step.tool
        if tool == "search_products":
            items = data.get("products", [])
            if items:
                top = ", ".join(f"{p['title']} ({p['price']})" for p in items[:3])
                lines.append(f"Found {len(items)} product(s). Top: {top}.")
            else:
                lines.append("No products matched that search.")
        elif tool == "evaluate_product":
            lines.append(f"{data['title']} scored {data['overall_score']} overall: {data['recommendation']}.")
        elif tool == "get_current_time":
            lines.append(f"It is {data['time']} on {data['day_of_week']}, {data['date']} ({data['timezone']}).")
        elif tool == "get_system_info":
            lines.append(
                f"{data['os']} {data['os_version']} on {data['architecture']}, {data['cpu_count']} CPUs, "
                f"{data['memory_available_gb']} of {data['memory_total_gb']} GB memory free."
            )
        elif tool == "list_running_apps":
            lines.append(f"{data['count']} processes running; listed the top {len(data['apps'])} by memory.")
        elif tool == "search_files":
            names = ", ".join(f["path"] for f in data["files"][:10])
            lines.append(
                f"Found {data['count']} file(s) in {data['searched_path']}" + (f": {names}." if names else ".")
            )
        elif tool == "read_file":
            body = data["content"][:500] + ("..." if data["size"] > 500 else "")
            lines.append(f"Read {data['path']} ({data['size']} characters):\n{body}")
        elif tool == "create_file":
            lines.append(f"Created {data['path']} ({data['size']} bytes).")
        elif tool == "create_task":
            lines.append(f"Added to-do item #{data['id']}: {data['title']}.")
        elif tool == "list_tasks":
            titles = "; ".join(f"#{i['id']} {i['title']} [{i['status']}]" for i in data["items"][:10])
            lines.append(f"{data['count']} to-do item(s)" + (f": {titles}." if titles else "."))
        elif tool == "search_web":
            lines.append(f"Returned {len(data['results'])} canned web result(s) (no live search).")
        else:
            lines.append(f"Completed {tool}.")
    if not lines:
        return "Nothing to do."
    return "\n".join(lines)


class Agent:
    """Plans and runs tasks with the registered tools."""

    def __init__(self, on_event: Optional[EventCallback] = None, approver: Optional[Approver] = None):
        # Importing registers the built-in tools.
        import deezy.tools.mock_tools  # noqa: F401

        self.settings = get_settings()
        self.db = get_db()
        self.llm = get_provider()
        self.tool_registry = get_tool_registry()
        self.memory = get_memory_manager()
        self.on_event = on_event or (lambda kind, payload: None)
        self.approver = approver
        self.planner = Planner(llm_provider=self.llm, available_tools=self.tool_registry.get_schemas())

    # -- planning -----------------------------------------------------------

    def _auto_approved(self, risk: RiskLevel) -> bool:
        agent = self.settings.agent
        if risk == RiskLevel.LOW:
            return agent.auto_approve_low_risk
        if risk == RiskLevel.MEDIUM:
            return not agent.approval_required_for_medium_risk
        return not agent.approval_required_for_high_risk

    def plan(self, objective: str) -> Plan:
        """Create a plan. Risk levels come from the tool registry, not from the planner."""
        objective = objective.strip()
        if not objective:
            raise ValueError("Objective is empty")
        if len(objective) > MAX_OBJECTIVE_LENGTH:
            raise ValueError(f"Objective is too long (limit {MAX_OBJECTIVE_LENGTH} characters)")

        context = self.memory.get_context_for_llm()
        plan = self.planner.create_plan(objective, context)
        plan.steps = plan.steps[:MAX_STEPS]
        for step in plan.steps:
            tool = self.tool_registry.get(step.tool)
            risk = tool.risk_level if tool else RiskLevel.HIGH
            step.risk_level = risk.value
            step.requires_approval = not self._auto_approved(risk)
        plan.requires_approval = any(s.requires_approval for s in plan.steps)
        self.on_event("plan_created", {"steps": len(plan.steps), "requires_approval": plan.requires_approval})
        return plan

    # -- execution ----------------------------------------------------------

    def execute(self, plan: Plan, task_id: Optional[int] = None) -> Dict[str, Any]:
        """Run every step of an (already approved) plan and store the outcome."""
        plan.status = "running"
        results: Dict[str, Any] = {}
        failed = False

        for step in plan.steps:
            if failed:
                step.status = "skipped"
                step.error = "an earlier step failed"
                continue
            step.status = "running"
            self.on_event("step_started", {"step_id": step.step_id, "tool": step.tool})
            try:
                params = resolve_params(step.params, results)
            except UnresolvedReference:
                step.status = "skipped"
                step.error = "an earlier step returned nothing to work with"
                self.on_event("step_skipped", {"step_id": step.step_id})
                continue

            result = self._run_tool(step, params)
            if not result.success:
                result = self._recover(step, params, result)
            if result.success and result.data is not None:
                step.status = "completed"
                step.result = result.data
                results[step.step_id] = result.data
                self.on_event("step_completed", {"step_id": step.step_id})
            else:
                step.status = "failed"
                step.error = result.error or "tool returned no data"
                failed = True
                self.on_event("step_failed", {"step_id": step.step_id, "error": step.error})

        plan.status = "failed" if failed else "completed"
        report = self._report(plan)
        self._store(plan, report, task_id)
        return report

    def _run_tool(self, step: PlanStep, params: Dict[str, Any]) -> ToolResult:
        if self.tool_registry.get(step.tool) is None:
            return ToolResult(success=False, error=f"Tool '{step.tool}' not found")
        try:
            return self.tool_registry.execute(step.tool, **params)
        except Exception as e:  # tools are untrusted code paths; report, don't crash the run
            logger.exception("Tool %s raised", step.tool)
            return ToolResult(success=False, error=str(e))

    def _recover(self, step: PlanStep, params: Dict[str, Any], result: ToolResult) -> ToolResult:
        """One deterministic recovery attempt: swap an unknown tool for a close match."""
        if "not found" in (result.error or "").lower() and self.tool_registry.get(step.tool) is None:
            names = [t.name for t in self.tool_registry.get_all()]
            match = difflib.get_close_matches(step.tool, names, n=1, cutoff=0.6)
            if match:
                self.on_event("recovery", {"step_id": step.step_id, "swapped_to": match[0]})
                step.tool = match[0]
                return self._run_tool(step, params)
        return result

    # -- reporting and memory ------------------------------------------------

    def _report(self, plan: Plan) -> Dict[str, Any]:
        done = [s for s in plan.steps if s.status == "completed"]
        return {
            "success": plan.status == "completed",
            "objective": plan.objective,
            "steps_completed": len(done),
            "steps_total": len(plan.steps),
            "message": summarize_plan(plan),
            "steps": [s.to_dict() for s in plan.steps],
        }

    def _store(self, plan: Plan, report: Dict[str, Any], task_id: Optional[int]) -> int:
        """Persist the run in the tasks table and add findings to memory."""
        status = "completed" if report["success"] else "failed"
        output = json.dumps({"plan": plan.to_dict(), "message": report["message"]}, default=str)
        error = None if report["success"] else report["message"]
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.transaction() as conn:
            if task_id is None:
                cur = conn.execute(
                    "INSERT INTO tasks (name, objective, status, output_data, error, started_at, completed_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (plan.objective[:100], plan.objective, status, output, error, now, now, now, now),
                )
                task_id = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE tasks SET status = ?, output_data = ?, error = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                    (status, output, error, now, now, task_id),
                )

        if self.settings.agent.enable_memory:
            self.memory.remember(
                f"Task '{plan.objective[:120]}' {status}: {report['message'][:200]}",
                category="task",
                importance=0.6,
                tags=["task", status],
            )
        return task_id

    # -- CLI entry point -----------------------------------------------------

    def run(self, objective: str) -> Dict[str, Any]:
        """Plan, ask the approver if needed, and execute."""
        plan = self.plan(objective)
        if plan.requires_approval:
            if self.approver is None or not self.approver(plan):
                plan.status = "cancelled"
                for step in plan.steps:
                    step.status = "skipped"
                    step.error = "plan not approved"
                report = self._report(plan)
                report["message"] = "Plan was not approved; nothing was run."
                self._store(plan, report, None)
                return report
        return self.execute(plan)
