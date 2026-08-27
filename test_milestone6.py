from deezy import main
from deezy.core.agent import Agent
from deezy.core.planner import Planner
from deezy.brain import get_provider

print("Imports successful")

# Test planner
planner = Planner()
plan = planner.create_plan("What is the time?")
print("Plan steps:", len(plan.steps))
for step in plan.steps:
    print("  " + step.step_id + ": " + step.tool + " - " + step.description)

# Test agent
agent = Agent()
result = agent.run("What is the time?")
print("Agent success:", result["success"])
print("Steps:", len(result["steps"]))
for s in result["steps"]:
    print("  " + s["tool"] + ": verified=" + str(s["verified"]))