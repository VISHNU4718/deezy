with open('deezy/core/agent.py.backup', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(330, 340):
    line = lines[i]
    indent = len(line) - len(line.lstrip())
    print(f'{i+1}: indent={indent} {repr(line[:80])}')