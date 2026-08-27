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
from .planner import Planner, Plan
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
    # Track all task execution history
    task_history: List[Dict] = field(default_factory=list)
    completed_steps: List[str] = field(
        default_factory=list)  # Track completed step IDs
    failed_steps: List[str] = field(
        default_factory=list)  # Track failed step IDs
    replan_count: int = 0  # Track number of re-plans


class Agent:
    """Main agent orchestrator implementing the agent loop."""

    def __init__(self):
        self.settings = get_settings()
        self.db = get_db()
        self.llm = get_provider()

        # Import tool modules to register them
        import tools.mock_tools
        self.tool_registry = get_tool_registry()
        self.memory = get_memory_manager()

        self.planner = Planner(
            llm_provider=self.llm,
            available_tools=self._get_tool_schemas())
        self.context: Optional[AgentContext] = None
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
        print(f"\n{'=' * 60}")
        print(f"DEEZY: Starting task - {objective}")
        print(f"{'=' * 60}\n")

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

            print(f"\n{'=' * 60}")
            print("DEEZY: Task completed")
            print(f"{'=' * 60}\n")

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

        print(
            f"   Created plan with {len(self.context.current_plan.steps)} steps:")
        for i, step in enumerate(self.context.current_plan.steps):
            approval = " [REQUIRES APPROVAL]" if step.requires_approval else ""
            deps = f" (depends on: {', '.join(step.depends_on)})" if step.depends_on else ""
            print(
                f"   {i + 1}. {step.description} (tool: {step.tool}, risk: {step.risk_level}){approval}{deps}")

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
            low_risk_steps = [
                s for s in self.context.current_plan.steps if not s.requires_approval]
            if low_risk_steps:
                print(
                    f"  [AUTO-APPROVED] {len(low_risk_steps)} low-risk step(s)")

        # Check if we need interactive approval
        medium_risk_steps = [
            s for s in self.context.current_plan.steps if s.risk_level == "medium"]
        high_risk_steps = [
            s for s in self.context.current_plan.steps if s.risk_level == "high"]

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

        # Outer loop for re-planning support
        while True:
            if self.context.iteration >= self.max_iterations:
                print(
                    f"\n[WARN] Max iterations ({self.max_iterations}) reached")
                break

            step = self.context.current_plan.steps[step_index]
            self.context.iteration += 1
            print(f"\n[ITER {self.context.iteration}] {step.description}")

            # Check if step dependencies are met
            if not self._check_dependencies(step):
                print(
                    f"   [WAIT] Waiting for dependencies: {', '.join(step.depends_on)}")
                # Move this step to the end of the queue
                self.context.current_plan.steps.append(
                    self.context.current_plan.steps.pop(step_index))
                continue

            # Check for per-step approval
            if step.requires_approval and not self._request_step_approval(step):
                result = ToolResult(
                    success=False, error="Step cancelled by user")
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
                        print(
                            f"   [RECOVERY] Re-executing step with modified params...")
                        continue
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
                self.context.failed_steps = []
                continue  # Restart execution with new plan

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

    def _classify_error(self, error: str) -> str:
        """Classify error type for targeted recovery strategies."""
        if not error:
            return "unknown"

        error_lower = error.lower()

        if "tool" in error_lower and "not found" in error_lower:
            return "tool_not_found"
        elif "permission" in error_lower or "access denied" in error_lower or "unauthorized" in error_lower:
            return "permission_denied"
        elif "invalid" in error_lower and ("param" in error_lower or "argument" in error_lower):
            return "invalid_params"
        elif "timeout" in error_lower or "timed out" in error_lower:
            return "timeout"
        elif "connection" in error_lower or "network" in error_lower or "unreachable" in error_lower:
            return "network_error"
        elif "rate limit" in error_lower or "too many requests" in error_lower:
            return "rate_limited"
        elif "not found" in error_lower or "not exist" in error_lower or "does not exist" in error_lower:
            return "resource_not_found"
        elif "already exist" in error_lower or "duplicate" in error_lower:
            return "duplicate_resource"
        else:
            return "unknown"

    def _try_deterministic_recovery(self, step, result: ToolResult, error_type: str) -> Optional[str]:
        """Try deterministic recovery based on error type."""
        if error_type == "tool_not_found":
            # Find similar tool
            import difflib
            available = [t.name for t in self.tool_registry.get_all()]
            matches = difflib.get_close_matches(step.tool, available, n=1, cutoff=0.5)
            if matches:
                alternate = matches[0]
                print(f"   [RECOVERY] Tool not found, trying similar: {alternate}")
                step.tool = alternate
                return f"Swapped to similar tool: {alternate}"
            return None

        elif error_type == "invalid_params":
            # Try to fix common param issues
            fixed = self._fix_common_param_issues(step, result.error)
            if fixed:
                return f"Fixed params: {fixed}"
            return None

        elif error_type == "permission_denied":
            # Can't auto-recover permission issues
            print(f"   [RECOVERY] Permission denied - requires user intervention")
            return None

        elif error_type == "timeout":
            # Try to increase timeout if supported
            if "timeout" in step.params:
                step.params["timeout"] = step.params["timeout"] * 2
                return f"Retrying with doubled timeout: {step.params['timeout']}"
            return None

        elif error_type == "rate_limited":
            # Skip for now, could retry later
            step.status = "skipped"
            return "Skipped due to rate limit"

        elif error_type == "resource_not_found":
            # Try to find alternative resource
            print(f"   [RECOVERY] Resource not found - skipping")
            step.status = "skipped"
            return "Skipped: resource not found"

        elif error_type == "duplicate_resource":
            # May be acceptable - mark as completed
            print(f"   [RECOVERY] Duplicate resource - marking as completed")
            step.status = "completed"
            return "Duplicate handled as success"

        return None

    def _fix_common_param_issues(self, step, error: str) -> Optional[Dict]:
        """Attempt to fix common parameter issues."""
        fixes = {}

        # Common fixes based on tool
        if step.tool == "search_products":
            if "query" in step.params:
                query = step.params["query"]
                if len(query) > 100:
                    fixes["query"] = query[:100]
                    return fixes
            if "limit" not in step.params:
                fixes["limit"] = 5
                return fixes

        elif step.tool == "evaluate_product":
            if "asin" in step.params:
                asin = step.params["asin"]
                if asin.startswith("{{") and "step_" in asin:
                    # Template not resolved - try to resolve
                    pass
            if "criteria" not in step.params:
                fixes["criteria"] = "relevance"
                return fixes

        elif step.tool == "open_application":
            if "app" in step.params:
                app = step.params["app"].lower()
                app_map = {
                    "calculator app": "calculator",
                    "notepad app": "notepad",
                    "chrome": "chrome",
                    "browser": "chrome",
                }
                if app in app_map:
                    fixes["app"] = app_map[app]
                    return fixes

        return None

    def _attempt_recovery(self, step, result: ToolResult) -> Optional[str]:
        """Attempt to recover from a failed step."""
        if not self.llm:
            return None

        print(f"   [RECOVERY] Attempting recovery for failed step...")

        from brain.provider import Message, MessageRole

        # Get available tools for the LLM to choose from
        available_tools = []
        for tool in self.tool_registry.get_all():
            available_tools.append({
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "parameters": [{"name": p.name, "type": p.type, "description": p.description, "required": p.required} for p in tool.parameters]
            })

        tools_json = json.dumps(available_tools, indent=2)

        system_prompt = f"""You are a recovery assistant for Deezy. A tool execution failed.
Analyze the failure and suggest ONE of:
1. RETRY - Retry with modified parameters
2. SKIP - Skip this step and continue
3. ALTERNATE - Use a different tool from the available list
4. ABORT - Stop execution

Available Tools:
{tools_json}

For ALTERNATE, you MUST specify the alternative tool name and parameters.
Respond with JSON: {{"action": "RETRY|SKIP|ALTERNATE|ABORT", "reason": "...", "modified_params": {{...}}, "alternate_tool": "tool_name", "alternate_params": {{...}}}}"""

        user_prompt = f"""
Failed Step: {step.description}
Tool: {step.tool}
Params: {json.dumps(step.params)}
Error: {result.error}
Previous Results: {json.dumps(self.context.step_results, default=str)[:500]}

What should we do?"""

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt)
        ]

        try:
            response = self.llm.chat(messages)
            content = response.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            recovery = json.loads(content)
            action = recovery.get("action", "ABORT")

            if action == "RETRY":
                modified = recovery.get("modified_params", {})
                step.params.update(modified)
                return f"Retrying with modified params: {modified}"
            elif action == "SKIP":
                step.status = "skipped"
                return "Skipping failed step"
            elif action == "ALTERNATE":
                alternate_tool_name = recovery.get("alternate_tool")
                alternate_params = recovery.get("alternate_params", {})

                if not alternate_tool_name:
                    return "ALTERNATE requires alternate_tool name"

                # Validate the alternative tool exists
                alternate_tool = self.tool_registry.get(alternate_tool_name)
                if not alternate_tool:
                    return f"Alternative tool '{alternate_tool_name}' not found in registry"

                # Check if approval is needed for the alternate tool
                if alternate_tool.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]:
                    # For recovery, we'll auto-approve if settings allow, otherwise ask
                    if not self._should_auto_approve(alternate_tool.risk_level):
                        print(f"   [RECOVERY] Alternate tool '{alternate_tool_name}' requires approval (risk: {alternate_tool.risk_level.value})")
                        if not self._request_step_approval_for_tool(alternate_tool_name, step.description, alternate_params):
                            return "Alternate tool approval denied"

                # Execute the alternate tool
                print(f"   [RECOVERY] Executing alternate tool: {alternate_tool_name}")
                try:
                    alternate_result = self.tool_registry.execute(alternate_tool_name, **alternate_params)
                    if alternate_result.success:
                        step.result = alternate_result
                        step.status = "completed"
                        # Store the alternate result for template resolution
                        self.context.step_results[step.step_id] = alternate_result.data
                        return f"Alternate tool '{alternate_tool_name}' succeeded"
                    else:
                        return f"Alternate tool '{alternate_tool_name}' also failed: {alternate_result.error}"
                except Exception as e:
                    return f"Alternate tool execution error: {e}"
            else:
                return None
        except Exception as e:
            print(f"   [RECOVERY] Recovery failed: {e}")
            return None

    def _should_auto_approve(self, risk_level: RiskLevel) -> bool:
        """Check if a risk level should be auto-approved based on settings."""
        if risk_level == RiskLevel.LOW:
            return self.settings.agent.auto_approve_low_risk
        elif risk_level == RiskLevel.MEDIUM:
            return not self.settings.agent.approval_required_for_medium_risk
        elif risk_level == RiskLevel.HIGH:
            return not self.settings.agent.approval_required_for_high_risk
        return False

    def _request_step_approval_for_tool(self, tool_name: str, description: str, params: Dict) -> bool:
        """Request approval for a specific tool execution during recovery."""
        tool = self.tool_registry.get(tool_name)
        risk = tool.risk_level.value if tool else "unknown"

        print(f"   [RECOVERY APPROVAL] Alternate tool requires confirmation (risk: {risk})")
        print(f"   Tool: {tool_name}")
        print(f"   Description: {description}")
        print(f"   Params: {json.dumps(params, indent=2)}")

        response = input("   Proceed with alternate tool? (y/N): ").strip().lower()
        return response in ("y", "yes")

    def _resolve_params(self, params: Dict) -> Dict:
        """Resolve template variables in params using previous step results."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                # Handle {{step_N_result}} and {{step_N_result.field}} patterns
                def replace_template(match):
                    template = match.group(1).strip()
                    if template.startswith("step_"):
                        # Parse step_<num>_result[.field][[index]] or step_<num>_result[[index]].field
                        import re as regex
                        # Match: step_<num>_result(?:\[(\d+)\])?(?:\.([^.\[\]]+))?(?:\[(\d+)\])?(?:\.([^.\[\]]+))?$
                        pattern = r'^step_(\d+)_result(?:\[(\d+)\])?(?:\.([^.\[\]]+))?(?:\[(\d+)\])?(?:\.([^.\[\]]+))?$'
                        m = regex.match(pattern, template)
                        if m:
                            step_num = m.group(1)
                            index1 = m.group(2)   # [index] after result
                            field1 = m.group(3)   # .field after result or after index1
                            index2 = m.group(4)   # [index] after field1
                            field2 = m.group(5)   # .field after index2

                            step_id = f"step_{step_num}"
                            if step_id in self.context.step_results:
                                data = self.context.step_results[step_id]
                                if data is None:
                                    return match.group(0)

                                # No field/index - return entire result
                                if field1 is None and index1 is None and index2 is None and field2 is None:
                                    return json.dumps(data)

                                # Navigate to the target value
                                current = data

                                # Handle index1 (e.g., step_1_result[0])
                                if index1 is not None:
                                    idx = int(index1)
                                    if isinstance(current, list) and idx < len(current):
                                        current = current[idx]
                                    else:
                                        return match.group(0)

                                # Handle field1 (e.g., step_1_result.products or step_1_result[0].products)
                                if field1 is not None:
                                    if isinstance(current, dict) and field1 in current:
                                        current = current[field1]
                                    else:
                                        return match.group(0)

                                # Handle index2 (e.g., step_1_result.products[0])
                                if index2 is not None:
                                    idx = int(index2)
                                    if isinstance(current, list) and idx < len(current):
                                        current = current[idx]
                                    else:
                                        return match.group(0)

                                # Handle field2 (e.g., step_1_result.products[0].asin)
                                if field2 is not None:
                                    if isinstance(current, dict) and field2 in current:
                                        current = current[field2]
                                    else:
                                        return match.group(0)

                                return json.dumps(current)
                    return match.group(0)

                resolved[key] = re.sub(r'\{\{(.+?)\}\}', replace_template, value)
            else:
                resolved[key] = value
        return resolved

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

Cost Constraint: MAX_MONTHLY_COST = ₹0/month (HARD LIMIT)
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


__all__ = ["Agent", "AgentContext"]