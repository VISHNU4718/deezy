from deezy.core.agent import Agent
agent = Agent()

print('Testing error classification:')
test_errors = [
    "Tool 'get_time' not found",
    'Permission denied: access to file',
    'Invalid parameter: query',
    'Connection timeout',
    'Network unreachable',
    'Rate limit exceeded',
    'Resource not found: file.txt',
    'Duplicate resource: already exists',
    'Unknown error'
]

for err in test_errors:
    classified = agent._classify_error(err)
    print('  ' + str(err) + ' -> ' + str(classified))