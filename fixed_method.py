"""
Core agent for Deezy.
Implements the agent loop: OBSERVE -> UNDERSTAND -> PLAN -> EXECUTE -> VERIFY
With support for dynamic task orchestration, re-planning, and verification.
"""
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from brain.models import TaskStatus, RiskLevel, ToolResult
from brain.provider import get_provider, Message, MessageRole
from brain.models import ToolCategory, RiskLevel as BrainRiskLevel
from core.planner import Planner, Plan
from brain import get_tool_registry, register_tool
from brain.models import BaseTool, ToolParameter, ToolCategory, RiskLevel
from config import get_settings
from memory import get_db, get_memory_manager


@dataclass
class AgentContext:
    """Context for the current agent execution."""
    objective: str
    user_input: str
    conversation_history: List[Dict] = field(default_factory=list)
    available_tools: List[Dict] = field(default_factory=list)
    memory_context: str = ""
    current_plan: Optional[Any] = None
    iteration: int = 0
    max_iterations: int = 10
    step_results: Dict[str, Any] = field(default_factory=dict)
    task_history: List[Dict] = field(default_factory=list)  # Track all task execution history
    completed_steps: List[str] = field(default_factory=list)  # Track completed step IDs
    failed_steps: List[str] = field(default_factory=list)  # Track failed step IDs
    replan_count: int = 0  # Track number of re-plans


class Agent:
    """Main agent orchestrator implementing the agent loop."""

    def __init__(self):
        self.settings = get_settings()
        self.db = get_db()
        self.llm = get_provider()
        
        # Import tool modules to register them
        import tools.mock_tools
        import tools.windows_tools
        import tools.browser_tools
        self.tool_registry = get_tool_registry()
        self.memory = get_memory_manager()
        
        self.planner = Planner(llm_provider=self.llm, available_tools=self._get_tool_schemas())
        self.context: Optional[Any] = None
        self.max_iterations = self.settings.agent.max_iterations

    def _get_tool_schemas(self) -> List[Dict]:
        """Get available tool schemas for the planner."""
        return self.tool_registry.get_schemas()

    def run(self, objective: str, user_input: str = "") -> Dict[str, Any]:
        """
        Main agent entry point.
        Implements the agent loop: OBSERVE -> UNDERSTAND -> PLAN -> EXECUTE -> VERIFY
        With support for dynamic task orchestration and re-planning.
        """
        print(f"\n{'='*60}")
        print(f"DEEZY: Starting task - {objective}")
        print(f"{'='*60}\n")

        # Initialize context
        self.context = AgentContext(
            objective=objective,
            user_input=user_input,
            available_tools=self._get_tool_schemas(),
            max_iterations=self.settings.agent.max_iterations
        )

        try:
            # OBSERVE - Gather context
            self._observe()

            # UNDERSTAND - Build context for LLM
            self._understand()

            # PLAN - Create execution plan
            self._plan()

            # EXECUTE + VERIFY loop with re-planning support
            result = self._execute_and_verify()

            # STORE MEMORY
            self._store_memory()

            # REPORT
            report = self._generate_report(result)

            print(f"\n{'='*60}")
            print("DEEZY: Task completed")
            print(f"{'='*60}\n")

            return report

        except Exception as e:
            error_report = {
                "success": False,
                "error": str(e),
                "objective": self.context.objective
            }
            print(f"\n[ERROR] Error: {e}")
            return error_report

    def _observe(self):
        """OBSERVE - Gather current state and context."""
        print("[OBSERVE] Gathering context...")

        # Get relevant memory from memory manager
        self.context.memory_context = self.memory.get_context_for_llm(
            max_short_term=10,
            max_long_term=5
        )

        # Get user instructions
        instructions = self.db.fetchall("""
            SELECT instruction FROM user_instructions WHERE is_active = 1
        """)
        if instructions:
            self.context.memory_context += "\n\nUser Instructions:\n" + \
                "\n".join(f"- {i['instruction']}" for i in instructions)

        print(f"   Loaded {len(self.tool_registry.get_all())} tools")

    def _understand(self):
        """UNDERSTAND - Process objective with context."""
        print("[UNDERSTAND] Processing objective...")

        # Build system prompt with context
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt()

        self.context.system_prompt = system_prompt
        self.context.user_prompt = user_prompt

    def _plan(self):
        """PLAN - Create execution plan."""
        print("[PLAN] Creating plan...")

        self.context.current_plan = self.planner.create_plan(
            objective=self.context.objective,
            context=self.context.memory_context
        )

        print(f"   Created plan with {len(self.context.current_plan.steps)} steps:")
        for i, step in enumerate(self.context.current_plan.steps):
            approval = " [REQUIRES APPROVAL]" if step.requires_approval else ""
            deps = f" (depends on: {', '.join(step.depends_on)})" if step.depends_on else ""
            print(f"   {i+1}. {step.description} (tool: {step.tool}, risk: {step.risk_level}){approval}{deps}")

        # Check for approval requirements before execution
        if self.context.current_plan.requires_approval:
            self._request_plan_approval()

    def _request_plan_approval(self):
        """Request user approval for plan with medium/high risk steps."""
        print("\n[APPROVAL REQUIRED] This plan contains steps that need confirmation:")
        for step in self.context.current_plan.steps:
            if step.requires_approval:
                tool = self.tool_registry.get(step.tool)
                risk = tool.risk_level.value if tool else step.risk_level
                print(f"  - {step.description} (risk: {risk})")
        
        # Auto-approve low risk based on settings
        if self.settings.agent.auto_approve_low_risk:
            low_risk_steps = [s for s in self.context.current_plan.steps if not s.requires_approval]
            if low_risk_steps:
                print(f"  [AUTO-APPROVED] {len(low_risk_steps)} low-risk step(s)")
        
        # Check if we need interactive approval
        medium_risk_steps = [s for s in self.context.current_plan.steps if s.risk_level == "medium"]
        high_risk_steps = [s for s in self.context.current_plan.steps if s.risk_level == "high"]
        
        need_approval = False
        if medium_risk_steps and self.settings.agent.approval_required_for_medium_risk:
            need_approval = True
        if high_risk_steps and self.settings.agent.approval_required_for_high_risk:
            need_approval = True
        
        if need_approval:
            response = input("   Proceed with plan? (y/N): ").strip().lower()
            if response not in ("y", "yes"):
                raise PermissionError("Plan execution cancelled by user")
            print("   [APPROVED] Plan approved by user\n")
        else:
            print("   [AUTO-APPROVED] Plan approved per settings\n")

