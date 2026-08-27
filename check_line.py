with open('deezy/core/agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

line = lines[333]  # Line 334
print(f'Line 334: {repr(line)}')
print(f'Length: {len(line)}')
print(f'Bytes: {list(line.encode("utf-8")[:50])}')

# Check the previous lines too
for i in range(330, 340):
    line = lines[i]
    print(f'{i+1}: {repr(line[:80])}')