import pytest

from deezy.core.agent import Agent, UnresolvedReference, resolve_params, summarize_plan
from deezy.core.planner import Plan
from deezy.tools.mock_tools import ReadFileTool


def test_resolve_params_whole_value_keeps_type():
    results = {"step_1": {"items": [{"id": 7}]}}
    assert resolve_params({"id": "{{step_1_result.items[0].id}}"}, results) == {"id": 7}


def test_resolve_params_interpolates_inside_text():
    results = {"step_1": {"name": "lamp"}}
    assert resolve_params({"q": "buy {{step_1_result.name}} now"}, results) == {"q": "buy lamp now"}


def test_resolve_params_passes_plain_values_through():
    assert resolve_params({"a": 1, "b": "x"}, {}) == {"a": 1, "b": "x"}


def test_resolve_params_missing_step_raises():
    with pytest.raises(UnresolvedReference):
        resolve_params({"a": "{{step_3_result.x}}"}, {})


def test_plan_rejects_empty_and_oversized_objectives():
    agent = Agent()
    with pytest.raises(ValueError):
        agent.plan("   ")
    with pytest.raises(ValueError):
        agent.plan("x" * 5000)


def test_read_only_plan_needs_no_approval():
    plan = Agent().plan("find a desk lamp under 50")
    assert plan.steps and not plan.requires_approval


def test_file_creation_requires_approval():
    plan = Agent().plan("create a file notes.txt with content: hello")
    assert plan.requires_approval
    assert any(s.tool == "create_file" and s.requires_approval for s in plan.steps)


def test_execute_stores_task_and_summarizes():
    agent = Agent()
    plan = agent.plan("create a file agent-test.txt with content: hi there")
    report = agent.execute(plan)
    assert report["success"]
    read = agent.execute(agent.plan("read agent-test.txt"))
    assert "hi there" in read["message"]


def test_summarize_plan_with_no_results_is_not_empty():
    assert summarize_plan(Plan(plan_id="p", objective="x", steps=[])) == "Nothing to do."


@pytest.mark.parametrize("bad", ["../../etc/hosts", "/../../etc/passwd", "..\\..\\windows\\win.ini"])
def test_sandbox_blocks_traversal(bad):
    result = ReadFileTool().execute(path=bad)
    assert not result.success


def test_sandbox_reads_seeded_file():
    result = ReadFileTool().execute(path="/welcome.txt")
    assert result.success and "demo sandbox" in result.data["content"]
