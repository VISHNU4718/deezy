from deezy.core.agent import Agent
agent = Agent()

class MockStep:
    def __init__(self, tool, params):
        self.tool = tool
        self.params = params
        self.status = "pending"

class MockResult:
    def __init__(self, error):
        self.error = error

# Test tool_not_found recovery - this should trigger tool swap
step = MockStep('get_time', {})
result = MockResult("Tool 'get_time' not found")
recovery = agent._try_deterministic_recovery(step, result, 'tool_not_found')
print('Tool not found recovery:', recovery)
print('New tool:', step.tool)

# Test invalid_params recovery
step2 = MockStep('search_products', {'query': 'a' * 150})
result2 = MockResult("Invalid parameter: query too long")
recovery2 = agent._try_deterministic_recovery(step2, result2, 'invalid_params')
print('Invalid params recovery:', recovery2)
print('Fixed params:', step2.params)