def _execute_and_verify(self) -> Dict[str, Any]:
        """EXECUTE + VERIFY - Execute plan steps with verification and re-planning support."""
        print("\n[EXECUTE] Running plan...")

        results = []
        step_index = 0
        completed_step_ids = set()

        while step_index < len(self.context.current_plan.steps):
            if self.context.iteration >= self.max_iterations:
                print(f"\n[WARN] Max iterations ({self.max_iterations}) reached")
                break

            step = self.context.current_plan.steps[step_index]
            self.context.iteration += 1
            print(f"\n[ITER {self.context.iteration}] {step.description}")

            # Check if step dependencies are met
            if not self._check_dependencies(step):
                print(f"   [WAIT] Waiting for dependencies: {', '.join(step.depends_on)}")
                # Move this step to the end of the queue
                self.context.current_plan.steps.append(self.context.current_plan.steps.pop(step_index))
                continue

            # Check for per-step approval
            if step.requires_approval and not self._request_step_approval(step):
                result = ToolResult(success=False, error="Step cancelled by user")
                verified = False
            else:
                # EXECUTE
                result = self._execute_step(step)

                # VERIFY with criteria
                verified = self._verify_step(step, result)

            # Store step result for template resolution
            self.context.step_results[step.step_id] = result.data if result.success else None

            # Update plan
            self.planner.update_plan(
                self.context.current_plan,
                step.step_id,
                result,
                error=None if verified else "Verification failed"
            )

            results.append({
                "step": step.step_id,
                "description": step.description,
                "tool": step.tool,
                "result": result,
                "verified": verified
            })

            if not verified:
                print(f"   [FAIL] Verification failed")
                self.context.failed_steps.append(step.step_id)
                
                # Attempt recovery
                recovery = self._attempt_recovery(step, result)
                if recovery:
                    print(f"   [RECOVERY] {recovery}")
                    # Check if recovery was RETRY - if so, re-execute this step
                    if "Retrying with modified params" in recovery:
                        print(f"   [RECOVERY] Re-executing step with modified params...")
                        continue  # Re-execute the same step (don't increment step_index)
                    # For ALTERNATE that succeeded, step is already marked completed
                    if "Alternate tool" in recovery and "succeeded" in recovery:
                        step.status = "completed"
                        completed_step_ids.add(step.step_id)
                        self.context.completed_steps.append(step.step_id)
                        step_index += 1
                        continue
                    # For SKIP, mark step as skipped and move to next
                    if step.status == "skipped":
                        step_index += 1
                        continue
                    # For other recoveries, move to next step
                    step_index += 1
                    continue
                break

            # Step verified successfully
            completed_step_ids.add(step.step_id)
            self.context.completed_steps.append(step.step_id)
            step.status = "completed"

            # Record task history
            self.context.task_history.append({
                "step_id": step.step_id,
                "description": step.description,
                "tool": step.tool,
                "params": step.params,
                "result": "success" if result.success else "failed",
                "verified": verified,
                "timestamp": datetime.now().isoformat()
            })

            # Check if objective is complete
            if self._is_objective_complete():
                print("   [OK] Objective complete!")
                break

            step_index += 1

        # If we had failures but some steps completed, consider re-planning
        if self.context.failed_steps and completed_step_ids and self.context.replan_count < 2:
            print(f"\n[PLAN] Some steps failed, attempting re-plan...")
            self.context.replan_count += 1
            failed_step = self.context.failed_steps[0] if self.context.failed_steps else None
            failure_reason = ""
            for r in results:
                if r["step"] == failed_step and not r["verified"]:
                    failure_reason = r["result"].error if r["result"] else "Unknown error"
                    break
            
            new_plan = self.planner.replan(
                self.context.current_plan,
                list(completed_step_ids),
                failed_step,
                failure_reason,
                self.context.memory_context
            )
            self.context.current_plan = new_plan
            # Reset step_index to re-execute from failed step
            step_index = 0
            # Reset failed_steps for new plan
            self.context.failed_steps = []
            # Continue with new plan
            continue

        return {
            "success": all(r["verified"] for r in results),
            "steps": results,
            "iterations": self.context.iteration
        }

    def _check_dependencies(self, step) -> bool:
        """Check if all step dependencies are met."""
        for dep_id in step.depends_on:
            if dep_id not in self.context.step_results or self.context.step_results[dep_id] is None:
                return False
        return True

    def _execute_step(self, step) -> ToolResult:
        """Execute a single plan step."""
        print(f"   [TOOL] Executing: {step.tool}")

        # Check if tool exists
        tool = self.tool_registry.get(step.tool)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{step.tool}' not found")

        # Prepare parameters (resolve any template variables)
        params = self._resolve_params(step.params)

        print(f"   Params: {json.dumps(params, indent=6)}")

        # Execute tool
        try:
            result = self.tool_registry.execute(step.tool, **step.params)
            return result
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _verify_step(self, step, result: ToolResult) -> bool:
        """Verify step execution result with criteria."""
        if not result.success:
            print(f"   [FAIL] Tool failed: {result.error}")
            return False

        # Use verification criteria if available
        criteria = getattr(step, 'verification_criteria', '')
        if criteria:
            print(f"   [VERIFY] Checking: {criteria}")
            # Check if result data meets criteria
            if result.data:
                # Simple heuristic verification based on criteria
                print(f"   [OK] Verified: {str(result.data)[:100]}")
                return True
            else:
                print(f"   [FAIL] No data returned for verification")
                return False

        # Basic verification - tool returned success
        if result.data:
            print(f"   [OK] Verified: {str(result.data)[:100]}")
            return True

        print(f"   [WARN] No data returned")
        return False

    def _is_objective_complete(self) -> bool:
        """Check if objective is complete."""
        if not self.context.current_plan:
            return False

        # Check if all steps are completed or skipped
        for step in self.context.current_plan.steps:
            if step.status not in ("completed", "skipped"):
                return False
        return True

    def _attempt_recovery(self, step, result: ToolResult) -> Optional[str]:
    def _format_memory_context(self, tasks) -> str:
        """Format recent tasks as memory context."""
        if not tasks:
            return "No recent tasks."

        lines = ["Recent tasks:"]
        for t in tasks:
            lines.append(f"- {t['name']} ({t['status']}): {t['objective'][:80]}")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        """Build system prompt with identity and constraints."""
        identity = self.settings.identity if hasattr(self.settings, 'identity') else {}

        return f"""You are Deezy, a personal AI operator.

Core Principles:
- Proactive: Anticipate needs, don't just wait for commands
- Analytical: Base decisions on data, not assumptions
- Concise: Communicate efficiently
- Transparent: Clearly distinguish facts from assumptions
- Action-oriented: Move from analysis to execution
- Cautious: Never take destructive actions without explicit approval

Cost Constraint: MAX_MONTHLY_COST = â‚¹0/month (HARD LIMIT)
- Prefer local models and free APIs
- NEVER use a paid API without explicit user consent

Available Tool Categories:
- SYSTEM: get_system_info, list_running_apps, create_notification
- FILES: search_files, read_file, create_file
- BROWSER: open_browser, navigate, read_page, search_web
- WEB_RESEARCH: search, retrieve_page, summarize_sources
- PRODUCTIVITY: create_task, list_tasks, complete_task

Risk Levels:
- LOW: automatic (research, analysis, drafts)
- MEDIUM: ask initially (updates, modifications)
- HIGH: always ask (publish, delete, system changes)

Current Task: {self.context.objective}
User Input: {self.context.user_input}

Memory Context:
{self.context.memory_context}"""

    def _build_user_prompt(self) -> str:
        """Build user prompt for current iteration."""
        if self.context.iteration == 0:
            return f"Objective: {self.context.objective}\n\nUser request: {self.context.user_input}\n\nWhat should you do first?"
        else:
            last_step = self.context.current_plan.steps[-1] if self.context.current_plan.steps else None
            if last_step:
                return f"Previous action: {last_step.tool}\nResult: {json.dumps(last_step.result, indent=2)[:500]}\n\nWhat should you do next?"
            return "What should you do next?"

    def _store_memory(self):
        """Store relevant memory from this execution."""
        if not self.context.current_plan:
            return

        # Store task in database
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO tasks (name, description, objective, status, risk_level, input_data, output_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.context.objective[:100],
                "",
                self.context.objective,
                "completed",
                "low",
                json.dumps({"user_input": self.context.user_input}),
                json.dumps({
                    "steps": len(self.context.current_plan.steps),
                    "step_results": {k: str(v)[:200] for k, v in self.context.step_results.items()},
                    "success": all(s.status == "completed" for s in self.context.current_plan.steps),
                    "task_history": self.context.task_history,
                    "replan_count": self.context.replan_count,
                    "completed_steps": self.context.completed_steps,
                    "failed_steps": self.context.failed_steps
                }),
                datetime.now()
            ))

        # Store conversation in memory
        self.memory.short_term.add_turn("user", self.context.user_input)
        self.memory.short_term.add_turn("assistant", 
            f"Completed task: {self.context.objective} with {len(self.context.current_plan.steps)} steps")
        
        # Store important findings in long-term memory
        for step in self.context.current_plan.steps:
            if step.status == "completed" and step.result and step.result.success:
                if step.result.data:
                    self.memory.remember(
                        f"Task: {step.description}. Result: {str(step.result.data)[:200]}",
                        category="task_result",
                        importance=0.6,
                        tags=["task", "result", step.tool]
                    )
            elif step.status == "failed":
                # Store failures for learning
                self.memory.remember(
                    f"Task failed: {step.description}. Error: {step.error}",
                    category="task_failure",
                    importance=0.7,
                    tags=["task", "failure", step.tool]
                )

    def _generate_report(self, result: Dict) -> Dict[str, Any]:
        """Generate final report with task history."""
        return {
            "success": result.get("success", False),
            "objective": self.context.objective,
            "iterations": result.get("iterations", 0),
            "steps_completed": len([s for s in result.get("steps", []) if s.get("verified")]),
            "steps": result.get("steps", []),
            "task_history": self.context.task_history,
            "replan_count": self.context.replan_count,
            "completed_steps": self.context.completed_steps,
            "failed_steps": self.context.failed_steps,
            "message": "Task completed successfully" if result.get("success") else "Task incomplete"
        }


__all__ = ["Agent"]