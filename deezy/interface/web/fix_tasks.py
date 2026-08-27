with open('src/pages/TasksPage.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 257 (index 256) - change '))}' to '})}'
lines[256] = lines[256].replace('))}', '})}')

with open('src/pages/TasksPage.tsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed TasksPage.tsx line 257')