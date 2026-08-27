with open('deezy/core/agent_fixed.py', 'rb') as f:
    content = f.read()

for i in range(760, 800):
    c = content[i]
    if 32 <= c < 127:
        char = chr(c)
    else:
        char = '.'
    print(f'{i}: {c} ({char})')