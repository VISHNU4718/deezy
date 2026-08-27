# Read the file and fix indentation completely
with open('deezy/core/agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Parse with ast to understand structure, then regenerate with proper formatting
import ast

try:
    tree = ast.parse(open('deezy/core/agent.py', 'r', encoding='utf-8').read())
    # If we can parse it, use ast.unparse to get clean formatting
    if hasattr(ast, 'unparse'):
        new_source = ast.unparse(ast.parse(open('deezy/core/agent.py', 'r', encoding='utf-8').read()))
        with open('deezy/core/agent_fixed.py', 'w', encoding='utf-8') as f:
            f.write(ast.unparse(ast.parse(open('deezy/core/agent.py', 'r', encoding='utf-8').read())))
        print('Fixed with ast.unparse')
    else:
        print('ast.unparse not available')
except SyntaxError as e:
    print(f'SyntaxError: {e}')
    print(f'Line: {e.lineno}, offset: {e.offset}')
    lines = open('deezy/core/agent.py', 'r', encoding='utf-8').read().split('\n')
    if e.lineno <= len(lines):
        print(f'Problem line: {repr(lines[e.lineno-1])}')
        print(f'Offset: {e.offset}')