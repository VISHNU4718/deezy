from deezy.core.agent import Agent
from deezy.core.planner import Planner
from deezy.brain import get_provider

print("Imports successful")

# Test planner
planner = Planner()
plan = planner.create_plan("What is the time?")
print("Plan steps:", len(plan.steps))
for step in plan.steps:
    print(f"  {step.step_id}: {step.tool} - {step.description}")

# Test agent
agent = Agent()
result = agent.run("What is the time?")
print("Agent success:", result["success"])
for step in result["steps"]:
    print(f"  {step['tool']}: verified={step['verified']}")